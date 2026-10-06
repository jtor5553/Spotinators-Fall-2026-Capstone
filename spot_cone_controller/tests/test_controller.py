from controller.mappings import command_from_sticks
from tests.conftest import make_controller

LIMITS = {
    "max_forward_speed": 0.6,
    "max_lateral_speed": 0.4,
    "max_rotation_speed": 0.6,
}


def test_full_stick_walks_with_trigger_released():
    command = command_from_sticks((0.0, 1.0), (0.0, 0.0), LIMITS, 0.12)
    assert command[0] == 0.6


def test_half_push_is_half_speed():
    full = command_from_sticks((0.0, 1.0), (0.0, 0.0), LIMITS, 0.0)
    half = command_from_sticks((0.0, 0.5), (0.0, 0.0), LIMITS, 0.0)
    assert full[0] == 0.6
    assert half[0] == 0.3


def test_forward_strafe_and_turn_directions():
    forward = command_from_sticks((0.0, 1.0), (0.0, 0.0), LIMITS, 0.12)
    strafe_right = command_from_sticks((1.0, 0.0), (0.0, 0.0), LIMITS, 0.12)
    turn_right = command_from_sticks((0.0, 0.0), (1.0, 0.0), LIMITS, 0.12)
    assert forward[0] == 0.6
    assert strafe_right[1] == -0.4
    assert turn_right[2] == -0.6


