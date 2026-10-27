"""Cone dispenser. The GUI calls this object and never touches GPIO."""

import time

from core.exceptions import SensorError
from core.state import DispenserState
from dispenser.mock_motor import MockMotor
from dispenser.motor_driver import CytronMDD10A, NullMotor
from dispenser.sensors import LimitSwitches


class HoldToDrop:
    """Accepts one action after the input has been held, then waits for release."""

    def __init__(self, hold_sec):
        self.hold_sec = float(hold_sec)
        self.started = None
        self.fired = False
        self.elapsed = 0.0
        self._marks = set()

    def update(self, pressed, now, verbose=False, label="X"):
        if not pressed:
            self.started = None
            self.fired = False
            self.elapsed = 0.0
            self._marks.clear()
            return False
        if self.fired:
            self.elapsed = self.hold_sec
            return False
        if self.started is None:
            self.started = now
            if verbose:
                print(f"{label} pressed...")
        self.elapsed = now - self.started
        if verbose:
            for mark in (0.1, 0.2, 0.3, 0.4, 0.5):
                if self.elapsed + 1e-9 >= mark and mark not in self._marks and mark <= self.hold_sec + 1e-9:
                    self._marks.add(mark)
                    print(f"{int(mark * 1000)} ms")
        if self.elapsed >= self.hold_sec:
            self.fired = True
            return True
        return False

    @property
    def progress(self):
        if self.hold_sec <= 0:
            return 0.0
        return max(0.0, min(1.0, self.elapsed / self.hold_sec))


