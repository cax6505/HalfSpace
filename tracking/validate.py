from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import read_artifact
from .metrics import evaluate_ball


def validate_path(path: str | Path) -> dict[str, object]:
    artifact = read_artifact(path)
    states = {"tracked": 0, "interpolated": 0, "lost": 0}
    maximum_players = {"home": 0, "away": 0}
    for frame in artifact.frames:
        states[frame.ball.state] += 1
        for side in maximum_players:
            maximum_players[side] = max(
                maximum_players[side],
                sum(
                    player.visible and player.team_id == side
                    for player in frame.players
                ),
            )

    summary: dict[str, object] = {
        "path": str(path),
        "schema_version": artifact.schema_version,
        "source": artifact.metadata.source,
        "title": artifact.metadata.title,
        "frames": len(artifact.frames),
        "ball_states": states,
        "maximum_visible_players_by_team": maximum_players,
    }
    if artifact.annotations and artifact.annotations.ball:
        metrics = evaluate_ball(
            (frame.ball for frame in artifact.frames),
            artifact.annotations.ball,
        )
        summary["ball_metrics"] = {
            "precision": metrics.precision,
            "recall": metrics.recall,
            "mean_position_error_m": metrics.mean_position_error_m,
            "tracked_percentage": metrics.tracked_percentage,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a HalfSpace tracking artifact.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_path(args.path), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
