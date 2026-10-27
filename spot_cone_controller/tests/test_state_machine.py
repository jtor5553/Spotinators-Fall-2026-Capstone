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
    assert first.state == SystemState.ARMED
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
    assert app.safety.motion_allowed is True
    assert app.state == SystemState.ARMED


def test_routes_exist(tmp_path):
    app = create_app(make_controller(tmp_path))
    paths = {getattr(route, "path", "") for route in app.routes}
    for path in (
        "/api/status",
        "/api/estop",
        "/api/stop",
        "/api/connect",
        "/api/signout",
        "/api/disconnect",
        "/api/pause",
        "/api/camera/frame",
    ):
        assert path in paths
    assert "/api/access" not in paths


def test_cli_mock_flags_are_gone():
    import pytest

    from main import apply_args, parse_args
    from core.config import load_config

    args = parse_args([])
    assert not hasattr(args, "mock")
    assert not hasattr(args, "mock_dispenser")
    assert not hasattr(args, "real")
    assert not hasattr(args, "gamepad")
    config = load_config()
    config["controller"]["mock"] = False
    config["system"]["mock_mode"] = False
    apply_args(config, args)
    assert config["system"]["mock_mode"] is False
    assert config["controller"]["mock"] is False
    with pytest.raises(SystemExit):
        parse_args(["--mock"])
    with pytest.raises(SystemExit):
        parse_args(["--mock-dispenser"])
    with pytest.raises(SystemExit):
        parse_args(["--real"])
    with pytest.raises(SystemExit):
        parse_args(["--gamepad"])