class Dispenser:
    def __init__(self, motor, switches, config, enabled, immediate, verbose=False):
        self.motor = motor
        self.switches = switches
        self.config = config
        self.enabled = enabled
        self.immediate = immediate
        self.verbose = verbose
        self.state = DispenserState.UNKNOWN
        self.cones_remaining = int(config.get("cone_capacity", 4))
        self.capacity = int(config.get("cone_capacity", 4))
        self.last_error = ""
        self._operation = None
        self._started = 0.0

    def initialize(self):
        self.motor.stop()
        if not self.enabled:
            self.state = DispenserState.DISABLED
            self.last_error = ""
            return
        if self.switches.enabled and (self.switches.home_pin is None or self.switches.end_pin is None):
            self.state = DispenserState.FAULT
            self.last_error = "Limit switches are enabled but pins are not configured."
            return
        try:
            self.motor.initialize()
        except Exception as exc:
            self.motor.stop()
            self.state = DispenserState.FAULT
            self.last_error = str(exc)
            return
        self.state = DispenserState.READY
        self.last_error = ""

    def status(self):
        return {
            "state": self.state.value,
            "cones_remaining": self.cones_remaining,
            "capacity": self.capacity,
            "enabled": self.enabled,
            "error": self.last_error,
            "motor_running": bool(self.motor.running),
        }

    def drop_cone(self):
        if not self._ready("drop"):
            return None
        if self.cones_remaining <= 0:
            self.last_error = "No cones remaining."
            return None
        return self._start("drop", "forward")

    def reverse(self):
        if not self._ready("reverse"):
            return None
        return self._start("reverse", "reverse")

    def home(self):
        if not self._ready("home"):
            return None
        self.state = DispenserState.HOMING
        return self._start("home", "reverse", state=DispenserState.HOMING)

    def stop(self):
        self.motor.stop()
        self._operation = None
        if self.state in (DispenserState.DROPPING, DispenserState.REVERSING, DispenserState.HOMING):
            if self.enabled:
                self.state = DispenserState.READY
        return True

    def adjust(self, delta):
        if self.state in (DispenserState.DROPPING, DispenserState.HOMING, DispenserState.REVERSING):
            return False
        updated = self.cones_remaining + int(delta)
        self.cones_remaining = max(0, min(self.capacity, updated))
        return True

    def reset_count(self):
        if self.state in (DispenserState.DROPPING, DispenserState.HOMING, DispenserState.REVERSING):
            return False
        self.cones_remaining = self.capacity
        return True

    def poll(self, now):
        if self._operation is None:
            return None
        try:
            if self._switch_finished():
                return self._finish(success=True)
        except SensorError as exc:
            self.motor.stop()
            self.state = DispenserState.FAULT
            self.last_error = str(exc)
            self._operation = None
            return "fault"
        timeout = float(self.config.get("motor_timeout_sec", 3.0))
        elapsed = now - self._started
        if elapsed + 1e-4 >= timeout:
            self.motor.stop()
            self.state = DispenserState.FAULT
            self.last_error = "Motor command exceeded its time limit."
            self._operation = None
            return "timeout"
        if elapsed >= self._duration_for(self._operation):
            kind = self._finish(success=True)
            if kind == "drop":
                return "complete"
            if kind:
                return "cycle"
            return "fault"
        return None

    def note_external_timeout(self):
        if self.state == DispenserState.FAULT and self.last_error:
            return
        self.motor.stop()
        self.state = DispenserState.FAULT
        self.last_error = "Motor command exceeded its time limit."
        self._operation = None

    def _ready(self, action):
        if not self.enabled or self.state == DispenserState.DISABLED:
            self.last_error = "Dispenser is disabled."
            return False
        if self.state == DispenserState.FAULT:
            self.last_error = self.last_error or "Dispenser is faulted."
            return False
        if self.state != DispenserState.READY:
            self.last_error = f"Dispenser is {self.state.value}, so {action} was ignored."
            return False
        return True

    def _start(self, operation, direction, state=DispenserState.DROPPING):
        try:
            self.motor.run(direction)
        except Exception as exc:
            self.motor.stop()
            self.state = DispenserState.FAULT
            self.last_error = str(exc)
            return None
        self._operation = operation
        self._started = time.monotonic()
        if operation == "reverse":
            self.state = DispenserState.REVERSING
        elif operation == "home":
            self.state = DispenserState.HOMING
        else:
            self.state = state
        self.last_error = ""
        if self.verbose and operation == "drop":
            print("DROP ACCEPTED")
            print("[MOCK DISPENSER]")
            print("Dropping cone...")
        if self.immediate:
            return "done" if self._finish(success=True) else None
        return "started"

    def _finish(self, success):
        self.motor.stop()
        operation = self._operation
        self._operation = None
        if not success or self.motor.running:
            self.state = DispenserState.FAULT
            self.last_error = "Motor did not stop."
            return False
        if operation == "drop":
            self.cones_remaining = max(0, self.cones_remaining - 1)
            if self.verbose:
                print("Cone dropped.")
                print(f"Cones remaining: {self.cones_remaining}")
        self.state = DispenserState.READY
        self.last_error = ""
        return operation

    def _duration_for(self, operation):
        if operation == "drop":
            return float(self.config.get("drop_duration_sec", 1.5))
        if operation == "home":
            return float(self.config.get("home_duration_sec", 1.5))
        return float(self.config.get("reverse_duration_sec", 0.5))

    def _switch_finished(self):
        if not self.switches.enabled or self.immediate:
            return False
        if self._operation == "drop":
            return self.switches.end_switch_active()
        if self._operation in ("home", "reverse"):
            return self.switches.home_switch_active()
        return False


def build_dispenser(config, verbose=False):
    settings = config["dispenser"]
    switches = LimitSwitches(
        enabled=bool(settings.get("limit_switches_enabled", False)),
        home_pin=settings.get("home_switch_pin"),
        end_pin=settings.get("end_switch_pin"),
    )
    if not settings.get("enabled", False):
        motor = NullMotor()
        enabled = False
        immediate = True
    elif settings.get("mock", True):
        motor = MockMotor()
        enabled = True
        immediate = True
    else:
        motor = CytronMDD10A(
            settings.get("dir_pin"),
            settings.get("pwm_pin"),
            duty_percent=settings.get("motor_duty_percent", 60),
            frequency=settings.get("motor_pwm_hz", 20000),
            dir_line=settings.get("dir_line"),
        )
        enabled = True
        immediate = False
    return Dispenser(motor, switches, settings, enabled, immediate, verbose=verbose)
