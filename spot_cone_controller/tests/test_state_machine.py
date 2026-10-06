from core.scenario import run_scenario
from core.state import SystemState
from gui.server import create_app
from tests.conftest import make_controller


def test_real_connect_uses_default_username(tmp_path):
    app = make_controller(tmp_path)
    app.config["system"]["mock_mode"] = False
    seen = {}

    class FakeSpot:
        def connect(self, hostname, username, password):
            del hostname
            seen["username"] = username
            seen["password"] = password
            return True

        def status(self):
            return {"connection": "CONNECTED"}

        def list_cameras(self):
            return []

    app.spot = FakeSpot()
    refused, message = app.connect_spot("10.0.0.5", "", "")
    assert refused is False
    assert message == "Password is required."
    ok, _message = app.connect_spot("10.0.0.5", "", "secret")
    assert ok is True
    assert seen == {"username": "user2", "password": "secret"}


def test_startup_is_safe(tmp_path):
    app = make_controller(tmp_path, dispenser_enabled=False)
    app.startup()
    assert app.state == SystemState.DISCONNECTED
    assert app.safety.motion_allowed is False
    assert app.dispenser.state.value == "DISABLED"
    assert app.dispenser.motor.running is False


def test_new_process_does_not_resume_old_motion(tmp_path):
    first = make_controller(tmp_path)
    first.startup()
    first.connect_spot("10.0.0.4", "op", "pw")
    first.stand()
    first.arm()
    second = make_controller(tmp_path / "restart")
    second.startup()
    assert second.state == SystemState.DISCONNECTED
    assert second.spot.velocity == (0.0, 0.0, 0.0)
    assert second.safety.motion_allowed is False


def test_estop_blocks_arm_and_resume(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.4", "op", "pw")
    app.stand()
    app.emergency_stop()
    assert app.arm()[0] is False
    assert app.resume()[0] is False
    app.reset_estop()
    assert app.resume()[0] is True
    assert app.safety.motion_allowed is False


def test_routes_exist(tmp_path):
    app = create_app(make_controller(tmp_path))
    paths = {getattr(route, "path", "") for route in app.routes}
    for path in ("/api/status", "/api/estop", "/api/stop", "/api/connect", "/api/camera/frame"):
        assert path in paths


def test_mock_scenario_passes():
    assert run_scenario(verbose=False) is True