def test_manual_connect_does_not_stand(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    ok, _message = app.connect_spot("10.0.0.4", "op", "pw", mock=True)
    assert ok is True
    assert app.state == SystemState.SPOT_CONNECTED
    assert app.spot.posture != "STANDING"
    assert app.spot.lease.acquires == 0
    refused, message = app.connect_spot("10.0.0.4", "op", "pw", mock=False)
    assert refused is False
    assert "Sign out" in message


def test_mock_connect_enables_mock_dispenser_without_pins(tmp_path):
    from dispenser.mock_motor import MockMotor

    app = make_controller(tmp_path, dispenser_enabled=False)
    app.config["dispenser"]["mock"] = False
    app.config["dispenser"]["dir_pin"] = None
    app.config["dispenser"]["pwm_pin"] = None
    app._dispenser_baseline_enabled = False
    app._dispenser_baseline_mock = False
    app.startup()
    assert app.dispenser.state.value == "DISABLED"
    ok, _message = app.connect_spot("10.0.0.4", "op", "pw", mock=True)
    assert ok is True
    assert app.dispenser.state.value == "READY"
    assert app.dispenser.enabled is True
    assert isinstance(app.dispenser.motor, MockMotor)
    assert app.config["dispenser"]["enabled"] is True
    assert app.config["dispenser"]["mock"] is True


def test_mock_connect_uses_real_motor_when_pins_set(tmp_path, monkeypatch):
    from dispenser.dispenser import build_dispenser
    from dispenser.motor_driver import CytronMDD10A

    monkeypatch.setattr(CytronMDD10A, "initialize", lambda self: None)

    app = make_controller(tmp_path, dispenser_enabled=False)
    app.config["dispenser"]["mock"] = True
    app.config["dispenser"]["dir_pin"] = 13
    app.config["dispenser"]["pwm_pin"] = 32
    app.config["dispenser"]["dir_line"] = 122
    app._dispenser_baseline_enabled = False
    app._dispenser_baseline_mock = True
    app.dispenser = build_dispenser(app.config, verbose=False)
    app.startup()
    ok, _message = app.connect_spot("10.0.0.4", "op", "pw", mock=True)
    assert ok is True
    assert app.config["dispenser"]["mock"] is False
    assert app.config["dispenser"]["enabled"] is True
    assert isinstance(app.dispenser.motor, CytronMDD10A)
    assert app.dispenser.motor.dir_pin == 13
    assert app.dispenser.motor.pwm_pin == 32
    assert app.dispenser.state.value == "READY"


def test_sign_out_releases_the_lease(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.4", "op", "pw", remember=True, mock=True)
    assert app.stand()[0] is True
    assert app.spot.lease.keepalive is True
    ok, _message = app.sign_out()
    assert ok is True
    assert app.spot.connected is False
    assert app.spot.lease.keepalive is None
    assert app.state == SystemState.DISCONNECTED
    assert app.safety.motion_allowed is False


def test_remember_stores_password_and_uncheck_clears_it(tmp_path):
    from pathlib import Path

    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.1.1.5", "ada", "s3cret-value", remember=True, mock=True)
    saved = Path(app.config["_paths"]["operator"]).read_text(encoding="utf-8")
    secret = Path(app.config["_paths"]["operator"]).with_suffix(".secret").read_text(encoding="utf-8")
    assert "s3cret-value" not in saved
    assert secret.strip() == "s3cret-value"
    assert app.config["saved_password"] == "s3cret-value"
    snapshot = app.snapshot()
    assert "saved_password" not in snapshot
    assert snapshot["password_saved"] is True
    assert "s3cret-value" not in str(snapshot)
    logged = " ".join(item["message"] for item in app.events.recent(40))
    assert "s3cret-value" not in logged
    app.sign_out()
    signed_out = app.snapshot()
    assert signed_out["password_saved"] is True
    assert "s3cret-value" not in str(signed_out)
    app.connect_spot("10.1.1.5", "ada", "s3cret-value", remember=False, mock=True)
    assert app.config["saved_password"] == ""
    assert not Path(app.config["_paths"]["operator"]).is_file()
    assert not Path(app.config["_paths"]["operator"]).with_suffix(".secret").is_file()


def test_saved_credentials_stand_and_enable_driving(tmp_path, monkeypatch):
    from core.config import save_operator_identity
    from mocks.mock_spot import MockSpot

    class FakeSession:
        def __init__(self, config):
            self.config = config
            self.connected = False
            self.posture = "UNKNOWN"
            self.prepared = True
            self.lease = type("Lease", (), {"acquires": 0, "keepalive": None, "lost": False})()

            def acquire(robot=None):
                del robot
                self.lease.acquires += 1
                self.lease.keepalive = True
                self.lease.lost = False

            self.lease.acquire = acquire
            self.lease.release = lambda: setattr(self.lease, "keepalive", None)
            self.lease.needs_reacquire = lambda: self.lease.keepalive is None or self.lease.lost

        def connect(self, hostname, username, password):
            del hostname, username, password
            self.connected = True
            return True

        def stand(self):
            self.lease.acquire()
            self.posture = "STANDING"

        def status(self):
            return {"connection": "CONNECTED" if self.connected else "NOT CONNECTED"}

        def list_cameras(self):
            return []

        def stop(self):
            return None

        def disconnect(self, power_off=True):
            del power_off
            self.connected = False
            self.lease.release()

    monkeypatch.setattr("core.app_controller.SpotSession", FakeSession)
    app = make_controller(tmp_path)
    save_operator_identity(app.config, "10.0.0.8", "user2", "secret")
    app.startup()
    assert not isinstance(app.spot, MockSpot)
    assert app.spot.connected is True
    assert app.spot.posture == "STANDING"
    assert app.spot.lease.acquires == 1
    assert app.safety.motion_allowed is True
    assert app.state == SystemState.ARMED


def test_mock_flag_skips_saved_startup(tmp_path):
    from core.config import save_operator_identity

    app = make_controller(tmp_path)
    save_operator_identity(app.config, "10.0.0.8", "user2", "secret")
    app.config["_skip_auto_start"] = True
    app.startup()
    assert app.spot.connected is False
    assert app.state == SystemState.DISCONNECTED
    assert app.safety.motion_allowed is False


def test_startup_without_password_stays_disconnected(tmp_path):
    app = make_controller(tmp_path)
    app.config["spot"]["hostname"] = "10.0.0.8"
    app.config["spot"]["username"] = "user2"
    app.startup()
    assert app.spot.connected is False
    assert app.state == SystemState.DISCONNECTED


def test_mock_scenario_passes():
    assert run_scenario(verbose=False) is True
