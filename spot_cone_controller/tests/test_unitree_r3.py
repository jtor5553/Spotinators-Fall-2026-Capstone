import struct

from controller.unitree_r3 import (
    DEFAULT_MAC,
    BIT_A,
    BIT_B,
    BIT_L1,
    BIT_R1,
    BIT_R2,
    BIT_START,
    BIT_Y,
    apply_deadzone,
    frame_to_controls,
    parse_frame,
    resolve_channel,
    resolve_mac,
)


IDLE_HEX = "000000800000008000000080000000000000423e"


def _packet_with_buttons(buttons1=0, buttons2=0, lx=0.0, ly=0.0, rx=0.0, ry=0.0):
    body = struct.pack("<ffff", lx, rx, ry, ly)
    return body + bytes([buttons1 & 0xFF, buttons2 & 0xFF, 66, 62])


def test_idle_frame_parses_centered_sticks_and_telemetry():
    packet = bytes.fromhex(IDLE_HEX)
    frame = parse_frame(packet)
    assert abs(frame["lx"]) < 1e-6
    assert abs(frame["ly"]) < 1e-6
    assert abs(frame["rx"]) < 1e-6
    assert abs(frame["ry"]) < 1e-6
    assert frame["battery"] == 66
    assert frame["rssi"] == 62
    assert len(frame["raw"]) == 20


def test_a_maps_to_x_for_cone_drop():
    packet = _packet_with_buttons(buttons2=1 << BIT_A)
    controls = frame_to_controls(parse_frame(packet))
    assert controls["buttons"]["x"] is True
    assert controls["buttons"]["circle"] is False
    assert controls["buttons"]["triangle"] is False


def test_face_and_shoulder_buttons():
    b1 = (1 << BIT_L1) | (1 << BIT_R1) | (1 << BIT_START) | (1 << BIT_R2)
    b2 = (1 << BIT_B) | (1 << BIT_Y)
    controls = frame_to_controls(parse_frame(_packet_with_buttons(b1, b2)))
    assert controls["buttons"]["lb"] is True
    assert controls["buttons"]["rb"] is True
    assert controls["buttons"]["options"] is True
    assert controls["buttons"]["circle"] is True
    assert controls["buttons"]["triangle"] is True
    assert controls["r2"] == 1.0


def test_r2_digital_bit_is_zero_when_released():
    controls = frame_to_controls(parse_frame(_packet_with_buttons()))
    assert controls["r2"] == 0.0


def test_deadzone_zeros_small_stick_values():
    assert apply_deadzone(0.05, 0.12) == 0.0
    assert apply_deadzone(-0.11, 0.12) == 0.0
    assert apply_deadzone(0.5, 0.12) == 0.5
    packet = _packet_with_buttons(lx=0.08, ly=-0.5, rx=0.2, ry=0.01)
    controls = frame_to_controls(parse_frame(packet), deadzone=0.12)
    assert controls["left"][0] == 0.0
    assert controls["left"][1] == -0.5
    assert abs(controls["right"][0] - 0.2) < 1e-6
    assert controls["right"][1] == 0.0


def test_resolve_mac_prefers_env(monkeypatch):
    monkeypatch.setenv("UNITREE_MAC", "AA:BB:CC:DD:EE:FF")
    assert resolve_mac({"mac": "98:DA:10:03:37:BA"}) == "AA:BB:CC:DD:EE:FF"
    monkeypatch.delenv("UNITREE_MAC")
    assert resolve_mac({"mac": "11:22:33:44:55:66"}) == "11:22:33:44:55:66"
    assert resolve_mac({}) == DEFAULT_MAC


def test_resolve_channel():
    assert resolve_channel({"rfcomm_channel": 1}) == 1
    assert resolve_channel({}) == 1
