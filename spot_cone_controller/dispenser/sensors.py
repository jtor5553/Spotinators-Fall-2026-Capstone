"""Optional limit switches. Disabled until the trailer wiring is decided."""

from core.exceptions import SensorError


class LimitSwitches:
    def __init__(self, enabled, home_pin, end_pin):
        self.enabled = bool(enabled)
        self.home_pin = home_pin
        self.end_pin = end_pin
        self._gpio = None

    def home_switch_active(self):
        if not self.enabled:
            return False
        return self._read(self.home_pin)

    def end_switch_active(self):
        if not self.enabled:
            return False
        return self._read(self.end_pin)

    def _read(self, pin):
        if pin is None:
            raise SensorError("Limit switch pin is not configured.")
        if self._gpio is None:
            try:
                import Jetson.GPIO as gpio
            except ImportError as exc:
                raise SensorError("Jetson.GPIO is not available, so limit switches cannot be read.") from exc
            self._gpio = gpio
            gpio.setmode(gpio.BOARD)
            gpio.setup(int(pin), gpio.IN)
        value = self._gpio.input(int(pin))
        return bool(value)
