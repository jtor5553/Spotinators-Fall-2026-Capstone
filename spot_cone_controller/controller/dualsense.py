"""PS5 DualSense on Linux evdev. Pairing can stay a one-time OS step."""

import shutil
import subprocess
import threading

from controller.controller_state import ControllerState


class DualSenseController:
    def __init__(self):
        self.state = ControllerState()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="dualsense", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2.0)
        self.state.set_connected(False, "Controller closed.")

    def snapshot(self):
        return self.state.snapshot()

    def is_connected(self):
        return self.state.is_connected()

    def get_left_stick(self):
        return self.state.get_left_stick()

    def get_right_stick(self):
        return self.state.get_right_stick()

    def get_r2(self):
        return self.state.get_r2()

    def get_button_x(self):
        return self.state.get_button_x()

    def get_button_triangle(self):
        return self.state.get_button_triangle()

    def get_button_circle(self):
        return self.state.get_button_circle()

    def get_options(self):
        return self.state.get_options()

    def _run(self):
        try:
            import evdev
        except ImportError:
            self.state.set_connected(False, "evdev is not installed. Pairing hardware was not changed.")
            return
        while not self._stop.is_set():
            device = self._find(evdev)
            if device is None:
                self.state.set_connected(False, "DualSense not found.")
                if self._stop.wait(1.0):
                    return
                continue
            self.state.set_connected(True, device.name)
            self._read(device, evdev)
            self.state.set_connected(False, "DualSense disconnected.")

    def _find(self, evdev):
        for path in evdev.list_devices():
            device = evdev.InputDevice(path)
            name = device.name or ""
            if "DualSense" in name or "Wireless Controller" in name:
                return device
            device.close()
        return None

    def _read(self, device, evdev):
        import select

        try:
            device.grab()
        except OSError:
            pass
        left = [0.0, 0.0]
        right = [0.0, 0.0]
        try:
            while not self._stop.is_set():
                ready, _, _ = select.select([device.fd], [], [], 0.2)
                if not ready:
                    continue
                for event in device.read():
                    self._handle(event, evdev, device, left, right)
        except OSError:
            return
        finally:
            try:
                device.ungrab()
            except OSError:
                pass
            try:
                device.close()
            except OSError:
                pass

    def _handle(self, event, evdev, device, left, right):
        codes = evdev.ecodes
        if event.type == codes.EV_ABS:
            info = device.absinfo(event.code)
            if event.code == codes.ABS_X:
                left[0] = _norm_axis(event.value, info)
            elif event.code == codes.ABS_Y:
                left[1] = -_norm_axis(event.value, info)
            elif event.code == codes.ABS_RX:
                right[0] = _norm_axis(event.value, info)
            elif event.code == codes.ABS_RY:
                right[1] = -_norm_axis(event.value, info)
            elif event.code == codes.ABS_RZ:
                self.state.set_r2(_norm_trigger(event.value, info))
            self.state.set_left(left[0], left[1])
            self.state.set_right(right[0], right[1])
        elif event.type == codes.EV_KEY:
            name = {
                codes.BTN_SOUTH: "x",
                codes.BTN_EAST: "circle",
                codes.BTN_NORTH: "triangle",
                codes.BTN_TL: "lb",
                codes.BTN_TR: "rb",
                codes.BTN_START: "options",
            }.get(event.code)
            if name:
                self.state.set_button(name, event.value != 0)


def _norm_axis(value, info):
    if info is None or info.max == info.min:
        return 0.0
    midpoint = (info.max + info.min) / 2.0
    half = (info.max - info.min) / 2.0
    if half == 0:
        return 0.0
    scaled = (value - midpoint) / half
    return max(-1.0, min(1.0, scaled))


def _norm_trigger(value, info):
    if info is None or info.max == info.min:
        return 0.0
    scaled = (value - info.min) / float(info.max - info.min)
    return max(0.0, min(1.0, scaled))


def paired_controllers():
    """Read already paired Bluetooth devices. This does not pair or connect."""
    if shutil.which("bluetoothctl") is None:
        return {
            "available": False,
            "message": "bluetoothctl was not found. Bluetooth hardware was not changed.",
            "devices": [],
        }
    try:
        completed = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "message": str(exc), "devices": []}
    devices = []
    for line in completed.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) >= 3 and parts[0] == "Device":
            devices.append({"address": parts[1], "name": parts[2]})
    return {
        "available": True,
        "message": "Paired devices. New pairing can be added later and is not required for this version.",
        "devices": devices,
    }
