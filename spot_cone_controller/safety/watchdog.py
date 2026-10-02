"""Stops motion and the motor when commands are not refreshed.

The motor stop path does not take the application lock. A stuck control loop
can still drop motor power. A frozen entire process cannot; the trailer needs
a physical motor E-stop for that case.
"""

import time


class Watchdog:
    def __init__(self, config, movement_stop, motor):
        self._movement = config["movement"]
        self._dispenser = config["dispenser"]
        self._movement_stop = movement_stop
        self._motor = motor
        self.last_motion_beat = 0.0
        self.motion_active = False
        self.motor_timeout_latched = False

    def beat_motion(self, now):
        self.last_motion_beat = now
        self.motion_active = True

    def clear_motion(self):
        self.motion_active = False

    def poll_motion(self, now):
        if not self.motion_active:
            return False
        limit = float(self._movement.get("watchdog_timeout_sec", 1.0))
        if now - self.last_motion_beat <= limit:
            return False
        self._movement_stop()
        self.motion_active = False
        return True

    def poll_motor(self, now=None):
        now = time.monotonic() if now is None else now
        motor = self._motor
        if not getattr(motor, "running", False):
            return False
        started = getattr(motor, "started_at", 0.0) or 0.0
        limit = float(self._dispenser.get("motor_timeout_sec", 3.0))
        if started and now - started > limit:
            motor.stop()
            self.motor_timeout_latched = True
            return True
        return False
