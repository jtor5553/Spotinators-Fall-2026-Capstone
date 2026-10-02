# Spot Cone Placement Controller

Manual control software for a Boston Dynamics Spot robot that tows a prototype traffic-cone trailer. The NVIDIA Jetson Orin Nano is the only controller. The Spot tablet is a touchscreen browser and does not command the robot.

Version 1.0.0 is the manual system. Autonomous cone placement is not included.

## Safety

The program starts disarmed. The dispenser motor starts off. Nothing in the saved configuration resumes a previous move or a previous motor command.

- Driving requires Enable driving, then the R2 trigger, then a stick. Sticks alone do nothing.
- Releasing R2 sends zero velocity immediately.
- Velocity commands last less than half a second and must be refreshed while the operator holds R2.
- If the PS5 controller disconnects, Spot is stopped, cone commands are disabled, and driving does not resume when the controller returns. Press Resume, then Enable driving.
- Stop and Emergency stop are different. Stop zeros velocity, stops the motor, and leaves Spot in its current posture. Emergency stop is immediate, has no confirmation, and stays on until Reset E-stop.
- Reset E-stop does not start driving.
- A motor command that runs too long turns the motor off and faults the dispenser.
- The tablet can disconnect. The Jetson program keeps running.
- This software does not replace Spot's physical E-stop or the trailer's mushroom E-stop. A frozen process cannot clear a GPIO pin. The mushroom button has to cut motor power.
- Test speeds stay low. The code also refuses commands above 0.6 m/s forward, 0.4 m/s sideways, and 0.6 rad/s turning, even if the config file is larger.
- Do not test the trailer in live traffic. Use a closed lot.

The Spot password is typed into the tablet and kept in memory. It is not written to `config.yaml` or the log. A password key in the config file is ignored.

## Run the mock system

Mock mode is the default. It does not talk to Spot, Bluetooth, or GPIO.

From this folder:

```powershell
cd spot_cone_controller
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py --mock-dispenser
```

On the Jetson:

```bash
cd ~/spot_cone_controller
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --mock-dispenser
```

Open `http://127.0.0.1:8000` on the same computer, or `http://<jetson-ip>:8000` from the tablet. The page is served by the Jetson. It does not use a CDN, cloud API, or external font.

Expected startup text:

```text
===================================
Spot Cone Placement Controller
===================================

Version: 1.0.0

Starting system...

Mode: MOCK
Spot: NOT CONNECTED
Controller: NOT CONNECTED
Dispenser: READY
Web Interface: STARTING

System ready.
```

Without `--mock-dispenser`, the dispenser line says `DISABLED`. That is the safe default in `config/config.yaml`.

In the browser, press Connect, or press Practice without Spot to use the dispenser screen before a robot is connected.

1. Enter any robot IP. Mock mode accepts it. The password can be blank in mock mode.
2. Connect. Battery reads 84% and the posture reads SITTING.
3. Press Stand, then Sit, then Stop.
4. Press and hold Drop cone for half a second. The count goes from 4 to 3. Holding longer does not drop another cone.
5. Emergency stop shows EMERGENCY STOP ACTIVE immediately. Stand is refused until Reset E-stop. Driving stays off after the reset.

Check the whole manual path without a browser:

```bash
python main.py --self-test
```

That command exits 0 when every mock check passes.

## Layout

```text
spot_cone_controller/
  main.py                 startup and web server
  config/                 defaults and operator settings
  core/                   state, config, and the app controller
  spot/                   real Spot SDK session
  mocks/                  fake Spot and fake controller
  controller/             DualSense and stick mapping
  dispenser/              motor, mock motor, optional limit switches
  safety/                 stop, E-stop, and watchdog rules
  gui/                    local HTML, CSS, and JavaScript
  autonomy/               empty extension point
  logging_system/         rotating log files
  deploy/                 systemd unit
  scripts/                read-only system check and optional hotspot
  tests/
```

The app controller is the only place that decides whether a command is legal. The page, the gamepad, and a future autonomy module send requests to it. They do not talk to Spot or the motor driver directly.

```text
Tablet browser / PS5 / future autonomy
                 |
          App controller
                 |
     +-----------+-----------+
     |           |           |
   Spot      Dispenser    Safety
```

States, in order: BOOTING, DISCONNECTED, SPOT_CONNECTED, CONTROL_READY, ARMED, MANUAL_OPERATION. Stop uses STOPPED. Failures use FAULT. The software E-stop uses ESTOP.

## Controls

| Input | Action |
| --- | --- |
| Left stick | Forward, back, and strafe, only while R2 is held |
| Right stick | Rotate, only while R2 is held |
| R2 | Dead-man. Release it and velocity goes to zero |
| X, held 0.5 s | Drop one cone, then wait for release |
| Triangle | Stand |
| Circle | Sit |
| Options | Normal stop |
| On-screen Emergency stop | Software E-stop, no confirmation |

Spot's body frame is +X forward, +Y left, and positive rotation to the left. The mapper converts the sticks into that frame and then applies the speed limits.

Enable driving before R2 will move the robot. After Stop, press Resume and then Enable driving again.

## Dispenser

The trailer uses one motor. A Cytron MDD10A has two channels; this program uses channel 1 only.

GPIO pin numbers are empty on purpose. The real driver refuses to start until `dir_pin` and `pwm_pin` are filled in after the wiring is finished. Until then, keep:

```yaml
dispenser:
  enabled: false
  mock: true
```

`--mock-dispenser` turns the mock motor on for software tests. It still does not energize hardware.

