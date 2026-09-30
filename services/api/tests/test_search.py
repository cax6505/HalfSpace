import pytest
from pydantic import ValidationError

from app.search import _filter_sql, _rrf
from app.search_models import SearchFilters, ZoneFilter


def row(sequence_id, score=0.5):
    return {"id": sequence_id, "match_id": 1, "possession_id": sequence_id, "phase_index": 0, "tag": "build-up", "tokens": [], "score": score}


def test_zone_grid_bounds_are_validated():
    assert ZoneFilter(x_min=2, x_max=5, y_min=1, y_max=6).x_max == 5
    with pytest.raises(ValidationError):
        ZoneFilter(x_min=6, x_max=5)


def test_rrf_fuses_deduplicates_and_preserves_source_lists():
    result = _rrf([row(1), row(2)], [row(2), row(3)])
    assert [item["id"] for item in result] == [2, 1, 3]
    assert result[0]["sources"] == ["vector", "fts"]
    assert result[0]["score"] > result[1]["score"]


def test_filter_sql_uses_bound_values_for_metadata():
    filters = SearchFilters(phase="build-up", team="Arsenal", competition="2", outcome="Complete")
    sql, params = _filter_sql(filters)
    assert "lower(s.tag) = lower(:phase)" in sql
    assert "t.name ILIKE :team" in sql
    assert params["competition_id"] == 2
    assert params["team"] == "%Arsenal%"


def test_named_competition_uses_bound_search_string():
    sql, params = _filter_sql(SearchFilters(competition="Premier League"))
    assert "c.name ILIKE :competition_name" in sql
    assert params["competition_name"] == "%Premier League%"
