from backend.config import SLOUCH_THRESHOLD, LATERAL_THRESHOLD


def classify(delta_pitch: float, delta_roll: float) -> str:
    """
    Classify posture based on corrected spine angle deltas.

    Args:
        delta_pitch: upper_pitch - lower_pitch (forward/backward flex)
        delta_roll: upper_roll - lower_roll (lateral lean)

    Returns:
        Classification string: "good", "slouching_forward", "hyperextended",
                               "leaning_right", or "leaning_left"
    """
    if delta_pitch > SLOUCH_THRESHOLD:
        return "slouching_forward"
    if delta_pitch < -SLOUCH_THRESHOLD:
        return "hyperextended"
    if delta_roll > LATERAL_THRESHOLD:
        return "leaning_right"
    if delta_roll < -LATERAL_THRESHOLD:
        return "leaning_left"
    return "good"
