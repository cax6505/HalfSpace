"""Build a 100-query starter set; sequence relevance IDs require data-backed review."""
from __future__ import annotations

import json
from pathlib import Path

rows = []
def add(query: str, filters: dict):
    rows.append({"query": query, "expected_filters": filters, "relevant_sequence_ids": [], "gold_status": "needs_relevance_annotation"})

phases = ["counter-attack", "build-up", "set-piece", "press-win-trigger", "zone-entry"]
for phase in phases:
    for wording in (f"Find {phase} sequences", f"Show me examples of {phase} play"):
        add(wording, {"phase": phase})
zones = [
    ("own third", {"x_min": 0, "x_max": 3, "y_min": 0, "y_max": 7}),
    ("middle third", {"x_min": 4, "x_max": 7, "y_min": 0, "y_max": 7}),
    ("attacking third", {"x_min": 8, "x_max": 11, "y_min": 0, "y_max": 7}),
    ("left channel", {"x_min": 0, "x_max": 11, "y_min": 0, "y_max": 1}),
    ("central channel", {"x_min": 0, "x_max": 11, "y_min": 2, "y_max": 5}),
    ("right channel", {"x_min": 0, "x_max": 11, "y_min": 6, "y_max": 7}),
]
for zone_name, zone in zones:
    add(f"Find sequences in the {zone_name}", {"zone": zone})
    add(f"Show attacking sequences from the {zone_name}", {"zone": zone})
triggers = ["ball recovery", "counterpress", "interception", "tackle", "pressure", "clearance", "keeper distribution", "turnover", "second ball", "press win"]
for trigger in triggers:
    add(f"Show possessions triggered by a {trigger}", {"trigger": trigger})
teams = ["Arsenal", "Barcelona", "Bayern Munich", "Chelsea", "Liverpool", "Manchester City", "Manchester United", "Real Madrid", "Tottenham Hotspur", "Juventus"]
for team in teams:
    add(f"Find build-up sequences for {team}", {"phase": "build-up", "team": team})
for competition in range(1, 11):
    add(f"Show counter-attacks in competition {competition}", {"phase": "counter-attack", "competition": str(competition)})
outcomes = ["Complete", "Incomplete", "Success", "Saved", "Goal", "Blocked", "Out", "Lost", "Won", "Offside"]
for outcome in outcomes:
    add(f"Find sequences with outcome {outcome}", {"outcome": outcome})
for i in range(10):
    team = teams[i]
    phase = phases[i % len(phases)]
    zone_name, zone = zones[i % len(zones)]
    add(f"Find {phase} sequences for {team} in the {zone_name}", {"phase": phase, "team": team, "zone": zone})
for i in range(10):
    phase = phases[i % len(phases)]
    outcome = outcomes[i]
    add(f"Find {outcome.lower()} outcomes during {phase} play", {"phase": phase, "outcome": outcome})
for query in [
    "Show me attacks that move quickly toward goal", "Find patient possession around the box", "Sequences where the defense wins the ball high", "How does the team escape pressure?", "Show dangerous transitions after a turnover", "Find wide progression followed by a cross", "Which possessions enter the penalty area?", "Show sustained attacks that end in a shot", "Find defensive recoveries and the next pass", "How are set pieces defended?",
]:
    add(query, {})
for i in range(8):
    phase = phases[i % len(phases)]
    trigger = triggers[i]
    add(f"Find {phase} play after a {trigger} in the attacking third", {"phase": phase, "trigger": trigger, "zone": zones[2][1]})

assert len(rows) == 100, len(rows)
root = Path(__file__).parent
(root / "search_cases.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
(root / "promptfoo_cases.jsonl").write_text("".join(json.dumps({"vars": {"query": row["query"], "expected_filters": row["expected_filters"]}}, ensure_ascii=False) + "\n" for row in rows))
