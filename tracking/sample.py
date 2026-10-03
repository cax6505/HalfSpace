from __future__ import annotations

import argparse
from pathlib import Path

from .io import write_artifact
from .schema import (
    BallObservation,
    ClipMetadata,
    EvaluationAnnotations,
    PlayerTrack,
    TeamMetadata,
    TrackingArtifact,
    TrackingFrame,
)

_HOME_POSITIONS = (
    (5.0, 40.0), (18.0, 12.0), (22.0, 30.0), (22.0, 50.0), (18.0, 68.0),
    (37.0, 20.0), (41.0, 40.0), (37.0, 60.0), (57.0, 16.0), (61.0, 40.0), (57.0, 64.0),
)
_AWAY_POSITIONS = tuple((120.0 - x, y) for x, y in _HOME_POSITIONS)


def build_sample_artifact(frame_count: int = 24) -> TrackingArtifact:
    """Build a deterministic, visibly labeled sample artifact for local demos and tests."""
    teams = (
        TeamMetadata("home", "Home sample", "home", "#f2f4f7", "#d7dde5"),
        TeamMetadata("away", "Away sample", "away", "#1f2937", "#4b5563"),
    )
    metadata = ClipMetadata(
        id="sample-broadcast-01",
        source="sample",
        title="Sample data · illustrative tracking contract",
        fps=25,
        frame_count=frame_count,
        width=1920,
        height=1080,
        duration_ms=round((frame_count - 1) * 1000 / 25),
        teams=teams,
    )
    frames: list[TrackingFrame] = []
    annotations: list[BallObservation] = []
    for frame_index in range(frame_count):
        progress = frame_index / max(frame_count - 1, 1)
        players = tuple(
            PlayerTrack(
                track_id=f"{side[0]}-{player_index + 1}",
                x=x + (progress * 4 if side == "home" and player_index > 7 else 0),
                y=y,
                team_id=side,
                role="goalkeeper" if player_index == 0 else "player",
                confidence=0.95,
            )
            for side, positions in (("home", _HOME_POSITIONS), ("away", _AWAY_POSITIONS))
            for player_index, (x, y) in enumerate(positions)
        )
        x = 35.0 + progress * 50.0
        y = 40.0 + (6.0 if frame_index % 2 else -6.0)
        truth = BallObservation(x, y, "tracked", 1.0)
        annotations.append(truth)
        if frame_index in {8, 9}:
            ball = BallObservation(None, None, "lost", 0.0)
        elif frame_index == 10:
            ball = BallObservation(x - 2.0, y, "interpolated", 0.5)
        else:
            ball = BallObservation(x, y, "tracked", 0.92)
        frames.append(TrackingFrame(frame_index, round(frame_index * 1000 / 25), players, ball, 0.94))
    return TrackingArtifact(metadata, tuple(frames), EvaluationAnnotations(tuple(annotations)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a labeled HalfSpace sample tracking artifact.")
    parser.add_argument("--output", type=Path, default=Path("artifacts/sample-tracking.json"))
    args = parser.parse_args()
    write_artifact(build_sample_artifact(), args.output)
    print(f"Wrote sample data tracking artifact to {args.output}")


if __name__ == "__main__":
    main()
