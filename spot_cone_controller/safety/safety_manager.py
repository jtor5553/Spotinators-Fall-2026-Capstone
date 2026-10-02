"""What the operator is allowed to do. The app controller is the only caller."""


class SafetyManager:
    def __init__(self):
        self.motion_allowed = False
        self.cone_allowed = True
        self.estop_latched = False
        self.stop_latched = False

    def arm(self):
        if self.estop_latched or self.stop_latched:
            return False
        self.motion_allowed = True
        self.cone_allowed = True
        return True

    def normal_stop(self):
        self.stop_latched = True
        self.motion_allowed = False
        self.cone_allowed = False

    def emergency_stop(self):
        self.estop_latched = True
        self.stop_latched = True
        self.motion_allowed = False
        self.cone_allowed = False

    def reset_estop(self):
        """Clear the software E-stop latch. Driving stays disabled."""
        self.estop_latched = False
        self.stop_latched = True
        self.motion_allowed = False
        self.cone_allowed = False

    def resume(self):
        """Operator acknowledgement after STOPPED. Does not arm driving."""
        if self.estop_latched:
            return False
        self.stop_latched = False
        self.motion_allowed = False
        self.cone_allowed = True
        return True

    def fault(self):
        self.stop_latched = True
        self.motion_allowed = False
        self.cone_allowed = False

    def on_connected(self):
        self.estop_latched = False
        self.stop_latched = False
        self.motion_allowed = False
        self.cone_allowed = True
