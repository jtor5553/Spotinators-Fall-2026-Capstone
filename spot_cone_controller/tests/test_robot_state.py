from spot.robot_state import parse_robot_state


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
