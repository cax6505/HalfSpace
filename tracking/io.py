from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from .schema import (
    BallObservation,
    ClipMetadata,
    EvaluationAnnotations,
    PlayerTrack,
    TeamMetadata,
    TrackingArtifact,
    TrackingFrame,
)


def write_artifact(artifact: TrackingArtifact, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_artifact(path: str | Path) -> TrackingArtifact:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return artifact_from_dict(payload)


def artifact_from_dict(payload: dict[str, Any]) -> TrackingArtifact:
    metadata_payload = payload["metadata"]
    metadata = ClipMetadata(
        **{name: metadata_payload[name] for name in _field_names(ClipMetadata) if name != "teams"},
        teams=tuple(TeamMetadata(**team) for team in metadata_payload.get("teams", [])),
    )
    frames = tuple(
        TrackingFrame(
            frame_index=frame["frame_index"],
            timestamp_ms=frame["timestamp_ms"],
            homography_confidence=frame.get("homography_confidence"),
            players=tuple(PlayerTrack(**player) for player in frame.get("players", [])),
            ball=BallObservation(**frame["ball"]),
        )
        for frame in payload.get("frames", [])
    )
    annotation_payload = payload.get("annotations")
    annotations = None
    if annotation_payload is not None:
        annotations = EvaluationAnnotations(
            ball=tuple(BallObservation(**ball) for ball in annotation_payload.get("ball", [])),
            player_positions={
                track_id: tuple(position)
                for track_id, position in annotation_payload.get("player_positions", {}).items()
            },
        )
    return TrackingArtifact(
        metadata=metadata,
        frames=frames,
        annotations=annotations,
        schema_version=payload.get("schema_version", "tracking/v1"),
    )


def _field_names(model: type[Any]) -> set[str]:
    return {field.name for field in fields(model)}
