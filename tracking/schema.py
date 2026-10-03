from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

BallState = Literal["tracked", "interpolated", "lost"]
PlayerRole = Literal["player", "goalkeeper", "referee", "official", "unknown"]


@dataclass(frozen=True)
class TeamMetadata:
    id: str
    name: str
    side: Literal["home", "away"]
    primary_color: str
    secondary_color: str | None = None


@dataclass(frozen=True)
class ClipMetadata:
    id: str
    source: Literal["broadcast", "sample"]
    title: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_ms: int
    teams: tuple[TeamMetadata, ...] = ()

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError("clip fps must be positive")
        if self.frame_count < 1:
            raise ValueError("clip frame_count must be positive")
        if self.width < 1 or self.height < 1:
            raise ValueError("clip dimensions must be positive")
        if self.duration_ms < 0:
            raise ValueError("clip duration must not be negative")
        if len(self.teams) > 2:
            raise ValueError("a clip can contain at most home and away teams")
        if len({team.side for team in self.teams}) != len(self.teams):
            raise ValueError("team sides must be unique")


@dataclass(frozen=True)
class PlayerTrack:
    """A player location in calibrated pitch metres, not image pixels."""

    track_id: str
    x: float | None
    y: float | None
    team_id: str | None
    role: PlayerRole = "unknown"
    confidence: float = 0.0
    visible: bool = True

    def __post_init__(self) -> None:
        if not self.track_id:
            raise ValueError("player track_id must not be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("player confidence must be between 0 and 1")
        if self.visible and (self.x is None or self.y is None):
            raise ValueError("visible players require pitch coordinates")


@dataclass(frozen=True)
class BallObservation:
    """A ball location in calibrated pitch metres."""

    x: float | None
    y: float | None
    state: BallState
    confidence: float = 0.0
    z_m: float | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("ball confidence must be between 0 and 1")
        if self.state == "lost" and (self.x is not None or self.y is not None):
            raise ValueError("lost ball observations must not draw coordinates")
        if self.state != "lost" and (self.x is None or self.y is None):
            raise ValueError("tracked or interpolated ball observations require coordinates")


@dataclass(frozen=True)
class TrackingFrame:
    frame_index: int
    timestamp_ms: int
    players: tuple[PlayerTrack, ...]
    ball: BallObservation
    homography_confidence: float | None = None

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index must not be negative")
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must not be negative")
        if self.homography_confidence is not None and not 0 <= self.homography_confidence <= 1:
            raise ValueError("homography confidence must be between 0 and 1")


@dataclass(frozen=True)
class EvaluationAnnotations:
    ball: tuple[BallObservation, ...] = ()
    player_positions: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class TrackingArtifact:
    metadata: ClipMetadata
    frames: tuple[TrackingFrame, ...]
    annotations: EvaluationAnnotations | None = None
    schema_version: str = "tracking/v1"

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("tracking artifact must contain at least one frame")
        if self.frames[-1].frame_index >= self.metadata.frame_count:
            raise ValueError("frame index exceeds clip metadata")
        for frame in self.frames:
            validate_frame(frame, self.metadata)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_frame(frame: TrackingFrame, metadata: ClipMetadata) -> None:
    """Validate team and role constraints without inventing missing tracks."""
    team_ids = {team.id for team in metadata.teams}
    visible_by_team: dict[str, int] = {}
    goalkeepers_by_team: dict[str, int] = {}

    for player in frame.players:
        if player.team_id is not None and player.team_id not in team_ids:
            raise ValueError(f"unknown team_id for track {player.track_id}: {player.team_id}")
        if player.team_id is None or player.role in {"referee", "official", "unknown"}:
            continue
        visible_by_team[player.team_id] = visible_by_team.get(player.team_id, 0) + int(player.visible)
        goalkeepers_by_team[player.team_id] = goalkeepers_by_team.get(player.team_id, 0) + int(player.role == "goalkeeper")

    overfull = [team_id for team_id, count in visible_by_team.items() if count > 11]
    if overfull:
        raise ValueError(f"more than 11 visible players for team(s): {', '.join(sorted(overfull))}")
    over_goalkeepers = [team_id for team_id, count in goalkeepers_by_team.items() if count > 2]
    if over_goalkeepers:
        raise ValueError(f"more than 2 goalkeepers for team(s): {', '.join(sorted(over_goalkeepers))}")
