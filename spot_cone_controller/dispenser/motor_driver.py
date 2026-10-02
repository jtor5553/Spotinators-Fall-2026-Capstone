"""Motor outputs. Channel 2 of a dual driver is intentionally unused."""

import threading
import time

from core.exceptions import MotorNotConfigured


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
    """One channel of a Cytron MDD10A. Pins come from config and may be empty."""

    def __init__(self, dir_pin, pwm_pin, duty_percent=60, frequency=1000):
        self.dir_pin = dir_pin
        self.pwm_pin = pwm_pin
        self.duty_percent = max(0.0, min(100.0, float(duty_percent)))
        self.frequency = int(frequency)
        self.running = False
        self.started_at = 0.0
        self.direction = None
        self._lock = threading.Lock()
        self._gpio = None
        self._pwm = None

    def initialize(self):
        if self.dir_pin is None or self.pwm_pin is None:
            raise MotorNotConfigured(
                "Cytron MDD10A pins are not set. Add dir_pin and pwm_pin after the trailer is wired."
            )
        try:
            import Jetson.GPIO as gpio
        except ImportError as exc:
            raise MotorNotConfigured("Jetson.GPIO is not available. The motor was not energized.") from exc
        with self._lock:
            gpio.setmode(gpio.BOARD)
            gpio.setup(int(self.dir_pin), gpio.OUT, initial=gpio.LOW)
            gpio.setup(int(self.pwm_pin), gpio.OUT, initial=gpio.LOW)
            self._pwm = gpio.PWM(int(self.pwm_pin), self.frequency)
            self._pwm.start(0.0)
            self._gpio = gpio
            self.running = False
            self.direction = None

    def run(self, direction):
        if self._gpio is None or self._pwm is None:
            raise MotorNotConfigured("Motor driver is not initialized.")
        with self._lock:
            level = self._gpio.HIGH if direction == "reverse" else self._gpio.LOW
            self._gpio.output(int(self.dir_pin), level)
            self._pwm.ChangeDutyCycle(self.duty_percent)
            self.direction = direction
            self.started_at = time.monotonic()
            self.running = True

    def stop(self):
        with self._lock:
            if self._pwm is not None:
                self._pwm.ChangeDutyCycle(0.0)
            if self._gpio is not None and self.dir_pin is not None:
                self._gpio.output(int(self.dir_pin), self._gpio.LOW)
            self.running = False
            self.direction = None

    def shutdown(self):
        self.stop()
        with self._lock:
            if self._pwm is not None:
                self._pwm.stop()
                self._pwm = None
            if self._gpio is not None:
                try:
                    self._gpio.cleanup()
                except Exception:
                    pass
                self._gpio = None
