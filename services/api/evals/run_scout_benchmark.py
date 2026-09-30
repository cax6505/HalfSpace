"""Compute SQL gold answers, then compare LangGraph with a one-shot baseline."""
from __future__ import annotations

import asyncio
import json
import math
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent_graph import build_scout_graph, initial_state, report_cost, run_single_agent_baseline
from app.scout_tools import _db_rows
from app.sql_guard import validate_readonly_sql


ROOT = Path(__file__).resolve().parents[3]
CASES_PATH = ROOT / "services/api/evals/scout_cases.jsonl"


def _numeric_answers(report: dict) -> list[float]:
    statements = []
    dossier = report.get("dossier", report)
    if dossier.get("overview"):
        statements.append(dossier["overview"].get("statement", ""))
    statements.extend(claim.get("statement", "") for claim in dossier.get("claims", []))
    return [float(value.replace(",", "")) for statement in statements for value in re.findall(r"(?<![A-Za-z])\d+(?:,\d{3})*(?:\.\d+)?", statement)]


def _result_metrics(rows: list[dict]) -> dict:
    accuracy = [row["correct"] for row in rows if row["correct"] is not None]
    submitted = sum(row["submitted_claims"] for row in rows)
    supported = sum(row["supported_claims"] for row in rows)
    dropped = sum(row["dropped_claims"] for row in rows)
    latencies = [row["latency_ms"] for row in rows]
    return {
        "accuracy": statistics.mean(accuracy) if accuracy else None,
        "groundedness_rate": supported / submitted if submitted else 0.0,
        "hallucination_rate": dropped / submitted if submitted else 0.0,
        "avg_steps": statistics.mean(row["steps"] for row in rows),
        "p50_latency_ms": statistics.median(latencies),
        "p95_latency_ms": sorted(latencies)[min(len(latencies)-1, max(0, math.ceil(0.95*len(latencies))-1))],
        "cost_per_query_usd": statistics.mean(row["cost_usd"] for row in rows),
    }


async def _run_graph(team: str, query: str) -> tuple[dict, int]:
    graph = build_scout_graph(); current = dict(initial_state(team, query)); steps = 0
    async for update in graph.astream(current, stream_mode="updates"):
        for _node, delta in update.items():
            current.update(delta)
            steps += int("trace_event" in delta)
    return current, steps


async def main():
    cases = [json.loads(line) for line in CASES_PATH.read_text().splitlines() if line.strip()]
    # Gold answers are generated on the live corpus by guarded SQL. Never hand-fill IDs or values.
    for case in cases:
        rows = _db_rows(validate_readonly_sql(case["gold_sql"]))
        case["ground_truth"] = rows[0][case["expected_field"]] if rows else None
        identifier_field = "sequence_id" if rows and "sequence_id" in rows[0] else "event_id" if rows and "event_id" in rows[0] else None
        value = rows[0].get(identifier_field) if identifier_field and rows else None
        case["ground_truth_evidence_id"] = f"{'sequence' if identifier_field == 'sequence_id' else 'event'}:{value}" if value is not None else None
    CASES_PATH.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases))
    runs = {"LangGraph multi-agent": [], "Single-agent baseline": []}
    for index, case in enumerate(cases, 1):
        truth = case.get("ground_truth")
        graph_started = time.perf_counter()
        try:
            state, steps = await _run_graph(case["team"], case["query"])
            dossier = state.get("dossier", {})
            verification = dossier.get("verification", {})
            answers = _numeric_answers(dossier)
            correct = any(math.isclose(value, float(truth), rel_tol=1e-4, abs_tol=1e-4) for value in answers) if truth is not None else None
            runs["LangGraph multi-agent"].append({"correct": correct, "submitted_claims": verification.get("submitted_claims", 0), "supported_claims": verification.get("supported_claims", 0), "dropped_claims": verification.get("dropped_claims", 0), "steps": steps, "latency_ms": (time.perf_counter()-graph_started)*1000, "cost_usd": report_cost(state), "error": None})
        except Exception as exc:
            runs["LangGraph multi-agent"].append({"correct": False if truth is not None else None, "submitted_claims": 0, "supported_claims": 0, "dropped_claims": 0, "steps": 0, "latency_ms": (time.perf_counter()-graph_started)*1000, "cost_usd": 0.0, "error": str(exc)[:400]})
        baseline_started = time.perf_counter()
        try:
            state = await run_single_agent_baseline(case["team"], case["query"])
            dossier = state.get("dossier", {})
            verification = dossier.get("verification", {})
            answers = _numeric_answers(dossier)
            correct = any(math.isclose(value, float(truth), rel_tol=1e-4, abs_tol=1e-4) for value in answers) if truth is not None else None
            runs["Single-agent baseline"].append({"correct": correct, "submitted_claims": verification.get("submitted_claims", 0), "supported_claims": verification.get("supported_claims", 0), "dropped_claims": verification.get("dropped_claims", 0), "steps": 8, "latency_ms": (time.perf_counter()-baseline_started)*1000, "cost_usd": report_cost(state), "error": None})
        except Exception as exc:
            runs["Single-agent baseline"].append({"correct": False if truth is not None else None, "submitted_claims": 0, "supported_claims": 0, "dropped_claims": 0, "steps": 8, "latency_ms": (time.perf_counter()-baseline_started)*1000, "cost_usd": 0.0, "error": str(exc)[:400]})
        print(f"[{index}/{len(cases)}] benchmark case complete")
    summary = {name: _result_metrics(rows) for name, rows in runs.items()}
    result = {"case_count": len(cases), "ground_truth_ready": sum(case.get("ground_truth") is not None for case in cases), "summary": summary, "runs": runs}
    (ROOT / "services/api/evals/scout_results.json").write_text(json.dumps(result, indent=2))
    doc = ROOT / "docs/EVALS.md"; current = doc.read_text(); marker = "\n## Scout dossier benchmark\n"; current = current.split(marker)[0]
    table = ["", "| Approach | Accuracy | Groundedness rate | Hallucination rate | Steps (avg) | p50 latency (ms) | p95 latency (ms) | Cost/query (USD) |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, metric in summary.items():
        def fmt(value, digits=3): return "Not measured" if value is None else f"{value:.{digits}f}"
        table.append(f"| {name} | {fmt(metric['accuracy'])} | {fmt(metric['groundedness_rate'])} | {fmt(metric['hallucination_rate'])} | {metric['avg_steps']:.1f} | {metric['p50_latency_ms']:.1f} | {metric['p95_latency_ms']:.1f} | ${metric['cost_per_query_usd']:.6f} |")
    section = f"\n## Scout dossier benchmark\n\nCases: {len(cases)}. SQL ground truth populated for {result['ground_truth_ready']}/{len(cases)} questions. Accuracy checks whether a verified dossier claim contains the SQL answer. Groundedness is verified claims divided by submitted claims. Hallucination rate is dropped claims divided by submitted claims. Costs include configured model and embedding API rates, excluding database and local cross-encoder compute.\n\n" + "\n".join(table) + "\n"
    doc.write_text(current.rstrip()+"\n"+section)
    print(json.dumps({"case_count": len(cases), "ground_truth_ready": result["ground_truth_ready"], "summary": summary}, indent=2))


if __name__ == "__main__": asyncio.run(main())
