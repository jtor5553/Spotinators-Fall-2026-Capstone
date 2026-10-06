"""Read battery, motor power, and robot E-stop from a Spot robot-state message."""


def parse_robot_state(state):
    battery = _battery_percent(state)
    motors = _motor_text(state)
    estop_names = _estop_names(state)
    return {
        "battery": battery,
        "motors": motors,
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


def _motor_text(state):
    power = getattr(state, "power_state", None)
    motor_state = getattr(power, "motor_power_state", None)
    name = str(motor_state)
    if "OFF" in name:
        return "OFF"
    if "ON" in name:
        return "ON"
    return "UNKNOWN"


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