def test_absolute_speed_cap(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.config["movement"]["max_forward_speed"] = 5
    app.connect_spot("10.0.0.8", "op", "pw")
    app.stand()
    app.arm()
    app.gamepad.set_connected(True)
    app.gamepad.set_r2(0.0)
    app.gamepad.set_left(0.0, 1.0)
    app.tick(1.0)
    assert app.spot.velocity[0] == 0.6


def test_right_trigger_raises_the_speed_cap(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.config["movement"]["max_forward_speed"] = 5
    app.connect_spot("10.0.0.8", "op", "pw")
    app.stand()
    app.arm()
    app.gamepad.set_connected(True)
    app.gamepad.set_r2(1.0)
    app.gamepad.set_left(0.0, 1.0)
    app.tick(1.0)
    assert app.spot.velocity[0] == 1.2


def test_rejected_drive_command_does_not_estop(tmp_path):
    app = _driving(tmp_path)

    def reject(*_args, **_kwargs):
        raise RuntimeError("expired")

    app.spot.set_velocity = reject
    app.tick(4.0)
    assert app.state.value != "ESTOP"
    assert app.spot.velocity == (0.0, 0.0, 0.0)


def test_velocity_command_outlasts_wifi_delay():
    import time

    from spot.movement import COMMAND_LIFETIME_SEC, send_velocity

    seen = {}

    class Client:
        def robot_command(self, command, end_time_secs=None, timesync_endpoint=None):
            del command
            seen["end"] = end_time_secs
            seen["sync"] = timesync_endpoint

    before = time.time()
    send_velocity(Client(), 0.1, 0.0, 0.0, 0.4, timesync_endpoint="clock")
    assert seen["sync"] == "clock"
    assert seen["end"] >= before + COMMAND_LIFETIME_SEC


def test_controller_loss_requires_resume(tmp_path):
    app = _driving(tmp_path)
    app.gamepad.set_connected(False)
    app.tick(2.0)
    assert app.state.value == "STOPPED"
    assert app.spot.velocity == (0.0, 0.0, 0.0)
    app.gamepad.set_connected(True)
    app.gamepad.set_r2(1.0)
    app.gamepad.set_left(0.0, 1.0)
    app.tick(3.0)
    assert app.state.value == "STOPPED"
    assert app.spot.velocity == (0.0, 0.0, 0.0)


def test_failed_sit_leaves_posture_so_a_later_stand_can_drive(tmp_path):
    app = _driving(tmp_path)
    app.spot.fail_sit = "Sit was rejected."
    app.spot.motor_error = "motors off"
    ok, message = app.sit()
    assert ok is False
    assert app.spot.posture == "STANDING"
    assert "Sit was rejected." in message
    assert "motors off" in message
    logged = _event_text(app)
    assert any(line.startswith("SIT FAILED") for line in logged)
    assert any("Sit was rejected." in line for line in logged)
    app.spot.motor_error = ""
    assert app.stand()[0] is True
    app.gamepad.set_r2(1.0)
    app.gamepad.set_left(0.0, 1.0)
    app.tick(5.0)
    assert app.spot.velocity[0] > 0


def test_lease_loss_is_logged_and_the_next_stand_reacquires(tmp_path):
    from spot.lease import LeaseManager

    lease = LeaseManager()
    lease._on_failure(RuntimeError("retain failed"))
    assert lease.lost is True
    assert lease.needs_reacquire() is True

    app = _driving(tmp_path)
    assert app.spot.lease.acquires == 1
    app.spot.lease.lost = True
    app.spot.lease.failure = "retain failed"
    app.tick(2.0)
    assert "LEASE LOST" in _event_text(app)
    assert app.stand()[0] is True
    assert app.spot.lease.acquires == 2
    assert app.spot.lease.lost is False
    assert "LEASE REACQUIRED" in _event_text(app)


def test_prepared_session_repowers_and_retries_stand():
    from spot.connection import SpotSession

    session = SpotSession({"camera": {"width": 4, "height": 4}})
    session.connected = True
    session.prepared = True
    session.powered_on = True
    session.motors = "ON"
    session.posture = "SITTING"
    session.robot = object()
    session.command_client = _FaultClient()
    session.lease.keepalive = object()
    powered = []
    session._power_on_motors = lambda: powered.append("on")
    attempts = {"n": 0}

    def issue():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("The robot must be powered on to accept a command.")

    session._issue_stand = issue
    session.stand()
    assert attempts["n"] == 2
    assert powered == ["on"]
    assert session.posture == "STANDING"
    assert session.motors == "ON"


def test_clearable_fault_is_cleared_once_before_the_retried_stand():
    from spot.connection import SpotSession

    session = SpotSession({"camera": {"width": 4, "height": 4}})
    session.connected = True
    session.prepared = True
    session.powered_on = True
    session.motors = "ON"
    session.robot = object()
    client = _FaultClient()
    session.command_client = client
    session.lease.keepalive = object()
    session.behavior_faults = [{"id": 7, "cause": "CAUSE_LEASE_TIMEOUT", "clearable": True}]
    session._power_on_motors = lambda: None
    attempts = {"n": 0}

    def issue():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("The robot may not be commanded with uncleared behavior faults.")

    session._issue_stand = issue
    session.stand()
    assert client.cleared == [7]
    assert attempts["n"] == 2
    assert session.posture == "STANDING"
    assert session.behavior_faults == []


def test_failed_sit_on_the_session_does_not_claim_sitting():
    from spot.connection import SpotSession

    session = SpotSession({"camera": {"width": 4, "height": 4}})
    session.connected = True
    session.prepared = True
    session.powered_on = True
    session.motors = "ON"
    session.posture = "STANDING"
    session.commanded_posture = "STANDING"
    session.robot = object()
    session.command_client = object()
    session.lease.keepalive = object()

    def issue():
        raise RuntimeError("Sit timed out.")

    session._issue_sit = issue
    try:
        session.sit()
    except RuntimeError as exc:
        assert "Sit timed out." in str(exc)
    else:
        raise AssertionError("sit should fail")
    assert session.posture == "STANDING"
    assert session.commanded_posture == "STANDING"


class _FaultClient:
    def __init__(self):
        self.cleared = []

    def clear_behavior_fault(self, fault_id):
        self.cleared.append(fault_id)


def _event_text(app):
    return [item["message"] for item in app.events.recent(40)]


def _driving(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.8", "op", "pw")
    app.stand()
    app.arm()
    app.gamepad.set_connected(True)
    app.gamepad.set_r2(1.0)
    app.gamepad.set_left(0.0, 1.0)
    app.tick(1.0)
    return app
