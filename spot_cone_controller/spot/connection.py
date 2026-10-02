"""Real Spot session. The Boston Dynamics SDK is imported only when connecting."""

from core.exceptions import SpotConnectionError
from spot.authentication import authenticate
from spot.cameras import SpotCameras, encode_solid_png
from spot.lease import LeaseManager
from spot.robot_state import parse_robot_state
from spot.spot_estop import SpotEStop


class SpotSession:
    def __init__(self, config):
        self.config = config
        self.robot = None
        self.connected = False
        self.hostname = ""
        self.battery = None
        self.posture = "UNKNOWN"
        self.motors = "UNKNOWN"
        self.robot_estop = False
        self.robot_estop_names = []
        self.velocity = (0.0, 0.0, 0.0)
        self.commanded_posture = None
        self.powered_on = False
        self.command_client = None
        self.state_client = None
        self.cameras = None
        self.lease = LeaseManager()
        self.estop = SpotEStop()
        self.prepared = False
        self._camera_names = []

    def connect(self, hostname, username, password):
        try:
            import bosdyn.client
            from bosdyn.client.image import ImageClient
            from bosdyn.client.robot_state import RobotStateClient
        except ImportError as exc:
            raise SpotConnectionError(
                "The Boston Dynamics Python SDK is not installed. "
                "Install bosdyn-client on the Jetson before using real Spot mode."
            ) from exc
        sdk = bosdyn.client.create_standard_sdk("SpotConeController")
        robot = sdk.create_robot(hostname)
        authenticate(robot, username, password)
        self.robot = robot
        self.hostname = hostname
        self.state_client = robot.ensure_client(RobotStateClient.default_service_name)
        image_client = robot.ensure_client(ImageClient.default_service_name)
        camera_cfg = self.config["camera"]
        self.cameras = SpotCameras(image_client, camera_cfg["width"], camera_cfg["height"])
        self.connected = True
        self.refresh_status()
        try:
            self._camera_names = self.cameras.list_sources()
        except Exception:
            self._camera_names = []
        return True

    def refresh_status(self):
        if not self.connected or self.state_client is None:
            raise SpotConnectionError("Spot is not connected.")
        parsed = parse_robot_state(self.state_client.get_robot_state())
        self.battery = parsed["battery"]
        self.motors = parsed["motors"]
        self.robot_estop = parsed["robot_estop"]
        self.robot_estop_names = parsed["robot_estop_names"]
        if self.commanded_posture:
            self.posture = self.commanded_posture
        elif self.motors == "OFF":
            # Unpowered Spot is treated as sitting. The motor field is shown separately.
            self.posture = "SITTING"
        else:
            self.posture = "POWERED"
        return self.status()

    def status(self):
        return {
            "connection": "CONNECTED" if self.connected else "NOT CONNECTED",
            "battery": self.battery,
            "robot_state": self.posture,
            "motors": self.motors,
            "hostname": self.hostname,
            "estop": self.robot_estop,
            "estop_names": list(self.robot_estop_names),
            "velocity": self.velocity,
        }

    def prepare_for_motion(self):
        if self.prepared:
            return
        if not self.connected or self.robot is None:
            raise SpotConnectionError("Spot is not connected.")
        self.estop.setup(self.robot)
        self.lease.acquire(self.robot)
        from bosdyn.client.power import PowerClient, power_on_motors
        from bosdyn.client.robot_command import RobotCommandClient

        power_client = self.robot.ensure_client(PowerClient.default_service_name)
        power_on_motors(power_client, timeout_sec=20)
        self.powered_on = True
        self.motors = "ON"
        self.command_client = self.robot.ensure_client(RobotCommandClient.default_service_name)
        self.prepared = True

    def stand(self):
        self.prepare_for_motion()
        from spot.movement import stand as command_stand

        command_stand(self.command_client)
        self.commanded_posture = "STANDING"
        self.posture = "STANDING"
        self.motors = "ON"

    def sit(self):
        self.prepare_for_motion()
        from spot.movement import sit as command_sit

        command_sit(self.command_client)
        self.commanded_posture = "SITTING"
        self.posture = "SITTING"
        self.velocity = (0.0, 0.0, 0.0)

    def set_velocity(self, forward, lateral, rotation, duration_sec=0.4):
        if not self.prepared or self.command_client is None:
            return False
        if self.posture != "STANDING":
            return False
        from spot.movement import send_velocity

        self.velocity = send_velocity(
            self.command_client, forward, lateral, rotation, duration_sec
        )
        return True

    def stop(self):
        self.velocity = (0.0, 0.0, 0.0)
        if self.command_client is None:
            return
        try:
            from spot.movement import send_velocity

            send_velocity(self.command_client, 0.0, 0.0, 0.0, 0.2)
        except Exception:
            pass

    def software_estop(self):
        self.stop()
        self.estop.stop()

    def software_estop_reset(self):
        self.estop.allow()

    def list_cameras(self):
        return list(self._camera_names)

    def get_camera_frame(self, name):
        if self.cameras is None:
            return None
        try:
            return self.cameras.fetch(name)
        except Exception:
            return None

    def disconnect(self, power_off=True):
        self.stop()
        if power_off and self.powered_on and self.robot is not None:
            try:
                from bosdyn.client.power import PowerClient, power_off_motors

                power_client = self.robot.ensure_client(PowerClient.default_service_name)
                power_off_motors(power_client, timeout_sec=20)
            except Exception:
                pass
        self.powered_on = False
        try:
            self.lease.release()
        except Exception:
            pass
        try:
            self.estop.shutdown()
        except Exception:
            pass
        self.command_client = None
        self.prepared = False
        self.connected = False
        self.battery = None
        self.motors = "OFF"
        self.velocity = (0.0, 0.0, 0.0)

    def placeholder_frame(self):
        camera = self.config["camera"]
        return encode_solid_png(int(camera["width"]), int(camera["height"]), 40, 40, 40)
