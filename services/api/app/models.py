"""Typed domain models for normalized sequence tokens."""
from pydantic import BaseModel, Field


class SequenceToken(BaseModel):
    event_type: str
    zone: tuple[int, int] = Field(description="x/y cell on a 12 by 8 pitch grid")
    outcome: str
    time_delta: float = Field(ge=0)


class SequenceRecord(BaseModel):
    match_id: int
    possession_id: int
    phase_index: int = Field(ge=0)
    tag: str
    tokens: list[SequenceToken]
