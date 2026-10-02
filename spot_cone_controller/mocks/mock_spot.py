"""Fake Spot used when the real robot is not on the network."""

from spot.cameras import encode_solid_png
from spot.movement import clamp_velocity


class MockSpot:
    COLORS = {
        "front": (24, 110, 58),
        "left": (28, 74, 140),
        "right": (150, 96, 28),
        "rear": (96, 42, 120),
    }

    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose
        self.connected = False
        self.hostname = ""
        self.battery = None
        self.posture = "UNKNOWN"
        self.motors = "OFF"
        self.robot_estop = False
        self.robot_estop_names = []
        self.velocity = (0.0, 0.0, 0.0)
        self.estop = False
        self.powered_on = False
        self.sources = ["front", "left", "right", "rear"]

    def connect(self, hostname, username, password):
        del username, password
        self.connected = True
        self.hostname = hostname
        self.battery = 84
        self.posture = "SITTING"
        self.motors = "OFF"
        self.estop = False
        self.velocity = (0.0, 0.0, 0.0)
        if self.verbose:
            print("MOCK SPOT CONNECTED")
            print("Battery: 84%")
            print("State: Sitting")
        return True

    def refresh_status(self):
        if not self.connected:
            from core.exceptions import SpotConnectionError

            raise SpotConnectionError("Mock Spot is not connected.")
        return self.status()

    def status(self):
        return {
            "connection": "CONNECTED" if self.connected else "NOT CONNECTED",
            "battery": self.battery,
            "robot_state": self.posture,
            "motors": self.motors,
            "hostname": self.hostname,
            "estop": self.estop,
            "estop_names": list(self.robot_estop_names),
            "velocity": self.velocity,
        }

    def prepare_for_motion(self):
        if not self.connected:
            raise RuntimeError("Mock Spot is not connected.")
        self.powered_on = True
        self.motors = "ON"

    def stand(self):
        if not self.connected:
            raise RuntimeError("Mock Spot is not connected.")
        if self.estop:
            raise RuntimeError("E-stop is active.")
        self.prepare_for_motion()
        self.posture = "STANDING"
        self.motors = "ON"
        if self.verbose:
            print("[MOCK SPOT]")
            print("Stand command received.")

    def sit(self):
        if not self.connected:
            raise RuntimeError("Mock Spot is not connected.")
        if self.estop:
            raise RuntimeError("E-stop is active.")
        self.posture = "SITTING"
        self.velocity = (0.0, 0.0, 0.0)
        if self.verbose:
            print("[MOCK SPOT]")
            print("Sit command received.")

    def set_velocity(self, forward, lateral, rotation, duration_sec=0.4):
        del duration_sec
        if not self.connected or self.estop or self.posture != "STANDING":
            self.velocity = (0.0, 0.0, 0.0)
            return False
        self.velocity = clamp_velocity(forward, lateral, rotation)
        return True

    def stop(self):
        self.velocity = (0.0, 0.0, 0.0)

    def software_estop(self):
        self.stop()
        self.estop = True

    def software_estop_reset(self):
        self.estop = False

    def list_cameras(self):
        if not self.connected:
            return []
        return list(self.sources)

    def get_camera_frame(self, name):
        color = self.COLORS.get(name, (50, 50, 50))
        camera = self.config["camera"]
        return encode_solid_png(int(camera["width"]), int(camera["height"]), *color)

    def disconnect(self, power_off=True):
        del power_off
        self.stop()
        self.connected = False
        self.battery = None
        self.motors = "OFF"
        self.powered_on = False
        self.estop = False

    def placeholder_frame(self):
        camera = self.config["camera"]
        return encode_solid_png(int(camera["width"]), int(camera["height"]), 20, 20, 20)
