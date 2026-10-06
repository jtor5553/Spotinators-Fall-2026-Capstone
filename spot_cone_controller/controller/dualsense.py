"""PS5 DualSense on Linux evdev. Pairing stays a one-time OS step."""

import os
import re
import shutil
import subprocess
import threading

from controller.controller_state import ControllerState

# Linux input event codes. python-evdev uses these same values.
EV_KEY = 0x01
EV_ABS = 0x03
ABS_X = 0x00
ABS_Y = 0x01
ABS_RX = 0x03
ABS_RY = 0x04
ABS_RZ = 0x05
BTN_GAMEPAD = 0x130
BTN_SOUTH = 0x130
BTN_EAST = 0x131
BTN_NORTH = 0x133
BTN_TL = 0x136
BTN_TR = 0x137
BTN_TR2 = 0x139
BTN_START = 0x13B

KEY_BUTTONS = {
    BTN_SOUTH: "x",
    BTN_EAST: "circle",
    BTN_NORTH: "triangle",
    BTN_TL: "lb",
    BTN_TR: "rb",
    BTN_START: "options",
}

PERMISSION_MESSAGE = (
    "DualSense is present but cannot be read. "
    "Add this user to the input group, then log in again."
)
NOT_FOUND_MESSAGE = "DualSense not found."
_BLUETOOTH_ADDRESS = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class DualSenseController:
    def __init__(self):
        self.state = ControllerState()
        self._stop = threading.Event()
        self._thread = None
        self._permission_denied = False

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
                if self._permission_denied:
                    self.state.set_connected(False, PERMISSION_MESSAGE)
                else:
                    connect_paired_dualsense()
                    self.state.set_connected(False, NOT_FOUND_MESSAGE)
                if self._stop.wait(1.0):
                    return
                continue
            self.state.set_connected(True, device.name)
            self._read(device, evdev)
            self.state.set_connected(False, "DualSense disconnected.")

    def _find(self, evdev):
        denied = False
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
            except PermissionError:
                if looks_like_dualsense(_sysfs_name(path)):
                    denied = True
                continue
            except OSError:
                continue
            selected = False
            try:
                name = device.name or ""
                abs_codes, key_codes = _capability_codes(device, evdev)
                selected = is_dualsense_gamepad(name, abs_codes, key_codes)
            except PermissionError:
                if looks_like_dualsense(getattr(device, "name", "") or _sysfs_name(path)):
                    denied = True
            except OSError:
                selected = False
            if selected:
                self._permission_denied = False
                return device
            _close_device(device)
        self._permission_denied = denied
        return None

    def _read(self, device, evdev):
        import select

        try:
            device.grab()
        except OSError:
            pass
        left = [0.0, 0.0]
        right = [0.0, 0.0]
        analog_r2 = False
        try:
            while not self._stop.is_set():
                ready, _, _ = select.select([device.fd], [], [], 0.2)
                if not ready:
                    continue
                for event in device.read():
                    analog_r2 = self._handle(event, device, left, right, analog_r2)
        except OSError:
            return
        finally:
            try:
                device.ungrab()
            except OSError:
                pass
            _close_device(device)

    def _handle(self, event, device, left, right, analog_r2):
        if event.type == EV_ABS:
            info = device.absinfo(event.code)
            return apply_axis_event(self.state, event.code, event.value, info, left, right, analog_r2)
        if event.type == EV_KEY:
            apply_key_event(self.state, event.code, event.value, analog_r2)
        return analog_r2


def looks_like_dualsense(name):
    """True for the gamepad name. Motion sensors and the touchpad are separate nodes."""
    lowered = (name or "").lower()
    if "motion sensors" in lowered or "touchpad" in lowered:
        return False
    return "dualsense" in lowered or "wireless controller" in lowered


def is_dualsense_gamepad(name, abs_codes, key_codes):
    """Accept the stick node only. Name match alone is not enough."""
    if not looks_like_dualsense(name):
        return False
    axes = _code_set(abs_codes)
    keys = _code_set(key_codes)
    if ABS_X not in axes:
        return False
    return BTN_SOUTH in keys or BTN_GAMEPAD in keys


def controller_absent_message(permission_denied):
    if permission_denied:
        return PERMISSION_MESSAGE
    return NOT_FOUND_MESSAGE


def apply_axis_event(state, code, value, info, left, right, analog_r2):
    if code == ABS_X:
        left[0] = _norm_axis(value, info)
    elif code == ABS_Y:
        left[1] = -_norm_axis(value, info)
    elif code == ABS_RX:
        right[0] = _norm_axis(value, info)
    elif code == ABS_RY:
        right[1] = -_norm_axis(value, info)
    elif code == ABS_RZ:
        state.set_r2(_norm_trigger(value, info))
        analog_r2 = True
    state.set_left(left[0], left[1])
    state.set_right(right[0], right[1])
    return analog_r2


def apply_key_event(state, code, value, analog_r2):
    """Map face buttons. BTN_TR2 is R2 only when the analog trigger axis is absent."""
    pressed = value != 0
    if code == BTN_TR2:
        if not analog_r2:
            state.set_r2(1.0 if pressed else 0.0)
        return
    name = KEY_BUTTONS.get(code)
    if name:
        state.set_button(name, pressed)


def paired_dualsense_addresses(devices):
    addresses = []
    for device in devices or []:
        if not looks_like_dualsense(device.get("name", "")):
            continue
        address = device.get("address", "")
        if _is_bluetooth_address(address):
            addresses.append(address)
    return addresses


def bluetoothctl_connect_args(address):
    """Arguments for connecting one already paired controller. Never pair or trust."""
    if not _is_bluetooth_address(address):
        return None
    return ["bluetoothctl", "connect", address]


def connect_paired_dualsense(run_command=None):
    """Connect an already paired DualSense. This does not scan, pair, or trust."""
    listing = paired_controllers()
    if not listing.get("available"):
        return {
            "connected": False,
            "message": listing.get("message", ""),
            "addresses": [],
        }
    addresses = paired_dualsense_addresses(listing.get("devices", []))
    if not addresses:
        return {"connected": False, "message": "No paired DualSense.", "addresses": []}
    runner = run_command or _bluetoothctl_connect
    for address in addresses:
        if runner(address):
            return {
                "connected": True,
                "message": "Connected paired DualSense.",
                "addresses": addresses,
            }
    return {
        "connected": False,
        "message": "Paired DualSense did not connect.",
        "addresses": addresses,
    }


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


def _bluetoothctl_connect(address):
    args = bluetoothctl_connect_args(address)
    if args is None or shutil.which("bluetoothctl") is None:
        return False
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _capability_codes(device, evdev):
    capabilities = device.capabilities()
    codes = evdev.ecodes
    abs_items = capabilities.get(codes.EV_ABS, capabilities.get(EV_ABS, []))
    key_items = capabilities.get(codes.EV_KEY, capabilities.get(EV_KEY, []))
    return _code_set(abs_items), _code_set(key_items)


def _code_set(items):
    codes = set()
    for item in items or []:
        if isinstance(item, tuple):
            codes.add(item[0])
        else:
            codes.add(item)
    return codes


def _sysfs_name(path):
    event = os.path.basename(path or "")
    name_path = os.path.join("/sys/class/input", event, "device", "name")
    try:
        with open(name_path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _close_device(device):
    try:
        device.close()
    except OSError:
        pass


def _is_bluetooth_address(address):
    return bool(_BLUETOOTH_ADDRESS.match(address or ""))


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
