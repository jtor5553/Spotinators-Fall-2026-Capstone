"""Read battery, motor power, and robot E-stop from a Spot robot-state message."""

# Spot's protobuf enum has deprecated aliases that share these numbers.
_MOTOR_BY_VALUE = {
    0: "UNKNOWN",
    1: "OFF",
    2: "ON",
    3: "POWERING_ON",
    4: "POWERING_OFF",
    5: "ERROR",
}

_MOTOR_BY_NAME = {
    "STATE_UNKNOWN": "UNKNOWN",
    "MOTOR_POWER_STATE_UNKNOWN": "UNKNOWN",
    "STATE_OFF": "OFF",
    "MOTOR_POWER_STATE_OFF": "OFF",
    "STATE_ON": "ON",
    "MOTOR_POWER_STATE_ON": "ON",
    "STATE_POWERING_ON": "POWERING_ON",
    "MOTOR_POWER_STATE_POWERING_ON": "POWERING_ON",
    "STATE_POWERING_OFF": "POWERING_OFF",
    "MOTOR_POWER_STATE_POWERING_OFF": "POWERING_OFF",
    "STATE_ERROR": "ERROR",
    "MOTOR_POWER_STATE_ERROR": "ERROR",
}

_CAUSE_BY_VALUE = {
    0: "CAUSE_UNKNOWN",
    1: "CAUSE_FALL",
    2: "CAUSE_HARDWARE",
    3: "CAUSE_LEASE_TIMEOUT",
    4: "CAUSE_COMMAND_FAILURE",
}

_CLEARABLE_STATUS = 1


def motors_are_off(motors):
    """True when Spot is not supplying motor power and is not in the process of turning it on."""
    return motors in ("OFF", "POWERING_OFF", "ERROR")


def parse_robot_state(state):
    battery = _battery_percent(state)
    motors, motor_error = _motor_status(state)
    estop_names = _estop_names(state)
    return {
        "battery": battery,
        "motors": motors,
        "motor_error": motor_error,
        "behavior_faults": _behavior_faults(state),
        "robot_estop": bool(estop_names),
        "robot_estop_names": estop_names,
    }


def _battery_percent(state):
    power = getattr(state, "power_state", None)
    if power is not None:
        charge = getattr(power, "locomotion_charge_percentage", None)
        value = getattr(charge, "value", None)
        if value:
            return int(round(float(value)))
    batteries = getattr(state, "battery_states", None) or []
    if batteries:
        charge = getattr(batteries[0], "charge_percentage", None)
        value = getattr(charge, "value", None)
        if value is not None:
            return int(round(float(value)))
    return None


def _motor_status(state):
    power = getattr(state, "power_state", None)
    if power is None:
        return "UNKNOWN", ""
    label = motor_power_label(getattr(power, "motor_power_state", None))
    message = str(getattr(power, "motor_power_error_message", "") or "")
    return label, message


def motor_power_label(motor_state):
    if motor_state is None:
        return "UNKNOWN"
    if isinstance(motor_state, str) and not motor_state.isdigit():
        return _MOTOR_BY_NAME.get(motor_state.strip().upper(), "UNKNOWN")
    try:
        number = int(motor_state)
    except (TypeError, ValueError):
        return _MOTOR_BY_NAME.get(str(motor_state).strip().upper(), "UNKNOWN")
    name = _sdk_motor_name(number)
    if name in _MOTOR_BY_NAME:
        return _MOTOR_BY_NAME[name]
    return _MOTOR_BY_VALUE.get(number, "UNKNOWN")


def _sdk_motor_name(number):
    try:
        from bosdyn.api.robot_state_pb2 import PowerState

        return PowerState.MotorPowerState.Name(number)
    except Exception:
        return ""


def _behavior_faults(state):
    fault_state = getattr(state, "behavior_fault_state", None)
    faults = getattr(fault_state, "faults", None) or []
    parsed = []
    for fault in faults:
        status = getattr(fault, "status", None)
        parsed.append(
            {
                "id": getattr(fault, "behavior_fault_id", None),
                "cause": _cause_label(getattr(fault, "cause", None)),
                "clearable": _is_clearable(status),
            }
        )
    return parsed


def _cause_label(cause):
    if cause is None:
        return "CAUSE_UNKNOWN"
    if isinstance(cause, str) and not cause.isdigit():
        text = cause.strip().upper()
        return text or "CAUSE_UNKNOWN"
    try:
        number = int(cause)
    except (TypeError, ValueError):
        return str(cause)
    name = _sdk_cause_name(number)
    if name:
        return name
    return _CAUSE_BY_VALUE.get(number, "CAUSE_UNKNOWN")


def _sdk_cause_name(number):
    try:
        from bosdyn.api.robot_state_pb2 import BehaviorFault

        return BehaviorFault.Cause.Name(number)
    except Exception:
        return ""


def _is_clearable(status):
    if status is None:
        return False
    if isinstance(status, str) and not status.isdigit():
        name = status.strip().upper()
        if "UNCLEARABLE" in name:
            return False
        return "CLEARABLE" in name
    try:
        return int(status) == _CLEARABLE_STATUS
    except (TypeError, ValueError):
        return False


def _estop_names(state):
    names = []
    stopped = _stopped_level()
    for estop_state in getattr(state, "estop_states", None) or []:
        level = getattr(estop_state, "state", stopped)
        if level == stopped:
            names.append(str(getattr(estop_state, "name", "estop")))
    return names


def _stopped_level():
    try:
        from bosdyn.api.robot_state_pb2 import EStopState

        return EStopState.STATE_ESTOPPED
    except Exception:
        return 1
