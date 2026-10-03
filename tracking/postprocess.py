from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .schema import BallObservation


@dataclass(frozen=True)
class BallPostprocessConfig:
    fps: float
    max_gap_frames: int = 5
    max_speed_mps: float = 38.0

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError("fps must be positive")
        if self.max_gap_frames < 0:
            raise ValueError("max_gap_frames must not be negative")
        if self.max_speed_mps <= 0:
            raise ValueError("max_speed_mps must be positive")


def postprocess_ball(
    observations: tuple[BallObservation, ...],
    config: BallPostprocessConfig,
) -> tuple[BallObservation, ...]:
    """Reject impossible jumps and interpolate only short, bounded gaps."""
    accepted: list[BallObservation | None] = []
    last_accepted_index: int | None = None
    for index, observation in enumerate(observations):
        candidate = observation if observation.state != "lost" else None
        if candidate is not None and accepted:
            previous = next((item for item in reversed(accepted) if item is not None), None)
            if previous is not None and previous.x is not None and previous.y is not None:
                distance = hypot(candidate.x - previous.x, candidate.y - previous.y)
                elapsed_frames = max(1, index - (last_accepted_index or 0))
                if distance * config.fps / elapsed_frames > config.max_speed_mps:
                    candidate = None
                else:
                    last_accepted_index = index
        elif candidate is not None:
            last_accepted_index = index
        accepted.append(candidate)

    result: list[BallObservation] = [
        item if item is not None else BallObservation(None, None, "lost", 0.0)
        for item in accepted
    ]
    index = 0
    while index < len(result):
        if result[index].state != "lost":
            index += 1
            continue
        start = index - 1
        end = index
        while end < len(result) and result[end].state == "lost":
            end += 1
        gap_length = end - index
        if (
            start >= 0
            and end < len(result)
            and gap_length <= config.max_gap_frames
            and result[start].x is not None
            and result[start].y is not None
            and result[end].x is not None
            and result[end].y is not None
        ):
            start_observation = result[start]
            end_observation = result[end]
            for offset in range(1, gap_length + 1):
                progress = offset / (gap_length + 1)
                result[start + offset] = BallObservation(
                    start_observation.x + (end_observation.x - start_observation.x) * progress,
                    start_observation.y + (end_observation.y - start_observation.y) * progress,
                    "interpolated",
                    min(start_observation.confidence, end_observation.confidence) * 0.5,
                )
        index = end
    return tuple(result)
