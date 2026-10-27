"""Orin Nano Super 40-pin helpers for Cytron channel 1 (same wiring as TestingMotors).

Pin map (Orin Nano / Orin NX carrier, not AGX Orin):
    header pin 32 -> PWM7, 32e0000.pwm
    header pin 13 -> GPIO PY.00, /dev/gpiochip0 line 122
    header pin 31 -> GPIO PQ.06, /dev/gpiochip0 line 106
"""

import errno
import os
import time

PWM_DEVICE = "32e0000.pwm"
GPIO_CHIP = "/dev/gpiochip0"
BOARD_DIR_LINES = {
    13: 122,
    31: 106,
}
PWM_BOARD_PIN = 32
PWM_PIN_GPIO_LINE = 41
DEFAULT_DIR_BOARD_PIN = 13
DEFAULT_DIR_LINE = BOARD_DIR_LINES[DEFAULT_DIR_BOARD_PIN]


def find_pwmchip(device_name=PWM_DEVICE):
    base = "/sys/class/pwm"
    for chip in sorted(os.listdir(base)):
        if os.path.basename(os.path.realpath(os.path.join(base, chip, "device"))) == device_name:
            return os.path.join(base, chip)
    raise RuntimeError(f"No pwmchip found for {device_name}; is the jetson-io overlay loaded?")


def resolve_dir_line(dir_pin=None, dir_line=None):
    if dir_line is not None:
        return int(dir_line)
    if dir_pin is None:
        return DEFAULT_DIR_LINE
    pin = int(dir_pin)
    if pin not in BOARD_DIR_LINES:
        raise ValueError(
            f"DIR BOARD pin {pin} is not supported. Use pin 13 (line 122) or pin 31 (line 106)."
        )
    return BOARD_DIR_LINES[pin]


def warn_if_pwm_pin_held_as_gpio():
    import gpiod
    from gpiod.line import Direction

    with gpiod.Chip(GPIO_CHIP) as chip:
        info = chip.get_line_info(PWM_PIN_GPIO_LINE)
    if info.used:
        raise RuntimeError(
            f"Line {PWM_PIN_GPIO_LINE} (pin {PWM_BOARD_PIN}) is requested as GPIO by "
            f"'{info.consumer}'; release it so PWM7 can drive the pin."
        )
    if info.direction == Direction.OUTPUT:
        print(
            f"Warning: line {PWM_PIN_GPIO_LINE} (pin {PWM_BOARD_PIN}) was last configured "
            "as a GPIO output. If no PWM appears on the pin, reboot so the pad returns to PWM mode."
        )


class HardwarePWM:
    def __init__(self, frequency_hz=20000, channel=0, device_name=PWM_DEVICE):
        self.chip = find_pwmchip(device_name)
        self.channel = channel
        self.path = os.path.join(self.chip, f"pwm{channel}")
        self.period_ns = int(1e9 / frequency_hz)
        self._exported_here = False

    def _write(self, attr, value, retries=20):
        target = os.path.join(self.path, attr)
        for attempt in range(retries):
            try:
                with open(target, "w") as f:
                    f.write(str(value))
                return
            except PermissionError:
                if attempt == retries - 1:
                    raise
                time.sleep(0.05)

    def _read(self, attr):
        with open(os.path.join(self.path, attr)) as f:
            return f.read().strip()

    def open(self):
        if not os.path.isdir(self.path):
            try:
                with open(os.path.join(self.chip, "export"), "w") as f:
                    f.write(str(self.channel))
                self._exported_here = True
            except OSError as e:
                if e.errno != errno.EBUSY:
                    raise
            for _ in range(40):
                if os.path.isdir(self.path):
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError(f"{self.path} did not appear after export")

        if int(self._read("period")) > 0:
            if self._read("enable") == "1":
                self._write("enable", 0)
            self._write("duty_cycle", 0)
        self._write("period", self.period_ns)
        self._write("duty_cycle", 0)
        self._write("enable", 1)
        return self

    def set_duty(self, percent):
        percent = max(0.0, min(100.0, float(percent)))
        self._write("duty_cycle", int(self.period_ns * percent / 100.0))

    def close(self):
        if not os.path.isdir(self.path):
            return
        try:
            if int(self._read("period")) > 0:
                self._write("duty_cycle", 0)
                self._write("enable", 0)
        finally:
            if self._exported_here:
                try:
                    with open(os.path.join(self.chip, "unexport"), "w") as f:
                        f.write(str(self.channel))
                except OSError:
                    pass
                self._exported_here = False

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()


class DirPin:
    def __init__(self, line=DEFAULT_DIR_LINE, initial=False, chip=GPIO_CHIP):
        self.line = int(line)
        self.chip = chip
        self.initial = initial
        self.request = None

    def open(self):
        import gpiod
        from gpiod.line import Direction, Value

        settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.ACTIVE if self.initial else Value.INACTIVE,
        )
        self.request = gpiod.request_lines(
            self.chip, consumer="spot-cone-dir", config={self.line: settings}
        )
        return self

    def set(self, high):
        from gpiod.line import Value

        self.request.set_value(self.line, Value.ACTIVE if high else Value.INACTIVE)

    def close(self):
        if self.request is not None:
            from gpiod.line import Value

            self.request.set_value(self.line, Value.INACTIVE)
            self.request.release()
            self.request = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()
