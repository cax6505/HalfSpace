from tracking.sample import build_sample_artifact


def test_sample_artifact_is_labeled_and_respects_lineup_limits() -> None:
    artifact = build_sample_artifact()

    assert artifact.metadata.source == "sample"
    assert artifact.metadata.title.startswith("Sample data")
    assert all(len([player for player in frame.players if player.team_id == "home"]) == 11 for frame in artifact.frames)
    assert any(frame.ball.state == "lost" for frame in artifact.frames)
    assert any(frame.ball.state == "interpolated" for frame in artifact.frames)
