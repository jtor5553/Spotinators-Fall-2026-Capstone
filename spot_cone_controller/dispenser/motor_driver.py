"""Motor outputs. Channel 2 of a dual driver is intentionally unused.

Cytron channel 1 on the Orin Nano uses hardware PWM on BOARD pin 32 and DIR on
BOARD pin 13 (gpiod line 122), matching Desktop/TestingMotors.
"""

import threading
import time

from core.exceptions import MotorNotConfigured
from dispenser.cytron_hw import (
    PWM_BOARD_PIN,
    DirPin,
    HardwarePWM,
    resolve_dir_line,
    warn_if_pwm_pin_held_as_gpio,
)


class NullMotor:
    """Used while the dispenser is disabled. run() is refused."""

    def __init__(self):
        self.running = False
        self.started_at = 0.0
        self.direction = None

    def initialize(self):
        self.stop()

    def run(self, direction):
        raise MotorNotConfigured("Dispenser motor is disabled.")

    def stop(self):
        self.running = False
        self.direction = None


class CytronMDD10A:
    """One channel of a Cytron MDD10A via hardware PWM + gpiod DIR."""

    def __init__(
        self,
        dir_pin=None,
        pwm_pin=None,
        duty_percent=60,
        frequency=20000,
        dir_line=None,
    ):
        self.dir_pin = dir_pin
        self.pwm_pin = pwm_pin
        self.dir_line = dir_line
        self.duty_percent = max(0.0, min(100.0, float(duty_percent)))
        self.frequency = int(frequency)
        self.running = False
        self.started_at = 0.0
        self.direction = None
        self._lock = threading.Lock()
        self._dir = None
        self._pwm = None

    def initialize(self):
        if self.pwm_pin is None and self.dir_pin is None and self.dir_line is None:
            raise MotorNotConfigured(
                "Cytron MDD10A pins are not set. Add dir_pin and pwm_pin after the trailer is wired."
            )
        pwm_pin = PWM_BOARD_PIN if self.pwm_pin is None else int(self.pwm_pin)
        if pwm_pin != PWM_BOARD_PIN:
            raise MotorNotConfigured(
                f"PWM must use BOARD pin {PWM_BOARD_PIN} (hardware PWM7). Got pin {pwm_pin}."
            )
        try:
            line = resolve_dir_line(self.dir_pin, self.dir_line)
        except ValueError as exc:
            raise MotorNotConfigured(str(exc)) from exc
        try:
            import gpiod  # noqa: F401
        except ImportError as exc:
            raise MotorNotConfigured(
                "gpiod is not available. Install gpiod and ensure the venv can import system packages."
            ) from exc
        with self._lock:
            self._shutdown_locked()
            try:
                warn_if_pwm_pin_held_as_gpio()
                self._dir = DirPin(line=line, initial=False)
                self._dir.open()
                self._pwm = HardwarePWM(frequency_hz=self.frequency)
                self._pwm.open()
                self._pwm.set_duty(0.0)
            except Exception:
                self._shutdown_locked()
                raise
            self.dir_line = line
            self.pwm_pin = pwm_pin
            self.running = False
            self.direction = None

    def run(self, direction):
        if self._dir is None or self._pwm is None:
            raise MotorNotConfigured("Motor driver is not initialized.")
        with self._lock:
            # Match TestingMotors: forward = DIR high, reverse = DIR low.
            self._dir.set(direction != "reverse")
            self._pwm.set_duty(self.duty_percent)
            self.direction = direction
            self.started_at = time.monotonic()
            self.running = True

    def stop(self):
        with self._lock:
            self._stop_locked()

    def shutdown(self):
        with self._lock:
            self._shutdown_locked()

    def _stop_locked(self):
        if self._pwm is not None:
            self._pwm.set_duty(0.0)
        if self._dir is not None:
            self._dir.set(False)
        self.running = False
        self.direction = None

    def _shutdown_locked(self):
        self._stop_locked()
        if self._pwm is not None:
            try:
                self._pwm.close()
            except Exception:
                pass
            self._pwm = None
        if self._dir is not None:
            try:
                self._dir.close()
            except Exception:
                pass
            self._dir = None
