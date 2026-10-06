from spot.robot_state import motors_are_off, parse_robot_state


class _EStop:
    def __init__(self, name, state):
        self.name = name
        self.state = state


class _RobotState:
    def __init__(self, items):
        self.estop_states = items


def test_not_estopped_endpoints_are_clear():
    state = _RobotState(
        [
            _EStop("hardware_estop", 2),
            _EStop("payload_estop", 2),
            _EStop("software_estop", 2),
        ]
    )
    parsed = parse_robot_state(state)
    assert parsed["robot_estop"] is False
    assert parsed["robot_estop_names"] == []


def test_estopped_endpoint_is_reported():
    state = _RobotState(
        [
            _EStop("hardware_estop", 1),
            _EStop("payload_estop", 2),
        ]
    )
    parsed = parse_robot_state(state)
    assert parsed["robot_estop"] is True
    assert parsed["robot_estop_names"] == ["hardware_estop"]


class _Power:
    def __init__(self, motor_state, message=""):
        self.motor_power_state = motor_state
        self.motor_power_error_message = message


class _Fault:
    def __init__(self, fault_id, cause, status):
        self.behavior_fault_id = fault_id
        self.cause = cause
        self.status = status


class _Faults:
    def __init__(self, faults):
        self.faults = faults


class _PoweredState:
    def __init__(self, motor_state, message="", faults=None):
        self.power_state = _Power(motor_state, message)
        self.behavior_fault_state = _Faults(faults or [])


def test_motor_power_uses_the_enum_not_a_substring():
    assert parse_robot_state(_PoweredState(2))["motors"] == "ON"
    assert parse_robot_state(_PoweredState("MOTOR_POWER_STATE_ON"))["motors"] == "ON"
    assert motors_are_off(parse_robot_state(_PoweredState(1))["motors"]) is True
    assert motors_are_off(parse_robot_state(_PoweredState("MOTOR_POWER_STATE_OFF"))["motors"]) is True
    assert motors_are_off(parse_robot_state(_PoweredState(5))["motors"]) is True
    assert motors_are_off(parse_robot_state(_PoweredState(3))["motors"]) is False
    assert motors_are_off("POWERING_ON") is False
    powered = parse_robot_state(_PoweredState("MOTOR_POWER_STATE_POWERING_ON"))
    assert powered["motors"] == "POWERING_ON"
    assert motors_are_off(powered["motors"]) is False


def test_motor_error_and_lease_timeout_fault_are_reported():
    state = _PoweredState(
        1,
        "motors off",
        [_Fault(9, 3, 1)],
    )
    parsed = parse_robot_state(state)
    assert parsed["motor_error"] == "motors off"
    assert parsed["behavior_faults"] == [
        {"id": 9, "cause": "CAUSE_LEASE_TIMEOUT", "clearable": True}
    ]
