"""Typed domain models for normalized sequence tokens."""
from pydantic import BaseModel, Field


class SequenceToken(BaseModel):
    event_type: str
    zone: tuple[int, int] = Field(description="x/y cell on a 12 by 8 pitch grid")
    outcome: str
    time_delta: float = Field(ge=0)
    event_id: str | None = None
    location: tuple[float, float] | None = None
    end_location: tuple[float, float] | None = None
    player_id: int | None = None
    team_id: int | None = None
    possession_team_id: int | None = None
    attacking_right: bool | None = None


class SequenceRecord(BaseModel):
    match_id: int
    possession_id: int
    phase_index: int = Field(ge=0)
    tag: str
    tokens: list[SequenceToken]
