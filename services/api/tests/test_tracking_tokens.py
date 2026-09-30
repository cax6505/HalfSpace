from app.ingest import _token


def event(*, team_id: int, possession_team_id: int, period: int = 1):
    return {
        "id": "event-1",
        "period": period,
        "minute": 1,
        "second": 2,
        "location": [101.25, 13.5],
        "team": {"id": team_id},
        "possession_team": {"id": possession_team_id},
        "player": {"id": 42},
        "_home_team_id": 1,
        "type": {"name": "Pass"},
        "pass": {"end_location": [113.75, 27.25]},
    }


def test_token_keeps_exact_action_coordinates_and_attack_direction():
    token = _token(event(team_id=1, possession_team_id=1), None)
    assert token["location"] == (101.25, 13.5)
    assert token["end_location"] == (113.75, 27.25)
    assert token["attacking_right"] is True
    assert token["possession_team_id"] == 1


def test_away_team_attacks_left_in_first_period_and_right_after_halftime():
    first_half = _token(event(team_id=2, possession_team_id=2), None)
    second_half = _token(event(team_id=2, possession_team_id=2, period=2), None)
    assert first_half["attacking_right"] is False
    assert second_half["attacking_right"] is True
