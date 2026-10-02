"""Latest controller sample. The reader thread and the control loop both use it."""

import threading


class ControllerState:
    def __init__(self):
        self._lock = threading.Lock()
        self.connected = False
        self.left = (0.0, 0.0)
        self.right = (0.0, 0.0)
        self.r2 = 0.0
        self.buttons = {
            "x": False,
            "triangle": False,
            "circle": False,
            "options": False,
        }
        self.message = ""

    def snapshot(self):
        with self._lock:
            return {
                "connected": self.connected,
                "left": {"x": self.left[0], "y": self.left[1]},
                "right": {"x": self.right[0], "y": self.right[1]},
                "r2": self.r2,
                "r2_held": self.r2 >= 0.2,
                "buttons": dict(self.buttons),
                "message": self.message,
            }

    def set_connected(self, connected, message=""):
        with self._lock:
            self.connected = bool(connected)
            if message:
                self.message = message
            if not connected:
                self.left = (0.0, 0.0)
                self.right = (0.0, 0.0)
                self.r2 = 0.0
                for name in self.buttons:
                    self.buttons[name] = False

    def set_left(self, x_value, y_value):
        with self._lock:
            self.left = (float(x_value), float(y_value))

    def set_right(self, x_value, y_value):
        with self._lock:
            self.right = (float(x_value), float(y_value))

    def set_r2(self, value):
        with self._lock:
            self.r2 = float(value)

    def set_button(self, name, pressed):
        with self._lock:
            if name in self.buttons:
                self.buttons[name] = bool(pressed)

    def set_axes(self, left, right, r2):
        with self._lock:
            self.left = (float(left[0]), float(left[1]))
            self.right = (float(right[0]), float(right[1]))
            self.r2 = float(r2)

    def is_connected(self):
        with self._lock:
            return self.connected

    def get_left_stick(self):
        with self._lock:
            return self.left

    def get_right_stick(self):
        with self._lock:
            return self.right

    def get_r2(self):
        with self._lock:
            return self.r2

    def get_button_x(self):
        return self._button("x")

    def get_button_triangle(self):
        return self._button("triangle")

    def get_button_circle(self):
        return self._button("circle")

    def get_options(self):
        return self._button("options")

    def _button(self, name):
        with self._lock:
            return self.buttons[name]
