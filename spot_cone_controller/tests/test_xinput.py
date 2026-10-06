from controller.controller_state import ControllerState
from controller.xinput_pad import BUTTON_A, BUTTON_B, BUTTON_LB, BUTTON_RB, BUTTON_START, BUTTON_Y, apply_xinput


def test_right_trigger_is_deadman_and_stick_up_is_positive():
    state = ControllerState()
    apply_xinput(state, 0, 255, 0, 32767, -32768, 0)
    snap = state.snapshot()
    assert snap["r2"] == 1.0
    assert snap["left"]["y"] == 1.0
    assert snap["right"]["x"] == -1.0
    assert snap["buttons"]["x"] is False


def test_xbox_face_buttons_match_existing_names():
    state = ControllerState()
    apply_xinput(state, BUTTON_A | BUTTON_Y | BUTTON_B | BUTTON_START, 0, 0, 0, 0, 0)
    assert state.snapshot()["buttons"] == {
        "x": True,
        "triangle": True,
        "circle": True,
        "options": True,
        "lb": False,
        "rb": False,
    }


def test_bumpers_are_sit_and_stand():
    state = ControllerState()
    apply_xinput(state, BUTTON_LB | BUTTON_RB, 0, 0, 0, 0, 0)
    buttons = state.snapshot()["buttons"]
    assert buttons["lb"] is True
    assert buttons["rb"] is True
