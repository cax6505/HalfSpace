import pytest

from tracking.schema import (
    BallObservation,
    ClipMetadata,
    PlayerTrack,
    TeamMetadata,
    TrackingFrame,
    validate_frame,
)


def metadata() -> ClipMetadata:
    return ClipMetadata(
        id="clip-1",
        source="sample",
        title="Labeled sample data",
        fps=25,
        frame_count=10,
        width=1920,
        height=1080,
        duration_ms=400,
        teams=(
            TeamMetadata("home", "Home team", "home", "#f0f0f0"),
            TeamMetadata("away", "Away team", "away", "#202020"),
        ),
    )


def test_lost_ball_has_no_drawable_position() -> None:
    with pytest.raises(ValueError, match="lost ball"):
        BallObservation(10, 10, "lost")


def test_frame_rejects_more_than_eleven_visible_team_players() -> None:
    players = tuple(
        PlayerTrack(f"track-{index}", float(index), 20, "home", "player", 0.9)
        for index in range(12)
    )
    frame = TrackingFrame(0, 0, players, BallObservation(None, None, "lost"))

    with pytest.raises(ValueError, match="more than 11"):
        validate_frame(frame, metadata())


def test_referees_do_not_count_toward_team_limit() -> None:
    players = tuple(
        PlayerTrack(f"track-{index}", float(index), 20, "home", "player", 0.9)
        for index in range(11)
    ) + (PlayerTrack("ref-1", 50, 40, None, "referee", 0.9),)

    validate_frame(TrackingFrame(0, 0, players, BallObservation(None, None, "lost")), metadata())
