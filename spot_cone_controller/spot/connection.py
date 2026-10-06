"""Real Spot session. The Boston Dynamics SDK is imported only when connecting."""

from core.exceptions import SpotConnectionError
from spot.authentication import authenticate
from spot.cameras import SpotCameras, encode_solid_png
from spot.lease import LeaseManager
from spot.robot_state import motors_are_off, parse_robot_state
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
        self.motor_error = ""
        self.behavior_faults = []
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
        self.command_error = ""

    def connect(self, hostname, username, password):
        try:
            import bosdyn.client
            from bosdyn.client.image import ImageClient
            from bosdyn.client.robot_state import RobotStateClient
        except ImportError as exc:
            raise SpotConnectionError(
                "The Boston Dynamics Python SDK is not installed. "
                "Install bosdyn-client before using real Spot mode."
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
        self.release_software_estop()
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
        self._apply_parsed_state(parsed)
        return self.status()

    def status(self):
        return {
            "connection": "CONNECTED" if self.connected else "NOT CONNECTED",
            "battery": self.battery,
            "robot_state": self.posture,
            "motors": self.motors,
            "motor_error": self.motor_error,
            "behavior_faults": [dict(fault) for fault in self.behavior_faults],
            "hostname": self.hostname,
            "estop": self.robot_estop,
            "estop_names": list(self.robot_estop_names),
            "velocity": self.velocity,
        }

    def prepare_for_motion(self):
        if not self.connected or self.robot is None:
            raise SpotConnectionError("Spot is not connected.")
        if not self.prepared:
            self.estop.setup(self.robot)
            self.lease.acquire(self.robot)
            from bosdyn.client.robot_command import RobotCommandClient

            self.command_client = self.robot.ensure_client(RobotCommandClient.default_service_name)
            self.prepared = True
        elif self.lease.needs_reacquire():
            self.lease.acquire(self.robot)
        self.ensure_motors_on()

    def ensure_motors_on(self, force=False):
        """Turn motor power on when it is off. A session that already stood can do this again."""
        if not force:
            if self.motors == "POWERING_ON":
                return
            if self.powered_on and not motors_are_off(self.motors):
                return
        if not self.connected or self.robot is None:
            raise SpotConnectionError("Spot is not connected.")
        self._power_on_motors()
        self.powered_on = True
        self.motors = "ON"
        self.motor_error = ""

    def stand(self):
        self._command_posture("STANDING", self._issue_stand)

    def sit(self):
        self._command_posture("SITTING", self._issue_sit)

    def _command_posture(self, posture, issue):
        self.prepare_for_motion()
        try:
            issue()
        except Exception as exc:
            if not self._recover_posture(exc):
                raise
            issue()
        self.commanded_posture = posture
        self.posture = posture
        self.motors = "ON"
        if posture == "SITTING":
            self.velocity = (0.0, 0.0, 0.0)

    def _issue_stand(self):
        from spot.movement import stand as command_stand

        command_stand(self.command_client)

    def _issue_sit(self):
        from spot.movement import sit as command_sit

        command_sit(self.command_client)

    def _recover_posture(self, exc):
        """Clear one blocking fault and power the motors, then let the caller retry once."""
        not_powered = command_needs_motor_power(exc)
        faulted = command_blocked_by_fault(exc) and self._has_clearable_fault()
        if not not_powered and not faulted:
            return False
        if faulted:
            try:
                self._clear_behavior_faults()
            except Exception:
                if not not_powered:
                    return False
        if self.lease.needs_reacquire():
            self.lease.acquire(self.robot)
        self.powered_on = False
        self.motors = "OFF"
        self.ensure_motors_on(force=True)
        return True

    def _has_clearable_fault(self):
        return any(fault.get("clearable") for fault in self.behavior_faults)

    def _clear_behavior_faults(self):
        if self.command_client is None:
            return
        remaining = []
        for fault in self.behavior_faults:
            fault_id = fault.get("id")
            if fault.get("clearable") and fault_id is not None:
                self.command_client.clear_behavior_fault(fault_id)
                continue
            remaining.append(fault)
        self.behavior_faults = remaining

    def _power_on_motors(self):
        from bosdyn.client.power import PowerClient, power_on_motors

        power_client = self.robot.ensure_client(PowerClient.default_service_name)
        power_on_motors(power_client, timeout_sec=20)

    def _apply_parsed_state(self, parsed):
        self.battery = parsed["battery"]
        self.motors = parsed["motors"]
        self.motor_error = parsed.get("motor_error") or ""
        self.behavior_faults = list(parsed.get("behavior_faults") or [])
        self.robot_estop = parsed["robot_estop"]
        self.robot_estop_names = parsed["robot_estop_names"]
        if motors_are_off(self.motors):
            self.powered_on = False
        if self.commanded_posture:
            self.posture = self.commanded_posture
        elif motors_are_off(self.motors):
            # Unpowered Spot is treated as sitting. The motor field is shown separately.
            self.posture = "SITTING"
        else:
            self.posture = "POWERED"

    def set_velocity(self, forward, lateral, rotation, duration_sec=0.4):
        if not self.prepared or self.command_client is None or self.posture != "STANDING":
            self.command_error = ""
            return False
        from spot.movement import send_velocity

        try:
            self.velocity = send_velocity(
                self.command_client,
                forward,
                lateral,
                rotation,
                duration_sec,
                timesync_endpoint=self._timesync_endpoint(),
            )
        except Exception as exc:
            self.velocity = (0.0, 0.0, 0.0)
            self.command_error = str(exc)
            return False
        self.command_error = ""
        return True

    def stop(self):
        self.velocity = (0.0, 0.0, 0.0)
        if self.command_client is None or self.posture == "SITTING":
            return
        try:
            from spot.movement import send_velocity

            send_velocity(
                self.command_client,
                0.0,
                0.0,
                0.0,
                0.2,
                timesync_endpoint=self._timesync_endpoint(),
            )
        except Exception:
            pass

    def _timesync_endpoint(self):
        robot = self.robot
        if robot is None:
            return None
        clock = getattr(robot, "time_sync", None)
        if clock is None:
            return None
        return getattr(clock, "endpoint", None)

    def software_estop(self):
        self.stop()
        self.estop.stop()
        self.powered_on = False
        self.motors = "OFF"

    def software_estop_reset(self):
        self.release_software_estop()

    def release_software_estop(self):
        """Register this program's endpoint and allow motion.

        Spot reports software_estop until some endpoint is checking in.
        """
        if self.robot is not None:
            self.estop.setup(self.robot)
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
        self.motor_error = ""
        self.behavior_faults = []
        self.velocity = (0.0, 0.0, 0.0)

    def placeholder_frame(self):
        camera = self.config["camera"]
        return encode_solid_png(int(camera["width"]), int(camera["height"]), 40, 40, 40)


def command_needs_motor_power(exc):
    if type(exc).__name__ == "NotPoweredOnError":
        return True
    text = str(exc).lower()
    return "not powered" in text or "must be powered on" in text


def command_blocked_by_fault(exc):
    if type(exc).__name__ == "BehaviorFaultError":
        return True
    return "behavior fault" in str(exc).lower()
