"""Future autonomy plugs in here. Version 1 does not drive or drop cones."""


class AutonomyManager:
    """Reserved command source. It is not wired to the movement manager."""

    def __init__(self):
        self.mode = "MANUAL"
        self.enabled = False

    def tick(self):
        if self.enabled:
            raise RuntimeError("Autonomous mode is not implemented. Manual control remains required.")
        return None
