"""Review retrieval candidates and attach human-judged relevant sequence IDs."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.search import _fts_candidates, _rrf, _vector_candidates, embed_query, parse_intent


async def main():
    path = Path(__file__).with_name("search_cases.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for index, case in enumerate(cases, 1):
        if case.get("gold_status") == "human_reviewed":
            continue
        intent, _ = await asyncio.to_thread(parse_intent, case["query"])
        vector, _ = await asyncio.to_thread(embed_query, intent.semantic_query)
        vectors, lexical = await asyncio.gather(
            asyncio.to_thread(_vector_candidates, vector, intent.filters),
            asyncio.to_thread(_fts_candidates, intent.semantic_query, intent.filters),
        )
        candidates = _rrf(vectors, lexical)[:20]
        print(f"\n[{index}/{len(cases)}] {case['query']}")
        print(f"Expected filters: {case['expected_filters']}")
        for row in candidates:
            tokens = row.get("tokens") or []
            if isinstance(tokens, str): tokens = json.loads(tokens)
            preview = ", ".join(token.get("event_type", "?") for token in tokens[:6])
            print(f"  id={row['id']} tag={row['tag']} preview={preview}")
        answer = input("Relevant sequence IDs (comma separated; 'none' or 'q'): ").strip()
        if answer.lower() == "q": break
        if answer.lower() == "none": relevant = []
        else:
            try: relevant = sorted({int(part.strip()) for part in answer.split(",") if part.strip()})
            except ValueError:
                print("IDs must be comma-separated integers; leaving this case unannotated."); continue
        case["relevant_sequence_ids"] = relevant
        case["gold_status"] = "human_reviewed"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cases))
        print(f"Saved relevance judgment: {relevant}")
    remaining = sum(row.get("gold_status") != "human_reviewed" for row in cases)
    print(f"Reviewed {len(cases) - remaining}/{len(cases)} query relevance sets.")


if __name__ == "__main__": asyncio.run(main())
