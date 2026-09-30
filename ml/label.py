from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

from sqlalchemy import create_engine, text


def main() -> None:
    parser = argparse.ArgumentParser(description="Hand-label tactical sequence records")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--output", default="ml/data/labels.jsonl")
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://halfspace:halfspace@localhost:5432/halfspace")
    engine = create_engine(url)
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM sequences")).scalar_one()
        if total < args.count:
            raise SystemExit(f"Need {args.count} sequences in the database; found {total}. Run make ingest first.")
        rows = conn.execute(text("SELECT id,match_id,possession_id,phase_index,tag,tokens FROM sequences ORDER BY id")).mappings().all()
    rng = random.Random(args.seed); rng.shuffle(rows)
    classes = ["counter-attack", "build-up", "set-piece", "press-win", "high-press", "low-block", "possession", "transition"]
    print("Enter an integer label, or 's' to skip. Labels:")
    for i, label in enumerate(classes, 1): print(f"  {i}. {label}")
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    existing = {json.loads(line)["id"]: json.loads(line) for line in output.read_text().splitlines() if line.strip()} if output.exists() else {}
    pending = [r for r in rows if f"{r['match_id']}:{r['possession_id']}:{r['phase_index']}" not in existing]
    with output.open("a") as stream:
        done = 0
        for row in pending:
            if done >= args.count: break
            sid = f"{row['match_id']}:{row['possession_id']}:{row['phase_index']}"
            print(f"\n{sid} | existing rule tag: {row['tag']}")
            for token in row["tokens"][:24]: print(f"  {token.get('event_type')} {token.get('zone')} {token.get('outcome')}")
            answer = input("Class (1-8, s skip, q quit): ").strip().lower()
            if answer == "q": break
            if answer == "s": continue
            if not answer.isdigit() or not 1 <= int(answer) <= len(classes):
                print("Please enter 1-8, s, or q."); continue
            stream.write(json.dumps({"id": sid, "label": classes[int(answer) - 1]}) + "\n"); stream.flush(); done += 1
            print(f"Saved {done}/{args.count} in this session.")
    print(f"Labels saved to {output}")


if __name__ == "__main__":
    main()
