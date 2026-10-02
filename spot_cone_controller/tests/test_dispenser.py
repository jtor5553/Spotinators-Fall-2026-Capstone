from core.state import DispenserState
from dispenser.dispenser import Dispenser, HoldToDrop
from dispenser.mock_motor import MockMotor
from dispenser.sensors import LimitSwitches
from tests.conftest import make_controller


def _dispenser(timeout, duration, immediate=False):
    motor = MockMotor()
    dispenser = Dispenser(
        motor,
        LimitSwitches(False, None, None),
        {
            "cone_capacity": 4,
            "motor_timeout_sec": timeout,
            "drop_duration_sec": duration,
            "reverse_duration_sec": 0.5,
            "home_duration_sec": 1.0,
        },
        enabled=True,
        immediate=immediate,
    )
    dispenser.initialize()
    return dispenser, motor


def test_hold_requires_half_second_and_one_cone_per_press():
    hold = HoldToDrop(0.5)
    assert hold.update(True, 0.0) is False
    assert hold.update(True, 0.49) is False
    assert hold.update(True, 0.5) is True
    assert hold.update(True, 5.0) is False
    assert hold.update(False, 5.1) is False
    assert hold.update(True, 5.2) is False
    assert hold.update(True, 5.7) is True


def test_successful_drop_decrements_once():
    dispenser, motor = _dispenser(3.0, 1.5, immediate=True)
    assert dispenser.drop_cone() == "done"
    assert dispenser.cones_remaining == 3
    assert motor.running is False


def test_failed_drop_does_not_decrement():
    dispenser, _motor = _dispenser(3.0, 1.5, immediate=True)
    dispenser.cones_remaining = 0
    assert dispenser.drop_cone() is None
    assert dispenser.cones_remaining == 0


def test_motor_timeout_counts_as_failure():
    dispenser, motor = _dispenser(0.2, 5.0, immediate=False)
    assert dispenser.drop_cone() == "started"
    assert dispenser.poll(dispenser._started + 0.2) == "timeout"
    assert dispenser.state == DispenserState.FAULT
    assert motor.running is False
    assert dispenser.cones_remaining == 4


def test_limit_switches_are_optional():
    switches = LimitSwitches(False, None, None)
    assert switches.home_switch_active() is False
    assert switches.end_switch_active() is False
    dispenser, motor = _dispenser(3.0, 1.0, immediate=True)
    dispenser.switches = LimitSwitches(True, None, None)
    dispenser.initialize()
    assert dispenser.state == DispenserState.FAULT
    assert motor.running is False


def test_gui_path_drops_while_robot_is_not_driving(tmp_path):
    app = make_controller(tmp_path)
    app.startup()
    app.set_gui_drop_hold(True, 1.0)
    app.tick(1.0)
    app.set_gui_drop_hold(True, 1.4)
    app.tick(1.4)
    assert app.dispenser.cones_remaining == 4
    app.set_gui_drop_hold(True, 1.5)
    app.tick(1.5)
    assert app.dispenser.cones_remaining == 3
