import pytest
from backend.classifier import classify
from backend.config import SLOUCH_THRESHOLD, LATERAL_THRESHOLD


def test_good_posture():
    assert classify(0.0, 0.0) == "good"


def test_slouching_forward():
    assert classify(SLOUCH_THRESHOLD + 1, 0.0) == "slouching_forward"


def test_hyperextended():
    assert classify(-(SLOUCH_THRESHOLD + 1), 0.0) == "hyperextended"


def test_leaning_right():
    assert classify(0.0, LATERAL_THRESHOLD + 1) == "leaning_right"


def test_leaning_left():
    assert classify(0.0, -(LATERAL_THRESHOLD + 1)) == "leaning_left"


def test_at_threshold_boundary_is_good():
    # > not >= means exactly at threshold is still good
    assert classify(SLOUCH_THRESHOLD, 0.0) == "good"
    assert classify(0.0, LATERAL_THRESHOLD) == "good"


def test_pitch_checked_before_roll():
    # slouch takes priority when both exceed thresholds
    assert classify(SLOUCH_THRESHOLD + 1, LATERAL_THRESHOLD + 1) == "slouching_forward"
