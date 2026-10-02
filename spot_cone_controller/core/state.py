"""Single system state. Hardware modules do not choose these transitions."""

from enum import Enum


class SystemState(Enum):
    BOOTING = "BOOTING"
    DISCONNECTED = "DISCONNECTED"
    SPOT_CONNECTED = "SPOT_CONNECTED"
    CONTROL_READY = "CONTROL_READY"
    ARMED = "ARMED"
    MANUAL_OPERATION = "MANUAL_OPERATION"
    STOPPED = "STOPPED"
    FAULT = "FAULT"
    ESTOP = "ESTOP"


class DispenserState(Enum):
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"
    HOMING = "HOMING"
    READY = "READY"
    DROPPING = "DROPPING"
    REVERSING = "REVERSING"
    FAULT = "FAULT"