Limit switches default to off. Timed motion is used instead. If you later install switches, set `limit_switches_enabled: true` and both pin numbers. Missing pins fault the dispenser instead of running blind.

The cone count starts at 4. Minus, plus, and Reset change the bookkeeping count when the trailer is reloaded. The count decreases only after a drop cycle finishes. A timeout or a rejected command does not decrease it.

## Cameras

After Spot is connected, the page lists the image sources the robot reports. It shows one source at a time, at the configured size and frame rate (640x480 and 5 fps). Raise `camera.fps` to 10 only after the Jetson stays responsive. Mock mode shows front, left, right, and rear color fields so the selector can be tested. Those names are not assumed for the real robot.

## Use the real Spot

Do this only after the mock checks pass, with Spot in a clear area and the physical E-stop in reach.

1. Install the SDK on the Jetson while you still have a network connection: `python3 -m pip install bosdyn-client`
2. In `config/config.yaml`, set `system.mock_mode: false`.
3. Leave `controller.mock: true` and `dispenser.enabled: false` for the first robot test.
4. Connect the Jetson Ethernet port to Spot. Do not hard-code the robot IP; type it on the connection screen.
5. Connect, confirm battery and posture, then Stand, Sit, and Stop.
6. Only then set `controller.mock: false`, install `python3-evdev`, and pair the DualSense.

The first real connection is read-only: login, time sync, battery, and posture. Stand is what takes the lease, registers the software E-stop endpoint, and powers the motors. Taking that endpoint replaces other software E-stop endpoints. Spot's physical button still works.

A failed connection stays on the page and reports the usual causes: Ethernet, IP, or credentials. It does not close the interface.

## PS5 controller

The DualSense pairs to the Jetson, not the tablet. This version reconnects to a controller that Linux has already paired. The on-screen Search paired button only lists devices with `bluetoothctl`. It does not pair a new controller. Pair once in Linux if the automatic GUI pairing is not in place yet:

```bash
bluetoothctl
```

Then scan, trust, and pair the DualSense. The program looks for an input device whose name contains `DualSense` or `Wireless Controller`.

If Phase 0 did not find Bluetooth hardware, leave `controller.mock: true`. The program will not pretend a radio is present.

## Logs

Logs go to `spot_cone_controller/logs/spot_cone.log`, rotating at about 1 MB with five backups. The same lines appear in the on-screen log. Connection attempts are logged. Passwords are not.

## Offline hotspot

Do not run the apply path until `scripts/system_check.sh` has shown a Wi-Fi interface. The Orin Nano Developer Kit has no built-in Wi-Fi unless an M.2 or USB adapter is installed.

Check only:

```bash
bash scripts/setup_hotspot.sh
```

If no radio is found, the script says `Wi-Fi: NOT FOUND` and exits without changes.

Create the access point only when you know the interface name and the address you want:

```bash
sudo bash scripts/setup_hotspot.sh --apply --interface wlan0 --address 192.168.50.1 --password 'choose-a-passphrase'
```

`192.168.50.1` is an example, not a detected address. The script refuses to run without an interface, an address, and a password of at least 8 characters. The tablet then joins `SPOT-CONE-CONTROL` and opens `http://<that-address>:8000`. No internet is required.

## Start on boot

`deploy/spot-cone-controller.service` restarts the program after a crash. A restart loads the config again and begins in DISCONNECTED with the motor off. It does not continue an old drive command.

Edit the user name and paths in the unit file, then:

```bash
sudo cp deploy/spot-cone-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now spot-cone-controller.service
```

Leave `mock_mode: true` until a supervised robot test has passed. Enabling the service does not by itself move Spot.

## Tests

```bash
cd spot_cone_controller
python -m pytest
```

The tests cover the state machine, R2 dead-man, controller loss, the half-second cone hold, the cone counter, motor timeout, E-stop, the watchdog, local-only page assets, and the startup service file.

Phase 0, on the Jetson only:

```bash
bash scripts/system_check.sh
```

That script is read-only. Copy the full output back before changing network settings or installing the Spot SDK.

## Hardware phases that still need the robot

The software for the manual system runs here in mock mode. These steps still happen on the Jetson with the hardware:

- Phase 0 system check, if the output has not been reviewed yet
- Real Spot Ethernet login, stand, sit, and stop
- DualSense over Bluetooth, only if a radio was found
- Real motor pulses, only after the mock dispenser tests pass and the pins are known
- Camera selection on the live Spot image service
- Hotspot and systemd install

## Autonomy

`autonomy/manager.py` is present and disabled. A later mode can request the same stand, sit, velocity, and drop commands the gamepad uses. It must go through the app controller. It cannot skip R2 policy, the watchdog, or either stop. GPS, route planning, cone spacing, and camera navigation are not implemented.

## Troubleshooting

| What you see | What it means |
| --- | --- |
| `Mode: MOCK` | Spot calls stay on the fake robot. Set `mock_mode: false` for the real robot. |
| Dispenser `DISABLED` | `dispenser.enabled` is false. Use `--mock-dispenser` to practice drops. |
| SDK is not installed | Install `bosdyn-client` on the Jetson before real mode. |
| `evdev is not installed` | Expected on Windows and until `python3-evdev` is installed on the Jetson. |
| Wi-Fi `NOT FOUND` | No radio was detected. Do not configure a hotspot. |
| `$'\r': command not found` | The shell script has Windows line endings. Run `sed -i 's/\r$//' scripts/system_check.sh` and try again. |
| Emergency stop stays on | Press Reset E-stop, then Resume, then Enable driving. A physical E-stop also has to be released on the robot. |
