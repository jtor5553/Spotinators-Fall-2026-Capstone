"""Central controller. Spot, the gamepad, the motor, and the GUI all come through here."""

import sys
import threading
import time

from autonomy.manager import AutonomyManager
from controller.dualsense import DualSenseController, paired_controllers
from controller.mappings import command_from_sticks
from controller.xinput_pad import XInputController
from core.config import save_operator_identity
from core.events import EventLog
from core.exceptions import SpotConnectionError
from core.state import DispenserState, SystemState
from dispenser.dispenser import HoldToDrop, build_dispenser
from logging_system.logger import flush_logs, setup_logging
from mocks.mock_controller import MockController
from mocks.mock_spot import MockSpot
from safety.safety_manager import SafetyManager
from safety.watchdog import Watchdog
from spot.cameras import encode_solid_png, prefer_visual_source, visual_sources
from spot.connection import SpotSession


class AppController:
    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose
        self.state = SystemState.BOOTING
        self.safety = SafetyManager()
        self.autonomy = AutonomyManager()
        self.last_error = ""
        self.warning = ""
        self.logger = None
        self.events = EventLog(None)
        self.spot = self._build_spot()
        self.gamepad = self._build_gamepad()
        self.dispenser = build_dispenser(config, verbose=verbose)
        self.watchdog = Watchdog(config, self.spot.stop, self.dispenser.motor)
        self.selected_camera = None
        self.camera_ok = False
        self._camera_failure_logged = False
        self._spot_cache = self.spot.status()
        self._last_spot_poll = 0.0
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._started = False
        self._threads_started = False
        self._loop_thread = None
        self._watch_thread = None
        self._shut_down = False
        hold = float(config["controller"].get("cone_hold_sec", 0.5))
        self._pad_drop = HoldToDrop(hold)
        self._gui_drop = HoldToDrop(hold)
        self._gui_hold = False
        self._gui_hold_at = 0.0
        self._prev_buttons = {"lb": False, "rb": False, "options": False}
        self._controller_was_connected = False
        self._controller_loss_handled = False
        self._spot_loss_handled = False
        self._lease_logged = False
        self._lease_loss_logged = False
        self._motor_faulted = False

    def startup(self):
        if self._started:
            return
        self._started = True
        root = self.config["_paths"]["root"]
        self.logger = setup_logging(self.config["logging"], root)
        self.events = EventLog(self.logger)
        self.state = SystemState.BOOTING
        if self.config.get("_password_in_config"):
            self.events.add("CONFIG PASSWORD IGNORED")
        self.events.add("SYSTEM START")
        self.dispenser.initialize()
        self.watchdog = Watchdog(self.config, self.spot.stop, self.dispenser.motor)
        if not self.config["controller"].get("mock", True):
            self.gamepad.start()
        self.safety.motion_allowed = False
        self.state = SystemState.DISCONNECTED
        self.last_error = ""

    def start_background(self):
        self.startup()
        if self._threads_started:
            return
        self._threads_started = True
        self._stop_event.clear()
        self._loop_thread = threading.Thread(target=self._loop, name="spot-cone-control", daemon=True)
        self._watch_thread = threading.Thread(target=self._watch_loop, name="spot-cone-watchdog", daemon=True)
        self._loop_thread.start()
        self._watch_thread.start()

    def shutdown(self):
        with self._lock:
            if self._shut_down:
                return
            self._shut_down = True
            self._stop_event.set()
            try:
                self.spot.stop()
            except Exception:
                self._log_exception("spot stop during shutdown failed")
            try:
                self.dispenser.stop()
            except Exception:
                self._log_exception("dispenser stop during shutdown failed")
            try:
                self.spot.disconnect(power_off=True)
            except Exception:
                self._log_exception("spot disconnect during shutdown failed")
            try:
                self.gamepad.close()
            except Exception:
                self._log_exception("controller close during shutdown failed")
            if self.dispenser.motor is not None and hasattr(self.dispenser.motor, "shutdown"):
                try:
                    self.dispenser.motor.shutdown()
                except Exception:
                    self._log_exception("motor shutdown failed")
            self.events.add("SYSTEM SHUTDOWN")
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2)
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2)
        flush_logs()

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            try:
                self._tick_locked(now)
            except Exception:
                self._log_exception("control loop error")
                self._enter_estop_locked("SOFTWARE FAULT")

    def connect_spot(self, hostname, username, password, remember=False):
        with self._lock:
            hostname = (hostname or "").strip()
            username = (username or "").strip() or "user2"
            if self.state == SystemState.ESTOP:
                return False, "Reset the E-stop before connecting."
            if not hostname:
                return False, "Robot IP is required."
            if not self.config["system"].get("mock_mode", True) and not password:
                return False, "Password is required."
            self.events.add("SPOT CONNECTION ATTEMPT")
            try:
                self.spot.connect(hostname, username, password)
            except Exception as exc:
                self.last_error = self._friendly_spot_error(exc, password)
                self.events.add("SPOT CONNECTION FAILED")
                return False, self.last_error
            self.safety.on_connected()
            self.state = SystemState.SPOT_CONNECTED
            self._spot_loss_handled = False
            self.last_error = ""
            self.warning = ""
            self._spot_cache = self.spot.status()
            self.events.add("SPOT CONNECTED")
            sources = visual_sources(self.spot.list_cameras())
            self.selected_camera = prefer_visual_source(sources)
            if remember:
                save_operator_identity(self.config, hostname, username)
            return True, "Connected."

    def disconnect_spot(self):
        with self._lock:
            try:
                self.spot.stop()
                self.dispenser.stop()
                self.spot.disconnect(power_off=True)
            except Exception as exc:
                self.last_error = str(exc)
            self.safety.motion_allowed = False
            self.safety.stop_latched = False
            self.state = SystemState.DISCONNECTED
            self.selected_camera = None
            self._spot_cache = self.spot.status()
            self.events.add("SPOT DISCONNECTED")
            return True, "Disconnected."

    def stand(self):
        with self._lock:
            return self._stand_locked()

    def sit(self):
        with self._lock:
            return self._sit_locked()

    def normal_stop(self):
        with self._lock:
            return self._normal_stop_locked("NORMAL STOP")

    def emergency_stop(self):
        with self._lock:
            return self._enter_estop_locked("EMERGENCY STOP")

    def reset_estop(self):
        with self._lock:
            if self.state != SystemState.ESTOP:
                return False, "E-stop is not active."
            try:
                self.spot.software_estop_reset()
            except Exception as exc:
                self.last_error = str(exc)
                return False, self.last_error
            self.safety.reset_estop()
            self.watchdog.clear_motion()
            self.state = SystemState.STOPPED
            self.warning = "E-stop reset. Driving is still disabled."
            self.last_error = ""
            self.events.add("ESTOP RESET")
            return True, self.warning

    def arm(self):
        with self._lock:
            if self.state != SystemState.CONTROL_READY or not self.safety.arm():
                self.last_error = "Enable driving only after Spot is connected, standing is available, and stop is cleared."
                return False, self.last_error
            self.state = SystemState.ARMED
            self.last_error = ""
            self.events.add("DRIVING ENABLED")
            return True, "Driving enabled. Hold R2 to move."

    def resume(self):
        with self._lock:
            if self.state != SystemState.STOPPED or not self.safety.resume():
                self.last_error = "Resume is available only after a stop, and not during E-stop."
                return False, self.last_error
            self.state = SystemState.CONTROL_READY if self.spot.connected else SystemState.DISCONNECTED
            if self.state == SystemState.DISCONNECTED:
                self.safety.motion_allowed = False
            self.warning = ""
            self.last_error = ""
            self.events.add("OPERATOR RESUME")
            return True, "Resumed. Driving stays disabled until you enable it."

    def request_drop(self):
        with self._lock:
            return self._request_drop_locked()

    def adjust_cones(self, delta):
        with self._lock:
            if not self.dispenser.adjust(delta):
                return False, "Cone count cannot change while the motor is running."
            self.events.add("CONE COUNT ADJUSTED")
            return True, f"Cones remaining: {self.dispenser.cones_remaining}"

    def reset_cones(self):
        with self._lock:
            if not self.dispenser.reset_count():
                return False, "Cone count cannot change while the motor is running."
            self.events.add("CONE COUNT RESET")
            return True, f"Cones remaining: {self.dispenser.cones_remaining}"

    def reverse_dispenser(self):
        with self._lock:
            if not self._cones_allowed():
                return False, self.last_error or "Cone motor commands are disabled."
            result = self.dispenser.reverse()
            if result is None:
                return False, self.dispenser.last_error or "Reverse was rejected."
            self.events.add("DISPENSER REVERSE")
            return True, "Reverse pulse started."

    def home_dispenser(self):
        with self._lock:
            if not self._cones_allowed():
                return False, self.last_error or "Cone motor commands are disabled."
            result = self.dispenser.home()
            if result is None:
                return False, self.dispenser.last_error or "Home was rejected."
            self.events.add("DISPENSER HOME")
            return True, "Home cycle started."

    def set_gui_drop_hold(self, pressed, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            self._gui_hold = bool(pressed)
            self._gui_hold_at = now

    def select_camera(self, name):
        with self._lock:
            sources = visual_sources(self.spot.list_cameras())
            if name not in sources:
                self.last_error = "That camera was not reported by Spot."
                return False, self.last_error
            self.selected_camera = name
            self._camera_failure_logged = False
            self.events.add(f"CAMERA SELECTED {name}")
            return True, name

    def camera_frame(self):
        with self._lock:
            name = self.selected_camera
            spot = self.spot
            width = int(self.config["camera"]["width"])
            height = int(self.config["camera"]["height"])
        if not name:
            return encode_solid_png(width, height, 20, 20, 20)
        try:
            frame = spot.get_camera_frame(name)
        except Exception:
            frame = None
        if not frame:
            self._note_camera_failure()
            return encode_solid_png(width, height, 60, 20, 20)
        self.camera_ok = True
        self._camera_failure_logged = False
        return frame

    def paired_controllers(self):
        return paired_controllers()

    def snapshot(self):
        with self._lock:
            pad = self.gamepad.snapshot()
            pad["r2_held"] = pad["r2"] >= float(self.config["controller"].get("r2_threshold", 0.2))
            return {
                "version": self.config["system"]["version"],
                "name": self.config["system"]["name"],
                "mode": "MOCK" if self.config["system"].get("mock_mode", True) else "REAL",
                "state": self.state.value,
                "message": self.last_error,
                "warning": self.warning,
                "estop_active": self.state == SystemState.ESTOP,
                "spot": dict(self._spot_cache),
                "controller": pad,
                "dispenser": self.dispenser.status(),
                "camera": {
                    "sources": visual_sources(self.spot.list_cameras()),
                    "selected": self.selected_camera,
                    "fps": int(self.config["camera"].get("fps", 5)),
                    "ok": self.camera_ok,
                },
                "log": self.events.recent(30),
                "drop_hold_progress": max(self._pad_drop.progress, self._gui_drop.progress),
                "commands": self._command_flags(),
                "saved_hostname": self.config["spot"].get("hostname") or "",
                "saved_username": self.config["spot"].get("username") or "",
                "autonomy": "NOT IMPLEMENTED",
            }

    def describe(self):
        spot = "CONNECTED" if self.spot.connected else "NOT CONNECTED"
        controller = "CONNECTED" if self.gamepad.is_connected() else "NOT CONNECTED"
        return {
            "mode": "MOCK" if self.config["system"].get("mock_mode", True) else "REAL",
            "spot": spot,
            "controller": controller,
            "dispenser": self.dispenser.state.value,
        }

    def _tick_locked(self, now):
        self.autonomy.tick()
        self._note_lease_loss_locked()
        self._refresh_spot(now)
        self._apply_motor_timeout()
        pad = self.gamepad.snapshot()
        self._update_controller_presence(pad)
        if self.state != SystemState.ESTOP:
            self._handle_buttons(pad)
        self._apply_motion(pad, now)
        self._update_drop_holds(pad, now)
        result = self.dispenser.poll(now)
        if result == "complete" and self.dispenser.cones_remaining >= 0:
            self.events.add("CONE DROP COMPLETE")
        elif result == "timeout":
            self._motor_fault()
        if self.watchdog.poll_motion(now) and self.state == SystemState.MANUAL_OPERATION:
            self._normal_stop_locked("WATCHDOG STOP")

    def _loop(self):
        while not self._stop_event.is_set():
            start = time.monotonic()
            self.tick(start)
            remaining = 0.05 - (time.monotonic() - start)
            if remaining > 0:
                self._stop_event.wait(remaining)

    def _watch_loop(self):
        while not self._stop_event.is_set():
            self.watchdog.poll_motor()
            self._stop_event.wait(0.1)

    def _refresh_spot(self, now):
        if not self.spot.connected or self._spot_loss_handled:
            return
        if now - self._last_spot_poll < 0.5:
            return
        self._last_spot_poll = now
        try:
            self._spot_cache = self.spot.refresh_status()
        except Exception as exc:
            self._handle_spot_lost(str(exc))
            return
        if self._spot_cache.get("estop") and not self.safety.estop_latched:
            names = self._spot_cache.get("estop_names") or []
            if names == ["software_estop"]:
                self._release_software_estop_locked()
            else:
                self._enter_estop_locked("SPOT REPORTED ESTOP")

    def _release_software_estop_locked(self):
        release = getattr(self.spot, "release_software_estop", None)
        if release is None:
            return
        try:
            release()
        except Exception:
            self._log_exception("software estop release failed")

    def _apply_motor_timeout(self):
        if self.watchdog.motor_timeout_latched:
            self.watchdog.motor_timeout_latched = False
            self.dispenser.note_external_timeout()
            self._motor_fault()

    def _update_controller_presence(self, pad):
        connected = bool(pad["connected"])
        if self._controller_was_connected and not connected and not self._controller_loss_handled:
            self._handle_controller_lost()
            self._controller_loss_handled = True
        if connected:
            if not self._controller_was_connected:
                self.events.add("CONTROLLER CONNECTED")
            self._controller_loss_handled = False
        self._controller_was_connected = connected

    def _handle_buttons(self, pad):
        buttons = pad["buttons"]
        if not pad["connected"]:
            self._prev_buttons = {"lb": False, "rb": False, "options": False}
            return
        if buttons["options"] and not self._prev_buttons["options"]:
            self._normal_stop_locked("NORMAL STOP")
        if buttons["rb"] and not self._prev_buttons["rb"]:
            self._stand_locked()
        if buttons["lb"] and not self._prev_buttons["lb"]:
            self._sit_locked()
        self._prev_buttons = {
            "lb": buttons["lb"],
            "rb": buttons["rb"],
            "options": buttons["options"],
        }

    def _apply_motion(self, pad, now):
        if getattr(self.spot, "posture", "") == "SITTING":
            self.watchdog.clear_motion()
            return
        movement = self.config["movement"]
        controller = self.config["controller"]
        allowed = self.safety.motion_allowed and pad["connected"] and self.state in (
            SystemState.ARMED,
            SystemState.MANUAL_OPERATION,
        )
        if not allowed:
            if self.watchdog.motion_active or any(self.spot.velocity):
                self.spot.stop()
                self.watchdog.clear_motion()
            if self.state == SystemState.MANUAL_OPERATION and self.safety.motion_allowed:
                self.state = SystemState.ARMED
            return
        command = command_from_sticks(
            (pad["left"]["x"], pad["left"]["y"]),
            (pad["right"]["x"], pad["right"]["y"]),
            movement,
            controller.get("deadzone", 0.12),
            pad["r2"],
        )
        if command == (0.0, 0.0, 0.0):
            if self.watchdog.motion_active or any(self.spot.velocity):
                self.spot.stop()
            self.watchdog.clear_motion()
            self.state = SystemState.ARMED
            return
        try:
            moved = self.spot.set_velocity(
                *command, duration_sec=movement.get("command_duration_sec", 0.4)
            )
        except Exception:
            self._log_exception("velocity command failed")
            moved = False
        if not moved:
            self.spot.stop()
            self.watchdog.clear_motion()
            if getattr(self.spot, "command_error", ""):
                self.last_error = "Drive command was rejected. Release the sticks, then try again."
            else:
                self.last_error = "Spot must be standing before it can drive."
            self.state = SystemState.ARMED
            return
        self.watchdog.beat_motion(now)
        self.state = SystemState.MANUAL_OPERATION
        self.last_error = ""

    def _update_drop_holds(self, pad, now):
        gui_pressed = self._gui_hold and (now - self._gui_hold_at) <= 0.3
        pad_pressed = bool(pad["connected"] and pad["buttons"]["x"])
        pad_fire = self._pad_drop.update(pad_pressed, now, verbose=self.verbose, label="X")
        gui_fire = self._gui_drop.update(gui_pressed, now, verbose=False, label="DROP")
        if pad_fire or gui_fire:
            self._request_drop_locked()

    def _request_drop_locked(self):
        if not self._cones_allowed():
            return False, self.last_error or "Cone drop is disabled."
        self.events.add("CONE DROP REQUEST")
        result = self.dispenser.drop_cone()
        if result is None:
            self.events.add("CONE DROP FAILED")
            self.last_error = self.dispenser.last_error or "Cone drop was rejected."
            return False, self.last_error
        if result == "done":
            self.events.add("CONE DROP COMPLETE")
            self.last_error = ""
            return True, "Cone dropped."
        self.last_error = ""
        return True, "Cone drop started."

    def _cones_allowed(self):
        if self.safety.estop_latched or self.state in (
            SystemState.ESTOP,
            SystemState.FAULT,
            SystemState.STOPPED,
        ):
            self.last_error = "Cone commands are disabled."
            return False
        if not self.safety.cone_allowed:
            self.last_error = "Cone commands are disabled."
            return False
        return True

    def _stand_locked(self):
        if not self._posture_allowed():
            return False, self.last_error
        was_lost = self._lease_is_lost()
        try:
            self.spot.stand()
        except Exception as exc:
            return self._posture_rejected("Stand", exc)
        self._spot_cache = self.spot.status()
        self._note_lease_reacquired(was_lost)
        self.events.add("STAND COMMAND")
        if not self._lease_logged and (
            getattr(self.spot, "prepared", False) or self.config["system"].get("mock_mode", True)
        ):
            self.events.add("LEASE ACQUIRED")
            self._lease_logged = True
        if self.state == SystemState.SPOT_CONNECTED:
            self.state = SystemState.CONTROL_READY
        self.last_error = ""
        return True, "Stand command sent."

    def _sit_locked(self):
        if not self._posture_allowed():
            return False, self.last_error
        was_lost = self._lease_is_lost()
        try:
            self.spot.sit()
        except Exception as exc:
            return self._posture_rejected("Sit", exc)
        self._note_lease_reacquired(was_lost)
        self.watchdog.clear_motion()
        self._spot_cache = self.spot.status()
        self.events.add("SIT COMMAND")
        if self.state == SystemState.MANUAL_OPERATION:
            self.state = SystemState.ARMED if self.safety.motion_allowed else SystemState.CONTROL_READY
        self.last_error = ""
        return True, "Sit command sent."

    def _posture_rejected(self, action, exc):
        self.last_error = _posture_failure(action, exc, self.spot)
        self.events.add(f"{action.upper()} FAILED")
        self.events.add(self.last_error)
        return False, self.last_error

    def _lease_is_lost(self):
        lease = getattr(self.spot, "lease", None)
        return bool(lease is not None and getattr(lease, "lost", False))

    def _note_lease_loss_locked(self):
        lease = getattr(self.spot, "lease", None)
        if lease is None or not getattr(lease, "lost", False) or self._lease_loss_logged:
            return
        self._lease_loss_logged = True
        self.events.add("LEASE LOST")
        detail = getattr(lease, "failure", "") or ""
        if detail:
            self.last_error = f"Spot dropped the control lease: {detail}"
        else:
            self.last_error = "Spot dropped the control lease. Stand to take control again."

    def _note_lease_reacquired(self, was_lost):
        if not was_lost or self._lease_is_lost():
            return
        self.events.add("LEASE REACQUIRED")
        self._lease_loss_logged = False
        self._lease_logged = True

    def _posture_allowed(self):
        if not self.spot.connected:
            self.last_error = "Spot is not connected."
            return False
        if self.state in (SystemState.ESTOP, SystemState.FAULT) or self.safety.estop_latched:
            self.last_error = "Posture commands are blocked."
            return False
        return True

    def _normal_stop_locked(self, reason):
        try:
            self.spot.stop()
        except Exception:
            self._log_exception("stop velocity failed")
        self.dispenser.stop()
        self.watchdog.clear_motion()
        self.safety.normal_stop()
        if self.state != SystemState.ESTOP:
            self.state = SystemState.STOPPED
        self.warning = ""
        self.last_error = ""
        self.events.add(reason)
        return True, "Stopped. Spot was left in its current posture."

    def _enter_estop_locked(self, reason):
        already = self.state == SystemState.ESTOP and self.safety.estop_latched
        try:
            self.spot.stop()
        except Exception:
            self._log_exception("estop velocity stop failed")
        self.dispenser.stop()
        try:
            self.spot.software_estop()
        except Exception:
            self._log_exception("software estop call failed")
        self.watchdog.clear_motion()
        self.safety.emergency_stop()
        self.state = SystemState.ESTOP
        self.last_error = "EMERGENCY STOP ACTIVE"
        self.warning = "EMERGENCY STOP ACTIVE"
        if not already:
            self.events.add("EMERGENCY STOP")
            if reason not in ("EMERGENCY STOP", ""):
                self.events.add(reason)
        return True, "EMERGENCY STOP ACTIVE"

    def _handle_controller_lost(self):
        try:
            self.spot.stop()
        except Exception:
            self._log_exception("controller-loss stop failed")
        self.dispenser.stop()
        self.watchdog.clear_motion()
        self.safety.normal_stop()
        if self.state != SystemState.ESTOP:
            self.state = SystemState.STOPPED
        self.warning = "CONTROLLER CONNECTION LOST. ROBOT STOPPED."
        self.events.add("CONTROLLER DISCONNECTED")

    def _handle_spot_lost(self, reason):
        if self._spot_loss_handled:
            return
        self._spot_loss_handled = True
        try:
            self.spot.stop()
        except Exception:
            pass
        self.dispenser.stop()
        try:
            self.spot.disconnect(power_off=False)
        except Exception:
            pass
        self.watchdog.clear_motion()
        self.safety.fault()
        self.state = SystemState.FAULT
        self.warning = "Spot communication lost. Connect again before moving."
        self.last_error = self.warning
        self._spot_cache = self.spot.status()
        self.events.add("SPOT DISCONNECTED")
        if reason:
            self.events.add(f"SPOT FAULT {reason[:180]}")

    def _motor_fault(self):
        if self._motor_faulted:
            return
        self._motor_faulted = True
        self.dispenser.note_external_timeout()
        try:
            self.spot.stop()
        except Exception:
            pass
        self.watchdog.clear_motion()
        self.safety.fault()
        if self.state != SystemState.ESTOP:
            self.state = SystemState.STOPPED
        self.safety.cone_allowed = False
        self.last_error = "Motor command exceeded its time limit."
        self.events.add("MOTOR TIMEOUT")

    def _note_camera_failure(self):
        self.camera_ok = False
        if not self._camera_failure_logged:
            self._camera_failure_logged = True
            self.events.add("CAMERA FAILURE")

    def _command_flags(self):
        connected = self.spot.connected
        blocked = self.state in (SystemState.ESTOP, SystemState.FAULT)
        return {
            "stand": connected and not blocked,
            "sit": connected and not blocked,
            "stop": True,
            "estop": True,
            "reset_estop": self.state == SystemState.ESTOP,
            "arm": self.state == SystemState.CONTROL_READY,
            "resume": self.state == SystemState.STOPPED,
            "drop": self._cones_allowed_quiet() and self.dispenser.state == DispenserState.READY,
            "adjust_cones": self.dispenser.state not in (
                DispenserState.DROPPING,
                DispenserState.HOMING,
                DispenserState.REVERSING,
            ),
        }

    def _cones_allowed_quiet(self):
        if self.safety.estop_latched or not self.safety.cone_allowed:
            return False
        return self.state not in (SystemState.ESTOP, SystemState.FAULT, SystemState.STOPPED)

    def _friendly_spot_error(self, exc, password):
        text = str(exc)
        if password:
            text = text.replace(password, "***")
        if len(text) > 300:
            text = text[:300]
        if isinstance(exc, SpotConnectionError) and "SDK" in text:
            return text
        return (
            "Unable to connect to Spot. Possible causes: Ethernet disconnected, "
            f"incorrect Spot IP, incorrect credentials. {text}"
        )

    def _build_spot(self):
        if self.config["system"].get("mock_mode", True):
            return MockSpot(self.config, verbose=self.verbose)
        return SpotSession(self.config)

    def _build_gamepad(self):
        if self.config["controller"].get("mock", True):
            return MockController()
        if sys.platform == "win32":
            return XInputController()
        return DualSenseController()

    def _log_exception(self, message):
        if self.logger is not None:
            self.logger.exception(message)


def _posture_failure(action, exc, spot):
    text = f"{action} failed: {exc}"
    motor_error = getattr(spot, "motor_error", "") or ""
    if motor_error and motor_error not in text:
        text = f"{text} {motor_error}"
    faults = getattr(spot, "behavior_faults", None) or []
    causes = [str(fault.get("cause")) for fault in faults if fault.get("cause")]
    if causes:
        text = text + " Fault: " + ", ".join(causes)
    return text
