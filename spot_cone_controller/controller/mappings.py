"""PS5 stick mapping. Sticks do nothing unless R2 is held."""

from spot.movement import clamp_velocity


def _shape(value, deadzone):
    value = float(value)
    deadzone = float(deadzone)
    if abs(value) <= deadzone:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    span = 1.0 - deadzone
    if span <= 0:
        return 0.0
    return sign * min(1.0, (abs(value) - deadzone) / span)


def command_from_sticks(left, right, r2, movement, deadzone, r2_threshold):
    """Return (forward, lateral, rotation) in the Spot body frame.

    left/right are (x, y) with +x right and +y up, already normalized to -1..1.
    """
    if float(r2) < float(r2_threshold):
        return (0.0, 0.0, 0.0)
    forward = _shape(left[1], deadzone) * float(movement["max_forward_speed"])
    lateral = -_shape(left[0], deadzone) * float(movement["max_lateral_speed"])
    rotation = -_shape(right[0], deadzone) * float(movement["max_rotation_speed"])
    return clamp_velocity(forward, lateral, rotation)
