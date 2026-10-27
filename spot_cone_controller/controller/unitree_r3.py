"""Unitree R3-1 remote over Classic Bluetooth RFCOMM (SPP).

The Jetson kernel here has BLE off, so this reader opens RFCOMM channel 1
itself and maps 20-byte stick/button frames into ControllerState the same
way DualSense does. Only one process may own the SPP socket — stop the
lab unitree-bt user service while this app is reading.
"""

from __future__ import annotations

import os
import socket
import struct
import threading

from controller.controller_state import ControllerState

DEFAULT_MAC = "98:DA:10:03:37:BA"
DEFAULT_CHANNEL = 1
FRAME_SIZE = 20
CONNECT_TIMEOUT_SEC = 10.0
READ_TIMEOUT_SEC = 0.2
RECONNECT_BACKOFF_SEC = (0.5, 1.0, 2.0, 5.0)

# Byte 16
BIT_R1 = 0
BIT_L1 = 1
BIT_START = 2
BIT_SELECT = 3
BIT_R2 = 4
BIT_L2 = 5
BIT_F1 = 6
BIT_F2 = 7

# Byte 17
BIT_A = 0
BIT_B = 1
BIT_X = 2
BIT_Y = 3


def _bit(byte_value, bit):
    return bool((int(byte_value) >> bit) & 1)


def apply_deadzone(value, deadzone):
    """Zero stick values inside the deadzone; pass through otherwise."""
    value = float(value)
    deadzone = float(deadzone)
    if abs(value) <= deadzone:
        return 0.0
    return max(-1.0, min(1.0, value))


def parse_frame(packet):
    """Parse one 20-byte RFCOMM payload into sticks and button bits."""
    if len(packet) < FRAME_SIZE:
        raise ValueError(f"Unitree frame needs {FRAME_SIZE} bytes, got {len(packet)}")
    lx, rx, ry, ly = struct.unpack_from("<ffff", packet, 0)
    b1 = packet[16]
    b2 = packet[17]
    battery = packet[18]
    rssi = packet[19]
    return {
        "lx": float(lx),
        "ly": float(ly),
        "rx": float(rx),
        "ry": float(ry),
        "buttons1": b1,
        "buttons2": b2,
        "battery": battery,
        "rssi": rssi,
        "raw": bytes(packet[:FRAME_SIZE]),
    }


def frame_to_controls(frame, deadzone=0.12):
    """Map a parsed frame into ControllerState fields (DualSense semantics)."""
    left_x = apply_deadzone(frame["lx"], deadzone)
    left_y = apply_deadzone(frame["ly"], deadzone)
    right_x = apply_deadzone(frame["rx"], deadzone)
    right_y = apply_deadzone(frame["ry"], deadzone)
    b1 = frame["buttons1"]
    b2 = frame["buttons2"]
    r2 = 1.0 if _bit(b1, BIT_R2) else 0.0
    buttons = {
        "x": _bit(b2, BIT_A),
        "circle": _bit(b2, BIT_B),
        "triangle": _bit(b2, BIT_Y),
        "lb": _bit(b1, BIT_L1),
        "rb": _bit(b1, BIT_R1),
        "options": _bit(b1, BIT_START),
    }
    return {
        "left": (left_x, left_y),
        "right": (right_x, right_y),
        "r2": r2,
        "buttons": buttons,
        "battery": frame["battery"],
        "rssi": frame["rssi"],
    }


def resolve_mac(controller_config=None):
    """UNITREE_MAC env wins over YAML; fall back to the lab remote MAC."""
    env = os.environ.get("UNITREE_MAC", "").strip()
    if env:
        return env
    if controller_config:
        configured = str(controller_config.get("mac") or "").strip()
        if configured:
            return configured
    return DEFAULT_MAC


def resolve_channel(controller_config=None):
    if controller_config and controller_config.get("rfcomm_channel") is not None:
        return int(controller_config["rfcomm_channel"])
    return DEFAULT_CHANNEL


class UnitreeR3Controller:
    """Background RFCOMM reader that exposes the DualSense controller API."""

    def __init__(self, controller_config=None):
        config = dict(controller_config or {})
        self.mac = resolve_mac(config)
        self.channel = resolve_channel(config)
        self.deadzone = float(config.get("deadzone", 0.12))
        self.state = ControllerState()
        self._stop = threading.Event()
        self._thread = None
        self._sock = None
        self._sock_lock = threading.Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="unitree-r3", daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        self._close_socket()
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
        backoff_index = 0
        while not self._stop.is_set():
            try:
                sock = self._connect()
            except Exception as exc:
                self.state.set_connected(False, f"Unitree R3 waiting: {exc}")
                delay = RECONNECT_BACKOFF_SEC[min(backoff_index, len(RECONNECT_BACKOFF_SEC) - 1)]
                backoff_index += 1
                if self._stop.wait(delay):
                    return
                continue
            backoff_index = 0
            self.state.set_connected(True, "Unitree R3")
            try:
                self._read_loop(sock)
            except Exception as exc:
                self.state.set_connected(False, f"Unitree R3 disconnected: {exc}")
            finally:
                self._close_socket()
            if self._stop.is_set():
                return
            if self._stop.wait(RECONNECT_BACKOFF_SEC[0]):
                return

    def _connect(self):
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        sock.settimeout(CONNECT_TIMEOUT_SEC)
        try:
            sock.connect((self.mac, self.channel))
        except Exception:
            sock.close()
            raise
        sock.settimeout(READ_TIMEOUT_SEC)
        with self._sock_lock:
            self._sock = sock
        return sock

    def _read_loop(self, sock):
        buf = bytearray()
        while not self._stop.is_set():
            try:
                chunk = sock.recv(64)
            except socket.timeout:
                continue
            if not chunk:
                raise ConnectionError("RFCOMM closed")
            buf.extend(chunk)
            while len(buf) >= FRAME_SIZE:
                packet = bytes(buf[:FRAME_SIZE])
                del buf[:FRAME_SIZE]
                self._apply_packet(packet)

    def _apply_packet(self, packet):
        frame = parse_frame(packet)
        controls = frame_to_controls(frame, self.deadzone)
        self.state.set_axes(controls["left"], controls["right"], controls["r2"])
        for name, pressed in controls["buttons"].items():
            self.state.set_button(name, pressed)
        if not self.state.is_connected():
            self.state.set_connected(True, "Unitree R3")

    def _close_socket(self):
        with self._sock_lock:
            sock = self._sock
            self._sock = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
