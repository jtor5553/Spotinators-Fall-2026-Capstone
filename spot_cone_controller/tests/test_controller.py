from controller.mappings import command_from_sticks
from tests.conftest import make_controller

LIMITS = {
    "max_forward_speed": 0.3,
    "max_lateral_speed": 0.2,
    "max_rotation_speed": 0.3,
}


def test_deadman_blocks_sticks():
    command = command_from_sticks((0.0, 1.0), (0.0, 0.0), 0.0, LIMITS, 0.12, 0.2)
    assert command == (0.0, 0.0, 0.0)


def test_forward_strafe_and_turn_directions():
    forward = command_from_sticks((0.0, 1.0), (0.0, 0.0), 1.0, LIMITS, 0.12, 0.2)
    strafe_right = command_from_sticks((1.0, 0.0), (0.0, 0.0), 1.0, LIMITS, 0.12, 0.2)
    turn_right = command_from_sticks((0.0, 0.0), (1.0, 0.0), 1.0, LIMITS, 0.12, 0.2)
    assert forward[0] == 0.3
    assert strafe_right[1] == -0.2
    assert turn_right[2] == -0.3


def test_absolute_speed_cap(tmp_path):
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
    assert app.spot.velocity[0] == 0.6


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
