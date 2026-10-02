"""Project errors. GUI and logs use the message text; they must not include secrets."""


class SpotConnectionError(Exception):
    """Spot could not be reached, authenticated, or commanded."""


class SafetyError(Exception):
    """A command was rejected because the robot is not in a safe state."""


class MotorNotConfigured(Exception):
    """The dispenser motor cannot run because pins or hardware are not set."""


class SensorError(Exception):
    """A limit-switch read failed."""
