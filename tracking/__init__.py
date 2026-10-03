"""Typed, precomputed tracking artifacts used by the HalfSpace product."""

from .schema import (
    BallObservation,
    BallState,
    ClipMetadata,
    EvaluationAnnotations,
    PlayerRole,
    PlayerTrack,
    TeamMetadata,
    TrackingArtifact,
    TrackingFrame,
    validate_frame,
)
from .metrics import BallMetrics, PlayerMetrics, evaluate_ball, evaluate_player_id_switches

__all__ = [
    "BallObservation",
    "BallState",
    "ClipMetadata",
    "EvaluationAnnotations",
    "PlayerRole",
    "PlayerTrack",
    "TeamMetadata",
    "TrackingArtifact",
    "TrackingFrame",
    "validate_frame",
    "BallMetrics",
    "PlayerMetrics",
    "evaluate_ball",
    "evaluate_player_id_switches",
]
