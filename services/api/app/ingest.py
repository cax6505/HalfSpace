"""Idempotently load StatsBomb open data, defaulting to two competitions."""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

import httpx
from sqlalchemy import text

from app.db import get_engine, initialize
from app.models import SequenceToken
from app.segmentation import segment_possessions
from app.settings import settings


def fetch_json(client: httpx.Client, url: str) -> Any:
    response = client.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def _upsert_event(conn: Any, match_id: int, event: dict[str, Any]) -> None:
    event_id = str(event["id"])
    event_type = (event.get("type") or {}).get("name", "Unknown")
    team = event.get("team") or {}
    player = event.get("player") or {}
    loc = event.get("location")
    outcome = ((event.get("pass") or {}).get("outcome") or {}).get("name")
    seconds = (event.get("minute", 0) or 0) * 60 + (event.get("second", 0) or 0)
    conn.execute(text("""INSERT INTO events (id,match_id,possession_id,event_index,period,minute,second,team_id,player_id,event_type,location,outcome,time_seconds,raw)
      VALUES (:id,:mid,:pid,:idx,:period,:minute,:second,:team,:player,:type,CAST(:loc AS jsonb),:outcome,:seconds,CAST(:raw AS jsonb))
      ON CONFLICT (id) DO UPDATE SET match_id=excluded.match_id,possession_id=excluded.possession_id,event_index=excluded.event_index,period=excluded.period,minute=excluded.minute,second=excluded.second,team_id=excluded.team_id,player_id=excluded.player_id,event_type=excluded.event_type,location=excluded.location,outcome=excluded.outcome,time_seconds=excluded.time_seconds,raw=excluded.raw"""), {
        "id": event_id, "mid": match_id, "pid": event.get("possession"), "idx": event.get("index", 0), "period": event.get("period"),
        "minute": event.get("minute"), "second": event.get("second"), "team": team.get("id"), "player": player.get("id"),
        "type": event_type, "loc": json.dumps(loc) if loc is not None else None, "outcome": outcome, "seconds": seconds,
        "raw": json.dumps(event),
    })
    conn.execute(text("DELETE FROM freeze_frames WHERE event_id=:id"), {"id": event_id})
    if team.get("id") is not None:
        conn.execute(text("INSERT INTO teams(id,name) VALUES(:id,:name) ON CONFLICT(id) DO UPDATE SET name=excluded.name"), {"id": team["id"], "name": team.get("name", "Unknown")})
    if player.get("id") is not None:
        conn.execute(text("INSERT INTO players(id,name,team_id) VALUES(:id,:name,:team) ON CONFLICT(id) DO UPDATE SET name=excluded.name,team_id=excluded.team_id"), {"id": player["id"], "name": player.get("name", "Unknown"), "team": team.get("id")})
    for frame in (event.get("shot") or {}).get("freeze_frame", []):
        conn.execute(text("INSERT INTO freeze_frames(event_id,frame) VALUES(:id,CAST(:frame AS jsonb)) ON CONFLICT DO NOTHING"), {"id": event_id, "frame": json.dumps(frame)})


def _token(event: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    location = event.get("location") or [0, 0]
    x, y = (float(location[0]), float(location[1])) if len(location) >= 2 else (0, 0)
    outcome = ((event.get("pass") or {}).get("outcome") or {}).get("name") or ((event.get("shot") or {}).get("outcome") or {}).get("name") or "none"
    now = (event.get("minute", 0) or 0) * 60 + (event.get("second", 0) or 0)
    before = ((previous or {}).get("minute", 0) or 0) * 60 + ((previous or {}).get("second", 0) or 0)
    token = SequenceToken(event_type=(event.get("type") or {}).get("name", "Unknown"), zone=(min(11, max(0, int(x / 120 * 12))), min(7, max(0, int(y / 80 * 8)))), outcome=outcome, time_delta=max(0, now - before))
    return token.model_dump()


def ingest() -> Counter[str]:
    base = settings.stats_bomb_data_url.rstrip("/")
    engine = get_engine()
    initialize(engine)
    counts: Counter[str] = Counter()
    with httpx.Client() as client:
        competitions = fetch_json(client, f"{base}/competitions.json")
        configured = os.getenv("COMPETITION_IDS", settings.competition_ids).strip()
        ids = [int(value) for value in configured.split()] if configured else list(dict.fromkeys(int(c["competition_id"]) for c in competitions))[:2]
        if len(ids) < 2 and not configured:
            raise RuntimeError("StatsBomb returned fewer than two competitions")
        for competition_id in ids:
            seasons = [c for c in competitions if int(c["competition_id"]) == competition_id]
            if not seasons:
                raise ValueError(f"Unknown StatsBomb competition_id={competition_id}")
            for season in seasons:
                season_id = int(season["season_id"])
                matches = fetch_json(client, f"{base}/matches/{competition_id}/{season_id}.json")
                for match in matches:
                    match_id = int(match["match_id"])
                    home = match.get("home_team") or {}
                    away = match.get("away_team") or {}
                    with engine.begin() as conn:
                        conn.execute(text("""INSERT INTO matches(id,competition_id,season_id,match_date,home_team_id,away_team_id,raw)
                          VALUES(:id,:comp,:season,:date,:home,:away,CAST(:raw AS jsonb)) ON CONFLICT(id) DO UPDATE SET raw=excluded.raw,match_date=excluded.match_date"""), {
                            "id": match_id, "comp": competition_id, "season": season_id, "date": match.get("match_date"), "home": home.get("home_team_id", home.get("id")), "away": away.get("away_team_id", away.get("id")), "raw": json.dumps(match),
                        })
                    events = fetch_json(client, f"{base}/events/{match_id}.json")
                    for event in events:
                        event["_match_id"] = match_id
                    grouped: dict[int, list[dict[str, Any]]] = {}
                    with engine.begin() as conn:
                        for event in events:
                            _upsert_event(conn, match_id, event)
                            pid = event.get("possession")
                            if pid is not None:
                                grouped.setdefault(int(pid), []).append(event)
                        for pid, group in grouped.items():
                            times = [(e.get("minute", 0) or 0) * 60 + (e.get("second", 0) or 0) for e in group]
                            conn.execute(text("""INSERT INTO possessions(match_id,possession_id,team_id,start_seconds,end_seconds) VALUES(:match,:pid,:team,:start,:end)
                              ON CONFLICT(match_id,possession_id) DO UPDATE SET team_id=excluded.team_id,start_seconds=excluded.start_seconds,end_seconds=excluded.end_seconds"""), {"match": match_id, "pid": pid, "team": (group[0].get("possession_team") or {}).get("id"), "start": min(times), "end": max(times)})
                            # Replace phases for this possession so reruns reflect changed source data.
                            conn.execute(text("DELETE FROM sequences WHERE match_id=:match AND possession_id=:pid"), {"match": match_id, "pid": pid})
                            for sequence in segment_possessions(group):
                                tokens = [_token(event, sequence.events[index - 1] if index else None) for index, event in enumerate(sequence.events)]
                                conn.execute(text("INSERT INTO sequences(match_id,possession_id,phase_index,tag,tokens) VALUES(:match,:pid,:phase,:tag,CAST(:tokens AS jsonb))"), {"match": match_id, "pid": pid, "phase": sequence.phase_index, "tag": sequence.tag, "tokens": json.dumps(tokens)})
                                counts[sequence.tag] += 1
    return counts


if __name__ == "__main__":
    result = ingest()
    print("Sequence counts by tag:")
    for tag, count in sorted(result.items()):
        print(f"{tag}: {count}")
