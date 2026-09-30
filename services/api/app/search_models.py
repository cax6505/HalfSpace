"""Validated wire and intent schemas for the sequence search endpoint."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ZoneFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x_min: int = Field(ge=0, le=11)
    x_max: int = Field(ge=0, le=11)
    y_min: int = Field(default=0, ge=0, le=7)
    y_max: int = Field(default=7, ge=0, le=7)

    @field_validator("x_max")
    @classmethod
    def x_order(cls, value: int, info):
        if "x_min" in info.data and value < info.data["x_min"]:
            raise ValueError("x_max must be greater than or equal to x_min")
        return value

    @field_validator("y_max")
    @classmethod
    def y_order(cls, value: int, info):
        if "y_min" in info.data and value < info.data["y_min"]:
            raise ValueError("y_max must be greater than or equal to y_min")
        return value


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phase: str | None = None
    zone: ZoneFilter | None = None
    trigger: str | None = None
    team: str | None = None
    competition: str | None = None
    outcome: str | None = None


class SearchIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: SearchFilters
    semantic_query: str = Field(min_length=1, max_length=500)
    exemplar_sequence_id: int | None = Field(default=None, gt=0)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)
    stream: bool = True
    filters: SearchFilters | None = None


class SearchHit(BaseModel):
    sequence_id: int
    match_id: int
    possession_id: int
    phase_index: int
    tag: str
    score: float
    tokens: list[dict]
    rerank_score: float | None = None
