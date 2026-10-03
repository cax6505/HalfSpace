from tracking.metrics import evaluate_ball, evaluate_player_id_switches
from tracking.schema import (
    BallObservation,
    ClipMetadata,
    PlayerTrack,
    TeamMetadata,
    TrackingArtifact,
    TrackingFrame,
)


def test_ball_metrics_report_tracking_and_error() -> None:
    metrics = evaluate_ball(
        (
            BallObservation(0, 0, "tracked", 1),
            BallObservation(10, 10, "lost", 0),
            BallObservation(20, 20, "interpolated", 0.5),
        ),
        (
            BallObservation(1, 1, "tracked", 1),
            BallObservation(10, 10, "tracked", 1),
            BallObservation(20, 20, "tracked", 1),
        ),
        match_radius_m=2,
    )
    assert metrics.true_positive_frames == 2
    assert metrics.predicted_frames == 2
    assert metrics.recall == 2 / 3
    assert metrics.tracked_percentage == 2 / 3 * 100


def test_player_id_switches_count_role_or_team_changes() -> None:
    metadata = ClipMetadata(
        "clip-1", "sample", "Labeled sample data", 25, 2, 100, 100, 40,
        (TeamMetadata("home", "Home", "home", "#fff"),),
    )
    frames = (
        TrackingFrame(0, 0, (PlayerTrack("p1", 1, 1, "home", "player", 1),), BallObservation(None, None, "lost")),
        TrackingFrame(1, 40, (PlayerTrack("p1", 1, 1, None, "referee", 1),), BallObservation(None, None, "lost")),
    )
    metrics = evaluate_player_id_switches(TrackingArtifact(metadata, frames))
    assert metrics.evaluated_tracks == 1
    assert metrics.id_switches == 1
