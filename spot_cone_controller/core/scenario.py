"""Mock walkthrough of the manual system. No robot, radio, or motor is used."""

import tempfile

from core.app_controller import AppController
from core.config import load_config
from core.state import DispenserState, SystemState
from dispenser.dispenser import Dispenser
from dispenser.mock_motor import MockMotor
from dispenser.sensors import LimitSwitches


def run_scenario(verbose=False):
    checks = []

    def check(name, condition):
        checks.append((name, bool(condition)))
        if verbose:
            print(("[PASS] " if condition else "[FAIL] ") + name)

    config = load_config()
    config["system"]["mock_mode"] = True
    config["controller"]["mock"] = True
    config["dispenser"]["enabled"] = True
    config["dispenser"]["mock"] = True
    config["logging"]["to_console"] = False
    config["logging"]["directory"] = tempfile.mkdtemp(prefix="spot-cone-")
    config["_paths"]["operator"] = config["logging"]["directory"] + "/operator.yaml"
    app = AppController(config, verbose=verbose)
    app.startup()

    check(
        "startup is disarmed and the motor is off",
        app.state == SystemState.DISCONNECTED
        and not app.safety.motion_allowed
        and not app.dispenser.motor.running,
    )
    ok, _message = app.connect_spot("192.0.2.20", "operator", "not-stored")
    check("mock Spot connects and reports battery", ok and app.snapshot()["spot"]["battery"] == 84)
    check("stand", app.stand()[0] and app.spot.posture == "STANDING")
    check("sit", app.sit()[0] and app.spot.posture == "SITTING")
    check("stand again for driving", app.stand()[0])
    check("enable driving", app.arm()[0] and app.state == SystemState.ARMED)

    app.gamepad.set_connected(True)
    app.gamepad.set_left(0.0, 1.0)
    app.gamepad.set_r2(0.0)
    app.tick(1.0)
    check("stick without R2 does not move", app.spot.velocity == (0.0, 0.0, 0.0))
    app.gamepad.set_r2(1.0)
    app.tick(1.2)
    check("R2 plus forward stick moves slowly", app.spot.velocity[0] > 0 and app.spot.velocity[0] <= 0.6)
    app.gamepad.set_r2(0.0)
    app.tick(1.4)
    check("releasing R2 stops immediately", app.spot.velocity == (0.0, 0.0, 0.0))

    app.gamepad.set_r2(1.0)
    app.tick(1.6)
    app.gamepad.set_connected(False)
    app.tick(1.8)
    check(
        "controller loss stops the robot and blocks cones",
        app.state == SystemState.STOPPED and app.spot.velocity == (0.0, 0.0, 0.0) and not app.safety.cone_allowed,
    )
    app.gamepad.set_connected(True)
    app.gamepad.set_r2(1.0)
    app.gamepad.set_left(0.0, 1.0)
    app.tick(2.0)
    check("reconnect does not resume motion", app.state == SystemState.STOPPED and app.spot.velocity == (0.0, 0.0, 0.0))

    check("resume does not arm driving", app.resume()[0] and not app.safety.motion_allowed)
    app.gamepad.set_button("x", True)
    app.tick(3.0)
    app.tick(3.4)
    check("short X press does not drop a cone", app.dispenser.cones_remaining == 4)
    app.tick(3.5)
    check("half-second X press drops one cone", app.dispenser.cones_remaining == 3)
    app.tick(8.0)
    check("holding X does not drop another cone", app.dispenser.cones_remaining == 3)
    app.gamepad.set_button("x", False)
    app.tick(8.2)
    app.gamepad.set_button("x", True)
    app.tick(8.2)
    app.tick(8.7)
    check("X must be released before the next cone", app.dispenser.cones_remaining == 2)

    check("normal stop", app.normal_stop()[0] and app.state == SystemState.STOPPED)
    before = app.dispenser.cones_remaining
    app.gamepad.set_button("x", False)
    app.tick(9.0)
    app.gamepad.set_button("x", True)
    app.tick(9.0)
    app.tick(9.6)
    check("stop disables cone drop", app.dispenser.cones_remaining == before)

    check("emergency stop blocks stand", app.emergency_stop()[0] and app.state == SystemState.ESTOP and not app.stand()[0])
    check("reset leaves driving disabled", app.reset_estop()[0] and app.state == SystemState.STOPPED)
    app.gamepad.set_r2(1.0)
    app.tick(11.0)
    check("motion stays off after E-stop reset", app.spot.velocity == (0.0, 0.0, 0.0))

    frame = app.camera_frame()
    check("one camera frame is produced", frame is not None and frame.startswith(b"\x89PNG"))
    messages = [item["message"] for item in app.events.recent(80)]
    check(
        "important events are logged",
        "SYSTEM START" in messages and "SPOT CONNECTED" in messages and "CONE DROP COMPLETE" in messages and "EMERGENCY STOP" in messages,
    )

    motor = MockMotor()
    timed = Dispenser(
        motor,
        LimitSwitches(False, None, None),
        {
            "cone_capacity": 4,
            "motor_timeout_sec": 0.2,
            "drop_duration_sec": 5.0,
            "reverse_duration_sec": 0.5,
            "home_duration_sec": 1.0,
        },
        enabled=True,
        immediate=False,
    )
    timed.initialize()
    timed.drop_cone()
    timed.poll(timed._started + 0.2)
    check(
        "motor timeout turns the motor off without counting a cone",
        timed.state == DispenserState.FAULT and not motor.running and timed.cones_remaining == 4,
    )

    app.shutdown()
    check("shutdown leaves the motor off", not app.dispenser.motor.running and app.spot.velocity == (0.0, 0.0, 0.0))
    if verbose:
        failed = [name for name, passed in checks if not passed]
        print(f"{len(checks) - len(failed)} / {len(checks)} checks passed")
    return all(passed for _name, passed in checks)
