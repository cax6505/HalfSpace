"""Fast offline contract gate for tracked search and scouting evaluation fixtures."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILTERS = {"phase", "zone", "trigger", "team", "competition", "outcome"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    search = load_jsonl(ROOT / "search_cases.jsonl")
    assert len(search) == 100, f"expected 100 search cases, found {len(search)}"
    for index, row in enumerate(search):
        assert isinstance(row.get("query"), str) and row["query"].strip(), f"search case {index} has no query"
        assert set(row.get("expected_filters", {})) <= FILTERS, f"search case {index} has unknown filter labels"
        assert isinstance(row.get("relevant_sequence_ids"), list), f"search case {index} has no relevance list"
    scout = load_jsonl(ROOT / "scout_cases.jsonl")
    assert len(scout) == 50, f"expected 50 scout cases, found {len(scout)}"
    for row in scout:
        assert row.get("gold_sql", "").lstrip().lower().startswith("select "), f"{row.get('id')} has no SELECT gold query"
        assert row.get("expected_field") in {"sequence_count", "event_count"}, f"{row.get('id')} has invalid expected field"
    prompts = load_jsonl(ROOT / "promptfoo_cases.jsonl")
    assert len(prompts) == 100, f"expected 100 promptfoo regression cases, found {len(prompts)}"
    print("Evaluation fixtures valid: 100 search parse cases, 100 Promptfoo rows, 50 SQL scout questions.")
    print("Live parse, retrieval, and dossier score regression requires the configured API key and ingested database.")


if __name__ == "__main__":
    main()
