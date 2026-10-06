from pathlib import Path

from core.config import load_config
from tests.conftest import make_controller

ROOT = Path(__file__).resolve().parents[1]


def test_software_estop_alone_does_not_latch(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.9", "op", "pw")
    app.stand()
    app.spot.estop = True
    app.spot.robot_estop_names = ["software_estop"]
    app.tick(1.0)
    assert app.state.value != "ESTOP"
    assert app.snapshot()["commands"]["stand"] is True


def test_hardware_estop_still_latches(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.9", "op", "pw")
    app.stand()
    app.spot.estop = True
    app.spot.robot_estop_names = ["hardware_estop"]
    app.tick(1.0)
    assert app.state.value == "ESTOP"
    assert app.stand()[0] is False


def test_estop_is_immediate_and_reset_does_not_drive(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.9", "op", "pw")
    app.stand()
    app.arm()
    app.gamepad.set_connected(True)
    app.gamepad.set_r2(1)
    app.gamepad.set_left(0, 1)
    app.tick(1)
    assert app.emergency_stop()[0] is True
    assert app.state.value == "ESTOP"
    assert app.spot.velocity == (0.0, 0.0, 0.0)
    assert app.stand()[0] is False
    assert app.reset_estop()[0] is True
    assert app.state.value == "STOPPED"
    app.tick(2)
    assert app.spot.velocity == (0.0, 0.0, 0.0)


def test_normal_stop_leaves_posture_and_blocks_cones(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.9", "op", "pw")
    app.stand()
    app.normal_stop()
    assert app.spot.posture == "STANDING"
    assert app.state.value == "STOPPED"
    assert app.request_drop()[0] is False
    assert app.dispenser.cones_remaining == 4


def test_watchdog_stops_stale_motion(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.connect_spot("10.0.0.9", "op", "pw")
    app.stand()
    app.arm()
    app.gamepad.set_connected(True)
    app.gamepad.set_r2(1)
    app.gamepad.set_left(0, 1)
    app.tick(5)
    assert app.spot.velocity[0] > 0
    app.watchdog.last_motion_beat = 0
    assert app.watchdog.poll_motion(5) is True
    assert app.spot.velocity == (0.0, 0.0, 0.0)


def test_password_is_not_loaded_from_config(tmp_path):
    path = tmp_path / "secret.yaml"
    path.write_text(
        "system:\n  operator_file: config/no-such-operator.yaml\n"
        "spot:\n  hostname: 10.1.1.1\n  username: ada\n  password: secret\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config["spot"]["hostname"] == "10.1.1.1"
    assert "password" not in config["spot"]
    assert config["_password_in_config"] is True


def test_gui_assets_are_local():
    text = ""
    for relative in ("gui/templates/index.html", "gui/static/app.js", "gui/static/style.css"):
        text += (ROOT / relative).read_text(encoding="utf-8").lower()
    for banned in ("cdn", "googleapis", "unpkg", "jsdelivr", "cloudflare", "are you sure"):
        assert banned not in text


def test_service_restarts_without_resuming_motion():
    text = (ROOT / "deploy" / "spot-cone-controller.service").read_text(encoding="utf-8")
    assert "Restart=on-failure" in text
    assert "KillSignal=SIGTERM" in text
    assert "stand" not in text.lower()
