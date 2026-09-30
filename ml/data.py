from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

import torch
from torch.nn.utils.rnn import pad_sequence

from model import encode_tokens


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def export_db(path: Path) -> None:
    from sqlalchemy import create_engine, text
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://halfspace:halfspace@localhost:5432/halfspace")
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, match_id, possession_id, phase_index, tokens FROM sequences ORDER BY id")).mappings()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as out:
            for row in rows:
                out.write(json.dumps({"id": f"{row['match_id']}:{row['possession_id']}:{row['phase_index']}", "tokens": row["tokens"]}) + "\n")


def augment(sequence: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    tokens = [dict(t) for t in sequence["tokens"]]
    if len(tokens) > 1 and rng.random() < 0.5:
        start = rng.randrange(min(3, len(tokens)))
        end = max(start + 1, len(tokens) - rng.randrange(min(3, len(tokens))))
        tokens = tokens[start:end]
    if rng.random() < 0.5:
        for token in tokens:
            if len(token.get("zone", [])) >= 2:
                token["zone"] = [11 - int(token["zone"][0]), int(token["zone"][1])]
    for token in tokens:
        zone = token.get("zone", [0, 0])
        token["zone"] = [max(0, min(11, int(zone[0]) + rng.choice([-1, 0, 0, 1]))), max(0, min(7, int(zone[1]) + rng.choice([-1, 0, 0, 1])))]
        token["time_delta"] = max(0.0, float(token.get("time_delta", 0)) * rng.uniform(0.9, 1.1))
    return {"id": sequence["id"], "tokens": tokens or sequence["tokens"][:1]}


def collate(batch: list[dict[str, Any]]) -> tuple[torch.Tensor, ...]:
    encoded = [encode_tokens(item["tokens"]) for item in batch]
    seqs = [list(x[0].shape)[0] for x in encoded]
    max_len = max(seqs)
    def pad(field: int, value: float = 0):
        return pad_sequence([x[field] for x in encoded], batch_first=True, padding_value=value)
    event, zone, outcome, delta = pad(0), pad(1), pad(2), pad(3)
    mask = torch.arange(max_len).unsqueeze(0) < torch.tensor(seqs).unsqueeze(1)
    return event, zone, outcome, delta, mask
