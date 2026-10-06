"""Velocity limits and the Spot body-frame command.

Spot's body frame, from the Boston Dynamics SDK:
  +v_x  forward
  +v_y  left
  +v_rot  turn left (counter-clockwise)

Configured speeds are capped again by absolute limits so a bad config value
cannot command a fast trailer tow.
"""

ABSOLUTE_MAX_FORWARD = 0.6
ABSOLUTE_MAX_LATERAL = 0.4
ABSOLUTE_MAX_ROTATION = 0.6
BOOST_MAX_FORWARD = 1.2
BOOST_MAX_LATERAL = 0.8
BOOST_MAX_ROTATION = 1.2
# Spot rejects a command whose end time has already passed when it arrives.
# On the robot Wi-Fi that trip can take longer than the 0.4 s refresh window.
COMMAND_LIFETIME_SEC = 2.0


def clamp_velocity(forward, lateral, rotation):
    return (
        _clamp(forward, BOOST_MAX_FORWARD),
        _clamp(lateral, BOOST_MAX_LATERAL),
        _clamp(rotation, BOOST_MAX_ROTATION),
    )


def _clamp(value, limit):
    value = float(value)
    if value > limit:
        return limit
    if value < -limit:
        return -limit
    return value


def send_velocity(command_client, forward, lateral, rotation, duration_sec, timesync_endpoint=None):
    """Send one velocity command. The caller must keep refreshing it."""
    import time

    from bosdyn.client.robot_command import RobotCommandBuilder

    forward, lateral, rotation = clamp_velocity(forward, lateral, rotation)
    command = RobotCommandBuilder.synchro_velocity_command(
        v_x=forward,
        v_y=lateral,
        v_rot=rotation,
    )
    lifetime = max(float(duration_sec), COMMAND_LIFETIME_SEC)
    end_time = time.time() + lifetime
    command_client.robot_command(
        command,
        end_time_secs=end_time,
        timesync_endpoint=timesync_endpoint,
    )
    return (forward, lateral, rotation)


def stand(command_client, timeout_sec=10):
    from bosdyn.client.robot_command import blocking_stand

    blocking_stand(command_client, timeout_sec=timeout_sec)


def sit(command_client, timeout_sec=10):
    from bosdyn.client.robot_command import blocking_sit

    blocking_sit(command_client, timeout_sec=timeout_sec)
