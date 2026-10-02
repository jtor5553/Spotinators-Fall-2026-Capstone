"""Named fault reasons. These are displayed and logged; they do not move the robot."""

from enum import Enum


class FaultCode(Enum):
    SPOT_LOST = "SPOT DISCONNECTED"
    CONTROLLER_LOST = "CONTROLLER DISCONNECTED"
    MOTOR_TIMEOUT = "MOTOR TIMEOUT"
    CAMERA = "CAMERA FAILURE"
    SOFTWARE = "SOFTWARE FAULT"
