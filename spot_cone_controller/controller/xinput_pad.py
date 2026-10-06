"""Windows XInput gamepad. Pair the PG-9083S in PC mode first."""

import ctypes
import sys
import threading

from controller.controller_state import ControllerState

BUTTON_A = 0x1000
BUTTON_B = 0x2000
BUTTON_Y = 0x8000
BUTTON_START = 0x0010
BUTTON_LB = 0x0100
BUTTON_RB = 0x0200

CONNECTED_NAME = "Xbox 360 Controller"
NOT_FOUND = "Gamepad not found. Pair the PG-9083S in PC mode (hold Home and X)."


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


class XInputController:
    def __init__(self):
        self.state = ControllerState()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="xinput", daemon=True)
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
        xinput = load_xinput()
        if xinput is None:
            if sys.platform != "win32":
                self.state.set_connected(False, "XInput is only available on Windows.")
            else:
                self.state.set_connected(False, "xinput1_4.dll was not found.")
            return
        while not self._stop.is_set():
            index = find_controller(xinput)
            if index is None:
                self.state.set_connected(False, NOT_FOUND)
                if self._stop.wait(0.5):
                    return
                continue
            self.state.set_connected(True, CONNECTED_NAME)
            self._read(xinput, index)
            self.state.set_connected(False, "Gamepad disconnected.")

    def _read(self, xinput, index):
        while not self._stop.is_set():
            sample = read_state(xinput, index)
            if sample is None:
                return
            apply_xinput(self.state, *sample)
            if self._stop.wait(0.02):
                return


def load_xinput():
    if sys.platform != "win32":
        return None
    for name in ("xinput1_4", "xinput1_3"):
        try:
            dll = ctypes.WinDLL(name)
        except OSError:
            continue
        dll.XInputGetState.argtypes = [ctypes.c_uint, ctypes.POINTER(XINPUT_STATE)]
        dll.XInputGetState.restype = ctypes.c_uint
        return dll
    return None


def find_controller(xinput):
    for index in range(4):
        if read_state(xinput, index) is not None:
            return index
    return None


def read_state(xinput, index):
    packet = XINPUT_STATE()
    result = xinput.XInputGetState(ctypes.c_uint(index), ctypes.byref(packet))
    if result != 0:
        return None
    pad = packet.Gamepad
    return (
        int(pad.wButtons),
        int(pad.bRightTrigger),
        int(pad.sThumbLX),
        int(pad.sThumbLY),
        int(pad.sThumbRX),
        int(pad.sThumbRY),
    )


def apply_xinput(state, buttons, right_trigger, thumb_lx, thumb_ly, thumb_rx, thumb_ry):
    """Map one XInput sample. Sticks are -32768..32767 with +Y up. Triggers are 0..255."""
    state.set_left(_norm_stick(thumb_lx), _norm_stick(thumb_ly))
    state.set_right(_norm_stick(thumb_rx), _norm_stick(thumb_ry))
    state.set_r2(_norm_trigger(right_trigger))
    state.set_button("x", bool(buttons & BUTTON_A))
    state.set_button("triangle", bool(buttons & BUTTON_Y))
    state.set_button("circle", bool(buttons & BUTTON_B))
    state.set_button("options", bool(buttons & BUTTON_START))
    state.set_button("lb", bool(buttons & BUTTON_LB))
    state.set_button("rb", bool(buttons & BUTTON_RB))


def _norm_stick(value):
    scaled = float(value) / 32767.0
    return max(-1.0, min(1.0, scaled))


def _norm_trigger(value):
    return max(0.0, min(1.0, float(value) / 255.0))
