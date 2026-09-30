"""Shared read-only research tools used by LangGraph and the MCP server."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.db import get_engine
from app.search import _fts_candidates, _rerank, _rrf, _sequence_text, _vector_candidates, embed_query, parse_intent
from app.settings import settings
from app.sql_guard import SQLGuardError, validate_readonly_sql
from app.tracing import traced


class SQLProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sql: str = Field(min_length=1, max_length=20_000)


SCHEMA_DESCRIPTION = """
events(id text event identifier, match_id, possession_id, team_id, player_id, event_type, location jsonb, outcome, time_seconds, raw jsonb)
sequences(id integer sequence identifier, match_id, possession_id, phase_index, tag, tokens jsonb, embedding vector)
possessions(match_id, possession_id, team_id, start_seconds, end_seconds)
matches(id, competition_id, season_id, match_date, home_team_id, away_team_id, raw jsonb)
teams(id, name), competitions(id, name), players(id, name, team_id), freeze_frames(id, event_id, frame jsonb)
"""


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _db_rows(sql: str) -> list[dict[str, Any]]:
    with get_engine().connect() as conn:
        with conn.begin():
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(f"SET LOCAL statement_timeout = '{int(settings.scout_statement_timeout_ms)}ms'")
            rows = conn.execute(text(sql)).mappings().all()
    return [_json_safe(dict(row)) for row in rows]


def _evidence_from_rows(rows: list[dict[str, Any]], tool: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for row in rows:
        event_values: list[Any] = []
        sequence_values: list[Any] = []
        for key, value in row.items():
            normalized = key.lower()
            if normalized in {"event_id", "event_ids"}:
                event_values.extend(value if isinstance(value, (list, tuple)) else [value])
            elif normalized in {"sequence_id", "sequence_ids"}:
                sequence_values.extend(value if isinstance(value, (list, tuple)) else [value])
        facts = {key: value for key, value in row.items() if key.lower() not in {"event_id", "event_ids", "sequence_id", "sequence_ids"}}
        for event_id in event_values:
            if event_id is not None:
                evidence.append({"evidence_id": f"event:{event_id}", "kind": "event", "tool": tool, "facts": facts})
        for sequence_id in sequence_values:
            if sequence_id is not None:
                evidence.append({"evidence_id": f"sequence:{sequence_id}", "kind": "sequence", "tool": tool, "facts": facts})
    return evidence


@traced("scout.guarded_sql")
def guarded_text_to_sql(question: str, team: str | None = None) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for guarded text-to-SQL")
    client_args = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_args["base_url"] = settings.openai_base_url
    client = OpenAI(**client_args)
    completion = client.chat.completions.parse(
        model=settings.search_llm_model,
        temperature=0,
        response_format=SQLProposal,
        messages=[
            {"role": "system", "content": "Write one read-only PostgreSQL SELECT over only the supplied public football schema. Always project stable source identifiers as e.id AS event_id or s.id AS sequence_id; for aggregate rows include MIN(e.id) AS event_id or MIN(s.id) AS sequence_id. Do not aggregate lists of IDs. No mutations, comments, unallowlisted functions, or multiple statements. Use SQL literals with normal escaping. Return SQL only in the schema.\n" + SCHEMA_DESCRIPTION},
            {"role": "user", "content": f"Team context: {team or 'unspecified'}\nResearch question: {question}"},
        ],
    )
    proposal = completion.choices[0].message.parsed
    if proposal is None:
        raise SQLGuardError("Text-to-SQL model returned no valid query")
    safe_sql = validate_readonly_sql(proposal.sql)
    rows = _db_rows(safe_sql)
    usage = completion.usage
    return {"sql": safe_sql, "row_count": len(rows), "usage": {"input_tokens": usage.prompt_tokens if usage else 0, "output_tokens": usage.completion_tokens if usage else 0}, "evidence": _evidence_from_rows(rows, "guarded_text_to_sql")}


@traced("scout.search_sequences")
def search_sequences(query: str, limit: int = 10) -> dict[str, Any]:
    intent, parse_usage = parse_intent(query)
    vector, embedding_tokens = embed_query(intent.semantic_query)
    vector_rows = _vector_candidates(vector, intent.filters, intent.exemplar_sequence_id)
    fts_rows = _fts_candidates(intent.semantic_query, intent.filters) if intent.exemplar_sequence_id is None else []
    ranked = _rrf(vector_rows, fts_rows)
    ranked = _rerank(intent.semantic_query, ranked[:settings.search_candidate_limit])[:max(1, min(limit, 50))]
    evidence = []
    for row in ranked:
        tokens = row["tokens"] if isinstance(row["tokens"], list) else json.loads(row["tokens"])
        evidence.append({"evidence_id": f"sequence:{row['id']}", "kind": "sequence", "tool": "search_sequences", "facts": {"tag": row["tag"], "score": float(row.get("rerank_score", row["score"])), "tokens": tokens, "text": _sequence_text(row)}})
    return {"count": len(evidence), "usage": {"input_tokens": parse_usage["input_tokens"], "output_tokens": parse_usage["output_tokens"], "embedding_tokens": embedding_tokens}, "evidence": evidence}


def _resolve_match(team: str | None, match_id: int | None) -> int | None:
    if match_id and not team:
        return match_id
    if not team:
        return None
    sql = text("""SELECT m.id FROM matches m
      WHERE (CAST(:match_id AS bigint) IS NULL OR m.id=:match_id)
      AND EXISTS (SELECT 1 FROM teams t WHERE t.name ILIKE :team AND t.id IN (m.home_team_id,m.away_team_id))
      ORDER BY m.match_date DESC NULLS LAST,m.id DESC LIMIT 1""")
    with get_engine().connect() as conn:
        value = conn.execute(sql, {"team": f"%{team}%", "match_id": match_id}).scalar_one_or_none()
    return int(value) if value is not None else None


def _resolve_team_id(team: str | None) -> int | None:
    if not team:
        return None
    with get_engine().connect() as conn:
        value = conn.execute(text("SELECT id FROM teams WHERE name ILIKE :team ORDER BY id LIMIT 1"), {"team": f"%{team}%"}).scalar_one_or_none()
    return int(value) if value is not None else None


def _xt_value(location: Any) -> float:
    if not isinstance(location, (list, tuple)) or len(location) < 2:
        return 0.0
    x = min(1.0, max(0.0, float(location[0]) / 120.0))
    y = min(1.0, max(0.0, float(location[1]) / 80.0))
    centrality = 1.0 - 0.45 * min(1.0, abs(y - 0.5) * 2.0)
    return 0.12 * max(0.0, (x - 0.15) / 0.85) ** 3 * centrality


@traced("scout.expected_threat")
def calculate_xt(team: str | None = None, match_id: int | None = None, limit: int = 1000) -> dict[str, Any]:
    selected_match = _resolve_match(team, match_id)
    if selected_match is None:
        return {"summary": "No matching match found", "evidence": []}
    team_id = _resolve_team_id(team)
    sql = text("""SELECT id,player_id,team_id,event_type,location,raw FROM events
      WHERE match_id=:match AND (:team_id IS NULL OR team_id=:team_id)
      AND event_type IN ('Pass','Carry') ORDER BY event_index LIMIT :limit""")
    with get_engine().connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, {"match": selected_match, "team_id": team_id, "limit": max(1, min(limit, 5000))}).mappings()]
    evidence = []; total = 0.0
    for index, row in enumerate(rows):
        raw = row["raw"] if isinstance(row["raw"], dict) else json.loads(row["raw"])
        start = row["location"] if isinstance(row["location"], (list, tuple)) else json.loads(row["location"] or "null")
        end = (raw.get("pass") or {}).get("end_location") if row["event_type"] == "Pass" else None
        if not end and index + 1 < len(rows):
            next_loc = rows[index + 1]["location"]
            end = next_loc if isinstance(next_loc, (list, tuple)) else json.loads(next_loc or "null")
        if not end or not start:
            continue
        outcome = (raw.get("pass") or {}).get("outcome") or {}
        if outcome and row["event_type"] == "Pass":
            continue
        delta = _xt_value(end) - _xt_value(start); total += delta
        evidence.append({"evidence_id": f"event:{row['id']}", "kind": "event", "tool": "calculate_xt", "facts": {"match_id": selected_match, "event_type": row["event_type"], "player_id": row["player_id"], "xt_added": round(delta, 6), "from": start, "to": end}})
    if evidence:
        action_count = len(evidence)
        evidence.append({"evidence_id": evidence[0]["evidence_id"], "kind": "event", "tool": "calculate_xt", "facts": {"xt_added": round(total, 4), "actions": action_count, "supporting_event_ids": [item["evidence_id"] for item in evidence]}})
    else:
        action_count = 0
    return {"match_id": selected_match, "team": team, "xt_added": round(total, 4), "actions": action_count, "method": "heuristic zone-value estimate; not a trained xT model", "evidence": evidence}


@traced("scout.passing_network")
def passing_network(team: str | None = None, match_id: int | None = None, limit: int = 1000) -> dict[str, Any]:
    selected_match = _resolve_match(team, match_id)
    if selected_match is None:
        return {"match_id": None, "edges": [], "evidence": []}
    team_id = _resolve_team_id(team)
    sql = text("""SELECT e.id,e.player_id,pp.name AS passer,(e.raw->'pass'->'recipient'->>'id') AS recipient_id,
      (e.raw->'pass'->'recipient'->>'name') AS recipient,e.team_id
      FROM events e LEFT JOIN players pp ON pp.id=e.player_id
      WHERE e.match_id=:match AND (:team_id IS NULL OR e.team_id=:team_id) AND e.event_type='Pass' AND e.outcome IS NULL
      ORDER BY e.event_index LIMIT :limit""")
    with get_engine().connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, {"match": selected_match, "team_id": team_id, "limit": max(1, min(limit, 5000))}).mappings()]
    groups: dict[tuple[int | None, str | None, int | None, str | None], list[str]] = defaultdict(list)
    for row in rows:
        recipient_id = int(row["recipient_id"]) if row["recipient_id"] else None
        groups[(row["player_id"], row["passer"], recipient_id, row["recipient"])].append(str(row["id"]))
    edges = []; evidence = []
    for (source_id, source, target_id, target), ids in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True):
        edge = {"from_player_id": source_id, "from_player": source, "to_player_id": target_id, "to_player": target, "passes": len(ids)}
        edges.append(edge)
        evidence.append({"evidence_id": f"event:{ids[0]}", "kind": "event", "tool": "passing_network", "facts": {**edge, "supporting_event_ids": ids}})
    return {"match_id": selected_match, "edges": edges, "evidence": evidence}


@traced("scout.pitch_control_360")
def pitch_control_360(match_id: int | None = None, team: str | None = None) -> dict[str, Any]:
    selected_match = _resolve_match(team, match_id)
    if selected_match is None:
        return {"match_id": None, "grid": [], "evidence": []}
    team_id = _resolve_team_id(team)
    sql = text("""SELECT e.id AS event_id,e.team_id AS attacking_team_id,ff.frame
      FROM freeze_frames ff JOIN events e ON e.id=ff.event_id
      WHERE e.match_id=:match AND (:team_id IS NULL OR e.team_id=:team_id) ORDER BY e.event_index LIMIT 10000""")
    with get_engine().connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, {"match": selected_match, "team_id": team_id}).mappings()]
    grouped: dict[str, list[tuple[int | None, dict[str, Any]]]] = defaultdict(list)
    for row in rows:
        frame = row["frame"] if isinstance(row["frame"], dict) else json.loads(row["frame"])
        grouped[str(row["event_id"])].append((row["attacking_team_id"], frame))
    controlled = [[0 for _ in range(8)] for _ in range(12)]; samples = [[0 for _ in range(8)] for _ in range(12)]
    evidence = []
    for event_id, frames in grouped.items():
        players = [frame for _, frame in frames if len(frame.get("location", [])) >= 2]
        if not players: continue
        for x in range(12):
            for y in range(8):
                px, py = (x + 0.5) * 10.0, (y + 0.5) * 10.0
                nearest = min(players, key=lambda p: (float(p["location"][0])-px)**2 + (float(p["location"][1])-py)**2)
                samples[x][y] += 1
                if nearest.get("teammate"): controlled[x][y] += 1
        evidence.append({"evidence_id": f"event:{event_id}", "kind": "event", "tool": "pitch_control_360", "facts": {"match_id": selected_match, "frame_players": len(players), "nearest_player_snapshot": True}})
    grid = [{"x": x, "y": y, "attacking_team_control_share": round(controlled[x][y] / samples[x][y], 4) if samples[x][y] else None, "frames": samples[x][y]} for x in range(12) for y in range(8)]
    frame_count = len(evidence)
    if evidence:
        evidence.append({"evidence_id": evidence[0]["evidence_id"], "kind": "event", "tool": "pitch_control_360", "facts": {"pitch_control_grid": grid, "frame_count": frame_count, "supporting_event_ids": [item["evidence_id"] for item in evidence]}})
    return {"match_id": selected_match, "frames": frame_count, "method": "nearest player per cell from available StatsBomb 360 snapshots; no velocity model", "grid": grid, "evidence": evidence}


@traced("scout.set_piece_summary")
def set_piece_summary(team: str | None = None, match_id: int | None = None, limit: int = 1000) -> dict[str, Any]:
    selected_match = _resolve_match(team, match_id)
    if selected_match is None:
        return {"match_id": None, "summary": [], "evidence": []}
    team_id = _resolve_team_id(team)
    sql = text("""SELECT id,team_id,
      COALESCE(raw->'pass'->'type'->>'name',raw->'shot'->'type'->>'name',event_type) AS event_type,
      player_id,outcome FROM events
      WHERE match_id=:match AND (:team_id IS NULL OR team_id=:team_id)
      AND (raw->'pass'->'type'->>'name' IN ('Corner','Free Kick','Throw-in','Penalty')
        OR raw->'shot'->'type'->>'name'='Penalty' OR event_type IN ('Corner','Free Kick','Throw-in','Penalty'))
      ORDER BY event_index LIMIT :limit""")
    with get_engine().connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, {"match": selected_match, "team_id": team_id, "limit": max(1, min(limit, 5000))}).mappings()]
    counts = Counter((row["event_type"], row["team_id"], row["outcome"] or "no explicit outcome") for row in rows)
    summary = []; evidence = []
    for (event_type, team_id, outcome), count in counts.items():
        ids = [str(row["id"]) for row in rows if (row["event_type"], row["team_id"], row["outcome"] or "no explicit outcome") == (event_type, team_id, outcome)]
        item = {"restart": event_type, "team_id": team_id, "outcome": outcome, "count": count}
        summary.append(item)
        evidence.append({"evidence_id": f"event:{ids[0]}", "kind": "event", "tool": "set_piece_summary", "facts": {**item, "supporting_event_ids": ids}})
    return {"match_id": selected_match, "summary": summary, "evidence": evidence}
