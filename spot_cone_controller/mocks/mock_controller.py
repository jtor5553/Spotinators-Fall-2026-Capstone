"""In-memory DualSense stand-in for tests and computers without Bluetooth."""

from controller.controller_state import ControllerState


class MockController(ControllerState):
    def start(self):
        return None

    def close(self):
        return None
