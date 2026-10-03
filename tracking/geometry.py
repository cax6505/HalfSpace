from __future__ import annotations

from math import isfinite
from typing import Sequence

Point = tuple[float, float]
Homography = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]


def apply_homography(point: Point, matrix: Homography) -> Point:
    """Project an image point through a 3x3 homography into pitch coordinates."""
    x, y = point
    denominator = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
    if abs(denominator) < 1e-12:
        raise ValueError("homography projection has a zero denominator")
    projected_x = (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]) / denominator
    projected_y = (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]) / denominator
    if not isfinite(projected_x) or not isfinite(projected_y):
        raise ValueError("homography projection produced a non-finite point")
    return projected_x, projected_y


def smooth_positions(
    positions: Sequence[Point | None],
    alpha: float = 0.35,
) -> tuple[Point | None, ...]:
    """Apply causal exponential smoothing while preserving lost observations."""
    if not 0 < alpha <= 1:
        raise ValueError("smoothing alpha must be greater than 0 and at most 1")
    smoothed: list[Point | None] = []
    previous: Point | None = None
    for position in positions:
        if position is None:
            smoothed.append(None)
            continue
        if previous is None:
            previous = position
        else:
            previous = (
                previous[0] + alpha * (position[0] - previous[0]),
                previous[1] + alpha * (position[1] - previous[1]),
            )
        smoothed.append(previous)
    return tuple(smoothed)
