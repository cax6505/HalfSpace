from tracking.postprocess import BallPostprocessConfig, postprocess_ball
from tracking.schema import BallObservation


def test_short_gap_is_interpolated() -> None:
    output = postprocess_ball(
        (
            BallObservation(0, 0, "tracked", 1),
            BallObservation(None, None, "lost"),
            BallObservation(0.8, 0, "tracked", 1),
        ),
        BallPostprocessConfig(fps=25, max_gap_frames=2, max_speed_mps=38),
    )
    assert output[1].state == "interpolated"
    assert output[1].x == 0.4


def test_long_gap_remains_lost() -> None:
    output = postprocess_ball(
        (
            BallObservation(0, 0, "tracked", 1),
            BallObservation(None, None, "lost"),
            BallObservation(None, None, "lost"),
            BallObservation(None, None, "lost"),
            BallObservation(2, 0, "tracked", 1),
        ),
        BallPostprocessConfig(fps=25, max_gap_frames=2, max_speed_mps=38),
    )
    assert [item.state for item in output] == ["tracked", "lost", "lost", "lost", "tracked"]


def test_impossible_jump_is_rejected() -> None:
    output = postprocess_ball(
        (BallObservation(0, 0, "tracked", 1), BallObservation(10, 0, "tracked", 1)),
        BallPostprocessConfig(fps=25, max_gap_frames=0, max_speed_mps=38),
    )
    assert output[1].state == "lost"
