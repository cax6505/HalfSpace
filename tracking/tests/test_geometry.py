import pytest

from tracking.geometry import apply_homography, smooth_positions


def test_identity_homography_preserves_pitch_point() -> None:
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    assert apply_homography((12.5, 7.25), identity) == (12.5, 7.25)


def test_homography_rejects_zero_denominator() -> None:
    with pytest.raises(ValueError, match="zero denominator"):
        apply_homography((1.0, 1.0), ((1, 0, 0), (0, 1, 0), (0, 0, 0)))


def test_smoothing_reduces_single_frame_jump_and_preserves_lost_gap() -> None:
    output = smooth_positions(((0.0, 0.0), (10.0, 0.0), None, (10.0, 0.0)), alpha=0.5)
    assert output == ((0.0, 0.0), (5.0, 0.0), None, (7.5, 0.0))
