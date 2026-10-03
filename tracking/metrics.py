from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable

from .schema import BallObservation, TrackingArtifact


@dataclass(frozen=True)
class BallMetrics:
    ground_truth_frames: int
    predicted_frames: int
    true_positive_frames: int
    precision: float
    recall: float
    mean_position_error_m: float | None
    tracked_percentage: float


@dataclass(frozen=True)
class PlayerMetrics:
    evaluated_tracks: int
    id_switches: int


def evaluate_ball(
    predictions: Iterable[BallObservation],
    ground_truth: Iterable[BallObservation],
    match_radius_m: float = 2.0,
) -> BallMetrics:
    predicted = tuple(predictions)
    truth = tuple(ground_truth)
    if len(predicted) != len(truth):
        raise ValueError("ball prediction and ground-truth sequences must have equal length")
    errors: list[float] = []
    true_positives = 0
    for prediction, target in zip(predicted, truth):
        if target.state == "lost" or target.x is None or target.y is None:
            continue
        if prediction.state == "lost" or prediction.x is None or prediction.y is None:
            continue
        error = hypot(prediction.x - target.x, prediction.y - target.y)
        errors.append(error)
        true_positives += int(error <= match_radius_m)
    ground_truth_frames = sum(target.state != "lost" and target.x is not None and target.y is not None for target in truth)
    predicted_frames = sum(prediction.state != "lost" and prediction.x is not None and prediction.y is not None for prediction in predicted)
    false_positives = predicted_frames - true_positives
    precision = true_positives / predicted_frames if predicted_frames else 0.0
    recall = true_positives / ground_truth_frames if ground_truth_frames else 0.0
    tracked_percentage = predicted_frames / len(predicted) * 100 if predicted else 0.0
    return BallMetrics(
        ground_truth_frames=ground_truth_frames,
        predicted_frames=predicted_frames,
        true_positive_frames=true_positives,
        precision=precision,
        recall=recall,
        mean_position_error_m=sum(errors) / len(errors) if errors else None,
        tracked_percentage=tracked_percentage,
    )


def evaluate_player_id_switches(artifact: TrackingArtifact) -> PlayerMetrics:
    """Count team/role changes for stable track IDs across consecutive frames."""
    previous: dict[str, tuple[str | None, str]] = {}
    switches = 0
    evaluated_tracks: set[str] = set()
    for frame in artifact.frames:
        current: dict[str, tuple[str | None, str]] = {}
        for player in frame.players:
            if not player.visible:
                continue
            identity = (player.team_id, player.role)
            current[player.track_id] = identity
            evaluated_tracks.add(player.track_id)
            if player.track_id in previous and previous[player.track_id] != identity:
                switches += 1
        previous = current
    return PlayerMetrics(evaluated_tracks=len(evaluated_tracks), id_switches=switches)
