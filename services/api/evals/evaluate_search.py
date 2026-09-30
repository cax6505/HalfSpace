"""Run the 100-query search set across vector/FTS/hybrid/reranked retrieval."""
from __future__ import annotations

import asyncio
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.search import _cross_encoder, _fts_candidates, _rerank, _rrf, _vector_candidates, embed_query, parse_intent
from app.settings import settings


def _recall(ids: list[int], relevant: list[int]) -> float | None:
    return len(set(ids[:10]) & set(relevant)) / len(relevant) if relevant else None


def _cost(llm: dict[str, int], embedding_tokens: int) -> float:
    return (llm["input_tokens"] * settings.search_cost_input_per_million + llm["output_tokens"] * settings.search_cost_output_per_million + embedding_tokens * settings.search_embedding_cost_per_million) / 1_000_000


def _timed(fn, *args):
    start = time.perf_counter(); result = fn(*args)
    return result, (time.perf_counter() - start) * 1000


async def evaluate():
    root = Path(__file__).resolve().parents[3]
    cases = [json.loads(line) for line in (root / "services/api/evals/search_cases.jsonl").read_text().splitlines() if line.strip()]
    measurements = {name: {"latency": [], "recall": [], "cost": []} for name in ("Vector only", "FTS only", "Hybrid", "Hybrid + rerank")}
    parse_ok = 0; parse_total = 0; query_runs = []
    cross_encoder = await asyncio.to_thread(_cross_encoder)
    await asyncio.to_thread(cross_encoder.predict, [("warmup", "warmup")], show_progress_bar=False)
    for index, case in enumerate(cases, 1):
        start = time.perf_counter()
        intent, llm_usage = await asyncio.to_thread(parse_intent, case["query"])
        expected = case["expected_filters"]
        actual = intent.filters.model_dump()
        filter_fields = ("phase", "zone", "trigger", "team", "competition", "outcome")
        parse_total += 1
        parse_ok += int(all(actual.get(key) == expected.get(key) for key in filter_fields))
        vector, embedding_tokens = await asyncio.to_thread(embed_query, intent.semantic_query)
        retrieval_start = time.perf_counter(); pre_retrieval_ms = (retrieval_start - start) * 1000
        (vector_rows, vector_ms), (fts_rows, fts_ms) = await asyncio.gather(
            asyncio.to_thread(_timed, _vector_candidates, vector, intent.filters, intent.exemplar_sequence_id),
            asyncio.to_thread(_timed, _fts_candidates, intent.semantic_query, intent.filters),
        )
        hybrid = _rrf(vector_rows, fts_rows)
        rerank_start = time.perf_counter()
        reranked = await asyncio.to_thread(_rerank, intent.semantic_query, hybrid[:settings.search_candidate_limit])
        rerank_elapsed = (time.perf_counter() - rerank_start) * 1000
        cost = _cost(llm_usage, embedding_tokens)
        latencies_by_mode = {
            "Vector only": pre_retrieval_ms + vector_ms,
            "FTS only": pre_retrieval_ms + fts_ms,
            "Hybrid": pre_retrieval_ms + max(vector_ms, fts_ms),
            "Hybrid + rerank": pre_retrieval_ms + max(vector_ms, fts_ms) + rerank_elapsed,
        }
        relevant = case.get("relevant_sequence_ids", [])
        result_ids = {
            "Vector only": [int(row["id"]) for row in vector_rows],
            "FTS only": [int(row["id"]) for row in fts_rows],
            "Hybrid": [int(row["id"]) for row in hybrid],
            "Hybrid + rerank": [int(row["id"]) for row in reranked],
        }
        for name, ids in result_ids.items():
            # Include LLM parse and embedding for all modes; add rerank work for the final mode.
            measurements[name]["latency"].append(latencies_by_mode[name])
            measurements[name]["cost"].append(cost)
            score = _recall(ids, relevant)
            if score is not None: measurements[name]["recall"].append(score)
        query_runs.append({"query": case["query"], "expected_filters": expected, "parsed_filters": actual, "candidate_ids": result_ids, "relevant_sequence_ids": relevant, "latency_ms_by_mode": latencies_by_mode, "cost_usd": cost})
        print(f"[{index}/{len(cases)}] search evaluation complete")
    metric = {}
    for name, values in measurements.items():
        latencies = values["latency"]
        metric[name] = {
            "recall@10": statistics.mean(values["recall"]) if values["recall"] else None,
            "p50_latency_ms": statistics.median(latencies),
            "p95_latency_ms": sorted(latencies)[min(len(latencies)-1, max(0, math.ceil(0.95 * len(latencies)) - 1))],
            "cost_per_query_usd": statistics.mean(values["cost"]),
        }
    results = {"query_count": len(cases), "filter_parse_accuracy": parse_ok / parse_total if parse_total else None, "annotated_retrieval_queries": sum(bool(c.get("relevant_sequence_ids")) for c in cases), "ablation": metric, "queries": query_runs}
    out = root / "services/api/evals/search_results.json"; out.write_text(json.dumps(results, indent=2))
    doc = root / "docs/EVALS.md"; text_doc = doc.read_text()
    marker = "\n## Search retrieval ablation\n"; text_doc = text_doc.split(marker)[0]
    has_gold = results["annotated_retrieval_queries"] > 0
    table = ["", "| Retrieval mode | Recall@10 | p50 latency (ms) | p95 latency (ms) | Cost/query (USD) |", "|---|---:|---:|---:|---:|"]
    for name, values in metric.items():
        recall = f"{values['recall@10']:.3f}" if values["recall@10"] is not None else "Needs relevance labels"
        table.append(f"| {name} | {recall} | {values['p50_latency_ms']:.1f} | {values['p95_latency_ms']:.1f} | ${values['cost_per_query_usd']:.6f} |")
    section = f"\n## Search retrieval ablation\n\nQueries: {len(cases)}. Filter parse accuracy (field-level exact matches): {results['filter_parse_accuracy']:.3f}. Relevant-ID annotations: {results['annotated_retrieval_queries']}/{len(cases)}. Latency includes LLM parsing and query embedding; rerank mode additionally includes cross-encoder latency. Cost includes configured OpenAI chat and embedding token prices and excludes database/Redis/compute charges. {'' if has_gold else 'Recall is withheld because the fixture has no human-annotated relevant sequence IDs yet.'}\n\n" + "\n".join(table) + "\n"
    doc.write_text(text_doc.rstrip() + "\n" + section)
    print(json.dumps({k: v for k, v in results.items() if k != "queries"}, indent=2))


if __name__ == "__main__": asyncio.run(evaluate())
