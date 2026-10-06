from controller.controller_state import ControllerState
from controller.dualsense import (
    ABS_RX,
    ABS_RY,
    ABS_X,
    ABS_Y,
    ABS_RZ,
    BTN_EAST,
    BTN_GAMEPAD,
    BTN_NORTH,
    BTN_SOUTH,
    BTN_START,
    BTN_TL,
    BTN_TR,
    BTN_TR2,
    NOT_FOUND_MESSAGE,
    PERMISSION_MESSAGE,
    apply_axis_event,
    apply_key_event,
    bluetoothctl_connect_args,
    connect_paired_dualsense,
    controller_absent_message,
    is_dualsense_gamepad,
    looks_like_dualsense,
)


class _AxisInfo:
    def __init__(self, minimum, maximum):
        self.min = minimum
        self.max = maximum


def test_gamepad_node_requires_sticks_and_face_button():
    name = "Sony Interactive Entertainment DualSense Wireless Controller"
    assert is_dualsense_gamepad(name, [ABS_X, ABS_Y], [BTN_SOUTH])
    assert is_dualsense_gamepad("Wireless Controller", [ABS_X], [BTN_GAMEPAD])
    assert not is_dualsense_gamepad(name, [], [BTN_SOUTH])
    assert not is_dualsense_gamepad(name, [ABS_X], [])
    assert not is_dualsense_gamepad("Xbox 360 Controller", [ABS_X], [BTN_SOUTH])


def test_motion_sensor_and_touchpad_nodes_are_ignored():
    assert not looks_like_dualsense("Wireless Controller Motion Sensors")
    assert not looks_like_dualsense("Sony Interactive Entertainment Wireless Controller Touchpad")
    assert not is_dualsense_gamepad(
        "DualSense Wireless Controller Motion Sensors",
        [ABS_X, ABS_Y, ABS_RX, ABS_RY],
        [BTN_SOUTH],
    )
    assert looks_like_dualsense("Sony Interactive Entertainment Wireless Controller")


def test_permission_message_names_the_input_group():
    assert "input group" in PERMISSION_MESSAGE
    assert "not found" not in PERMISSION_MESSAGE.lower()
    assert controller_absent_message(True) == PERMISSION_MESSAGE
    assert controller_absent_message(False) == NOT_FOUND_MESSAGE


def test_r2_button_is_fallback_when_analog_axis_is_absent():
    state = ControllerState()
    apply_key_event(state, BTN_TR2, 1, analog_r2=False)
    assert state.get_r2() == 1.0
    apply_key_event(state, BTN_TR2, 0, analog_r2=False)
    assert state.get_r2() == 0.0


def test_analog_r2_stays_when_digital_trigger_is_released():
    state = ControllerState()
    left = [0.0, 0.0]
    right = [0.0, 0.0]
    analog = apply_axis_event(state, ABS_RZ, 255, _AxisInfo(0, 255), left, right, False)
    assert analog is True
    assert state.get_r2() == 1.0
    apply_key_event(state, BTN_TR2, 0, analog_r2=True)
    assert state.get_r2() == 1.0


def test_face_buttons_keep_existing_names():
    state = ControllerState()
    apply_key_event(state, BTN_SOUTH, 1, False)
    apply_key_event(state, BTN_EAST, 1, False)
    apply_key_event(state, BTN_NORTH, 1, False)
    apply_key_event(state, BTN_START, 1, False)
    apply_key_event(state, BTN_TL, 1, False)
    apply_key_event(state, BTN_TR, 1, False)
    assert state.snapshot()["buttons"] == {
        "x": True,
        "circle": True,
        "triangle": True,
        "options": True,
        "lb": True,
        "rb": True,
    }


def test_generic_driver_numbers_buttons_from_square():
    from controller.dualsense import GENERIC_LAYOUT, layout_from_driver

    assert layout_from_driver("hid-generic") == GENERIC_LAYOUT
    assert layout_from_driver("hid-playstation") == "playstation"
    state = ControllerState()
    apply_key_event(state, 0x131, 1, False, "generic")
    apply_key_event(state, 0x134, 1, False, "generic")
    apply_key_event(state, 0x135, 1, False, "generic")
    apply_key_event(state, 0x139, 1, False, "generic")
    apply_key_event(state, 0x137, 1, False, "generic")
    buttons = state.snapshot()["buttons"]
    assert buttons["x"] is True
    assert buttons["lb"] is True
    assert buttons["rb"] is True
    assert buttons["options"] is True
    assert state.get_r2() == 1.0


def test_usb_and_bluetooth_reports_map_the_same_buttons():
    from controller.dualsense import apply_dualsense_sample, parse_dualsense_report

    usb = bytearray(64)
    usb[0] = 0x01
    usb[1] = 128
    usb[2] = 0
    usb[3] = 255
    usb[4] = 128
    usb[6] = 255
    usb[8] = 0x20
    usb[9] = 0x01 | 0x02 | 0x20
    sample = parse_dualsense_report(bytes(usb))
    assert sample["buttons"] == {
        "x": True,
        "circle": False,
        "triangle": False,
        "lb": True,
        "rb": True,
        "options": True,
    }
    assert sample["r2"] == 1.0
    assert sample["left"][1] == 1.0
    assert sample["right"][0] > 0.9

    bluetooth = bytearray(78)
    bluetooth[0] = 0x31
    bluetooth[2] = 128
    bluetooth[3] = 255
    bluetooth[9] = 0x80
    bluetooth[10] = 0x20
    sample = parse_dualsense_report(bytes(bluetooth))
    assert sample["buttons"]["triangle"] is True
    assert sample["buttons"]["options"] is True
    assert sample["left"][1] < -0.9
    assert parse_dualsense_report(b"\x01\x00\x00") is None

    state = ControllerState()
    state.set_button("x", True)
    apply_dualsense_sample(state, parse_dualsense_report(bytes(bluetooth)))
    assert state.get_button_x() is False
    assert state.get_options() is True


def test_connect_uses_only_an_already_paired_dualsense(monkeypatch):
    def fake_paired():
        return {
            "available": True,
            "message": "",
            "devices": [
                {"address": "AA:BB:CC:DD:EE:FF", "name": "DualSense Wireless Controller"},
                {"address": "11:22:33:44:55:66", "name": "Xbox Wireless Controller"},
                {"address": "01:02:03:04:05:06", "name": "Wireless Controller Motion Sensors"},
            ],
        }

    monkeypatch.setattr("controller.dualsense.paired_controllers", fake_paired)
    calls = []

    def runner(address):
        calls.append(address)
        return True

    result = connect_paired_dualsense(run_command=runner)
    assert calls == ["AA:BB:CC:DD:EE:FF"]
    assert result["connected"] is True
    assert bluetoothctl_connect_args("AA:BB:CC:DD:EE:FF") == [
        "bluetoothctl",
        "connect",
        "AA:BB:CC:DD:EE:FF",
    ]
    assert bluetoothctl_connect_args("not-a-mac") is None
