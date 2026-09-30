from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScoutQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["sql", "search_sequences", "xt", "passing_network", "pitch_control", "set_piece_summary"]
    question: str = Field(min_length=3, max_length=500)
    team: str | None = None
    match_id: int | None = Field(default=None, gt=0)
    sequence_id: int | None = Field(default=None, gt=0)
    limit: int = Field(default=10, ge=1, le=50)


class ScoutPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questions: list[ScoutQuestion] = Field(min_length=3, max_length=8)


class NumericCheck(BaseModel):
    metric: str
    value: float


class DossierClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=5, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1)
    checks: list[NumericCheck] = Field(default_factory=list)


class TacticalDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overview: DossierClaim
    claims: list[DossierClaim] = Field(min_length=1, max_length=20)


class Critique(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_more_evidence: bool
    followup_questions: list[ScoutQuestion] = Field(default_factory=list, max_length=4)
    concerns: list[str] = Field(default_factory=list, max_length=8)


class ScoutRequest(BaseModel):
    team: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=3, max_length=1000)
    stream: bool = True
