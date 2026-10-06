"""Stick mapping. Deflection sets speed. The right trigger raises the top speed."""

from spot.movement import (
    ABSOLUTE_MAX_FORWARD,
    ABSOLUTE_MAX_LATERAL,
    ABSOLUTE_MAX_ROTATION,
    BOOST_MAX_FORWARD,
    BOOST_MAX_LATERAL,
    BOOST_MAX_ROTATION,
)


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


def command_from_sticks(left, right, movement, deadzone, trigger=0.0):
    """Return (forward, lateral, rotation) in the Spot body frame.

    left/right are (x, y) with +x right and +y up, already normalized to -1..1.
    Speed follows how far each stick is pushed. trigger 0 keeps the normal cap.
    trigger 1 raises that cap to the boost limit.
    """
    trigger = max(0.0, min(1.0, float(trigger)))
    forward = _scaled(left[1], deadzone, movement["max_forward_speed"], ABSOLUTE_MAX_FORWARD, BOOST_MAX_FORWARD, trigger)
    lateral = -_scaled(left[0], deadzone, movement["max_lateral_speed"], ABSOLUTE_MAX_LATERAL, BOOST_MAX_LATERAL, trigger)
    rotation = -_scaled(right[0], deadzone, movement["max_rotation_speed"], ABSOLUTE_MAX_ROTATION, BOOST_MAX_ROTATION, trigger)
    return (forward, lateral, rotation)


def _scaled(stick, deadzone, configured, normal_cap, boost_cap, trigger):
    base = min(abs(float(configured)), float(normal_cap))
    if normal_cap <= 0:
        return 0.0
    multiplier = 1.0 + trigger * ((float(boost_cap) / float(normal_cap)) - 1.0)
    speed = _shape(stick, deadzone) * base * multiplier
    limit = float(normal_cap) + (float(boost_cap) - float(normal_cap)) * trigger
    if speed > limit:
        return limit
    if speed < -limit:
        return -limit
    return speed
