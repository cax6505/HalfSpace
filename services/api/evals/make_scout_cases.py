"""Generate 50 SQL-ground-truth scout questions for common StatsBomb teams."""
import json
from pathlib import Path

teams = ["Arsenal", "Barcelona", "Bayern Munich", "Chelsea", "Liverpool", "Manchester City", "Manchester United", "Real Madrid", "Tottenham Hotspur", "Juventus"]
phases = ["build-up", "counter-attack", "set-piece", "zone-entry"]
rows = []
for team in teams:
    escaped = team.replace("'", "''")
    for phase in phases:
        query = f"How many {phase} sequences do we have for {team}?"
        sql = f"SELECT COUNT(*) AS sequence_count, MIN(s.id) AS sequence_id FROM sequences s JOIN possessions p ON p.match_id=s.match_id AND p.possession_id=s.possession_id JOIN teams t ON t.id=p.team_id WHERE t.name ILIKE '%{escaped}%' AND s.tag='{phase}'"
        rows.append({"id": f"{team.lower().replace(' ', '-')}-{phase}", "team": team, "query": query, "gold_sql": sql, "expected_field": "sequence_count", "ground_truth": None, "ground_truth_evidence_id": None})
    query = f"How many corners were taken by {team}?"
    sql = f"SELECT COUNT(*) AS event_count, MIN(e.id) AS event_id FROM events e JOIN teams t ON t.id=e.team_id WHERE t.name ILIKE '%{escaped}%' AND e.raw->'pass'->'type'->>'name'='Corner'"
    rows.append({"id": f"{team.lower().replace(' ', '-')}-corners", "team": team, "query": query, "gold_sql": sql, "expected_field": "event_count", "ground_truth": None, "ground_truth_evidence_id": None})
assert len(rows) == 50
path = Path(__file__).with_name("scout_cases.jsonl")
path.write_text("".join(json.dumps(row) + "\n" for row in rows))
