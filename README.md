# Spotinators Fall 2026 Capstone

This is the Fall 2026 capstone software for Spotinators.

A Boston Dynamics Spot robot tows a small trailer that drops traffic cones. An NVIDIA Jetson Orin Nano on the trailer is the controller. The Spot tablet is only a touchscreen. It opens this program in a web browser. It does not drive the robot.

You can practice the full operator screen on a Windows PC, including a PG-9083S gamepad. Spot and the cone motor are connected later, on the Jetson. The Jetson uses the PS5 controller.

The on-screen title stays **Spot Cone Placement System**. That is the operator page. This repository is the capstone project around it.

## Practice on Windows

Open PowerShell in this repository folder, then run:

```powershell
cd spot_cone_controller
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py --mock-dispenser
```

Leave that window open. In a browser, open:

http://127.0.0.1:8000

Then:

1. Type any numbers into Robot IP. Mock mode does not use a real address. The username can stay `user2`.
2. Leave the password blank and press **Connect to Spot**. **Practice without Spot** only opens the operator page. Commands still need a connection.
3. Press **Stand**, then **Sit**, then **Stop**.
4. Press and hold **Hold to drop cone** for half a second. The count goes from 4 to 3. Holding longer does not drop a second cone.
5. Press **Emergency stop**. The page says EMERGENCY STOP ACTIVE immediately. Stand is refused until you press **Reset E-stop**.

Press Ctrl+C in PowerShell when you want to quit.

The startup text should include `Mode: MOCK` and `Dispenser: READY`. If you start without `--mock-dispenser`, the dispenser stays `DISABLED` and cone drops are refused. That is the safe default.

To check the same path without a browser:

```powershell
.\.venv\Scripts\python main.py --self-test
```

The last line should say `25 / 25 checks passed`.

### PG-9083S on Windows

Pair the pad in PC mode before starting the program. Hold Home and X until the LED flashes, then add it in Windows Bluetooth settings. Android or DirectInput mode is invisible to this program.

From `spot_cone_controller`:

```powershell
.\.venv\Scripts\python main.py --mock-dispenser --gamepad
```

Open http://127.0.0.1:8000. The controller card should say `Xbox 360 Controller`. Stick numbers should move when you push the sticks. Pull the right trigger and **Boost** should show Held with a percent. Startup still says `Mode: MOCK`. `--mock` forces the fake controller even if `--gamepad` is also present.

Then:

1. Type any Robot IP, leave the password blank, and press **Connect to Spot**.
2. Press **Stand**, then **Enable driving**.
3. Push the left stick to walk and the right stick to turn. Speed follows how far each stick is pushed. Hold the right trigger to raise the top speed. Releasing the sticks stops.
4. Hold A for half a second to drop one cone.
5. The right bumper stands, the left bumper sits, and Start stops.

| PG-9083S | PS5 | What it does |
| --- | --- | --- |
| Left stick | Left stick | Walk. Speed follows how far you push it. |
| Right stick | Right stick | Turn. |
| Right trigger | R2 | Hold to go faster. |
| Left bumper | L1 | Sit |
| Right bumper | R1 | Stand |
| A (bottom) | Cross | Hold for half a second to drop one cone. |
| Start | Options | Stop |

## Practice on the Jetson

Copy this repository onto the Jetson, or clone it:

```bash
git clone https://github.com/jtor5553/Spotinators-Fall-2026-Capstone.git
cd Spotinators-Fall-2026-Capstone/spot_cone_controller
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --mock-dispenser
```

On the Jetson itself, open http://127.0.0.1:8000.

From the Spot tablet, open `http://<jetson-ip>:8000`. The tablet only displays the page. Closing the tablet does not stop the program on the Jetson.

This first Jetson run is still mock mode. It does not move Spot or power the motor.

Before changing any network setting, run the read-only hardware check:

```bash
bash scripts/system_check.sh
```

Save the whole output. It reports whether Wi-Fi and Bluetooth hardware are actually installed. The Orin Nano Developer Kit does not include those radios unless a card or USB adapter was added.

## What the buttons do

| Control | What it does |
| --- | --- |
| Stand | Spot stands. On the real robot this is the first command that takes control. The right bumper (R1 on PS5) does the same thing. |
| Sit | Spot sits. The left bumper (L1 on PS5) does the same thing. |
| Stop | Speed goes to zero and the cone motor turns off. Spot stays in its current posture. Start (Options on PS5) does the same thing. |
| Enable driving | Arms the sticks. Required after Stand, and again after Resume. |
| Resume | Clears a stop. Does not start driving by itself. |
| Emergency stop | Stops immediately. There is no confirmation question. |
| Reset E-stop | Clears the software E-stop. Driving stays off. |
| Left stick | Forward, back, and sideways. Speed follows how far the stick is pushed. |
| Right stick | Rotate. Speed follows how far the stick is pushed. |
| Right trigger / R2 | Raises the top speed while it is held. A full pull doubles the normal cap. |
| Release the sticks | Speed goes to zero immediately. |
| A or Cross, held 0.5 seconds | Drops one cone. A tap does nothing. Holding the button does not drop more cones. |

The same list is on the operator page under **Controller buttons**.

After Stop, or after the controller disconnects, press **Resume** and then **Enable driving** before the sticks will move Spot again.

## Safety rules

Read this before the real robot is connected.

- The program starts disarmed. The motor starts off.
- Restarting the program does not continue an old move or an old motor command.
- Sticks do nothing until Spot is standing and driving is enabled.
- How far a stick is pushed sets the speed. With the right trigger released, the caps are 0.6 m/s forward, 0.4 m/s sideways, and 0.6 rad/s turning.
- A full right-trigger pull raises those caps to 1.2 m/s forward, 0.8 m/s sideways, and 1.2 rad/s turning. The program will not command faster than that.
- Releasing the sticks stops immediately. A command that is not refreshed also expires, and the watchdog stops the robot.
- If the gamepad disconnects, Spot stops and cone drops are disabled.
- Stop and Emergency stop are different buttons. Do not treat them as the same thing.
- The software E-stop does not replace Spot's physical E-stop, or the mushroom E-stop on the trailer. Those buttons must still cut power.
- Do the first real tests in a closed lot, not in traffic.
- The Spot password is typed on the tablet and kept in memory. Do not put it in `config.yaml`. Remembering the IP and username writes only those two fields to `config/operator.yaml` on that computer.

## Connect the real hardware

Do these one at a time, after the mock practice above works. Stay in a clear area with Spot's physical E-stop in reach.

### Spot

1. On the computer that will talk to Spot, while it still has internet, run `python -m pip install bosdyn-client`.
2. Start with `--real`, or set `system.mock_mode: false` in `spot_cone_controller/config/config.yaml`. `--mock` still forces practice mode if both are present.
3. Leave the controller mocked and the dispenser disabled for this test.
4. Plug the computer's Ethernet port into Spot.
5. Open the page. The username starts as `user2`. Type Spot's IP and password, then press Connect. Check **Remember IP and username on this computer** if the next start should fill those two fields in. The password is cleared from the page after each attempt.
6. Confirm the battery and posture. Then press Stand, Sit, and Stop.

A failed connection stays on the page. The usual causes are a disconnected Ethernet cable, the wrong IP, or the wrong password.

Connecting registers this program as Spot's software E-stop endpoint and allows motion. A hardware E-stop still latches the page until that button is released and you press Reset E-stop. Stand is the step that takes control of Spot. Connecting reads status and clears only the software endpoint.

### PS5 controller

Skip this if the system check said Bluetooth was not found.

1. Pair the DualSense to the Jetson once, with `bluetoothctl`.
2. Install the input library: `sudo apt-get install python3-evdev`.
3. In `config.yaml`, under `controller`, set `mock: false`.
4. Restart the program. The controller card should show the stick values before you enable driving. L1 sits, R1 stands, and R2 is the speed boost.

The Search paired button only lists controllers Linux already knows. It does not pair a new one. On Windows, skip this section and start with `--gamepad` instead.

### Cone motor

Do not enable the real motor until mock drops, the half-second hold, and Emergency stop have been practiced.

The trailer uses one motor on channel 1 of a Cytron MDD10A. Channel 2 is unused. Pin numbers stay empty until the wiring is finished. The program will not energize the motor while those pins are empty.

When the pins are known, set them in `config.yaml`, then set:

```yaml
dispenser:
  enabled: true
  mock: false
  dir_pin: 0
  pwm_pin: 0
```

Replace the zeros with the real header pins. Limit switches stay off unless both switch pins are installed.

The cone count starts at 4. Use minus, plus, or Reset when the trailer is reloaded. The count drops only after a drop finishes. A rejected or timed-out command does not change it.

### Cameras

After Spot is connected, the page lists picture cameras and shows one at a time. Depth and projected-depth sources stay off the page. When Spot reports `frontleft_fisheye_image`, that camera is selected first. The starting size is 640 by 480 at 5 frames per second. Try 10 frames per second only if the page stays responsive. Do not assume the mock names front, left, right, and rear exist on the real robot.

### Tablet Wi-Fi

Run `bash scripts/setup_hotspot.sh` first. If it says `Wi-Fi: NOT FOUND`, stop. There is nothing to configure.

When a Wi-Fi interface is present, create the network with the interface name and address you choose:

```bash
sudo bash scripts/setup_hotspot.sh --apply --interface wlan0 --address 192.168.50.1 --password 'choose-a-passphrase'
```

`192.168.50.1` is only an example. The tablet joins `SPOT-CONE-CONTROL` and opens `http://<that-address>:8000`. Internet is not required.

### Start when the Jetson boots

Edit the user name in `spot_cone_controller/deploy/spot-cone-controller.service`, then:

```bash
sudo cp deploy/spot-cone-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now spot-cone-controller.service
```

Leave `mock_mode: true` until a supervised test has passed. A crash restart comes back disarmed, with the motor off.

## Tests

From the `spot_cone_controller` folder, with the virtual environment activated or by calling its Python directly:

```powershell
.\.venv\Scripts\python -m pytest
```

```bash
.venv/bin/python -m pytest
```

## If something looks wrong

| What you see | What to do |
| --- | --- |
| `Mode: MOCK` | This is practice mode. Set `mock_mode: false` only when Spot is connected on purpose. |
| Dispenser says DISABLED | Start with `--mock-dispenser`, or set `dispenser.enabled: true` for a mock practice. |
| The page does not open | The PowerShell or Jetson window must still be running `main.py`. Use http://127.0.0.1:8000 on that same computer. |
| SDK is not installed | On the Jetson, run `python3 -m pip install bosdyn-client`. |
| evdev is not installed | Expected on Windows. Use `--gamepad` there. On the Jetson, install `python3-evdev` before using the PS5 controller. |
| Gamepad not found | Put the PG-9083S in PC mode (hold Home and X) and pair it again in Bluetooth settings. Restart with `--gamepad`. |
| Sticks move on the card but Spot stays still | Press Stand, then Enable driving. After Stop, press Resume and then Enable driving again. |
| Boost stays Released | Pull the right trigger. On the PS5 that trigger is R2. |
| Wi-Fi NOT FOUND | Do not set up a hotspot. The Jetson has no Wi-Fi radio in that result. |
| `$'\r': command not found` | The script has Windows line endings. On the Jetson run `sed -i 's/\r$//' scripts/system_check.sh` and try again. |
| Emergency stop will not clear | Press Reset E-stop, then Resume, then Enable driving. Also release Spot's physical E-stop if it is pressed. |

## What is included

```text
spot_cone_controller/     the program
  main.py                 starts the controller and the web page
  gui/                    the touchscreen page
  controller/             stick mapping, DualSense reader, Windows XInput reader
  spot/                   real Spot connection
  mocks/                  fake Spot and fake controller
  dispenser/              cone motor, mock motor, optional limit switches
  safety/                 stop, E-stop, and the watchdog
  config/                 settings. Do not store the Spot password here.
  scripts/                Jetson hardware check and optional hotspot
  deploy/                 startup service
  tests/                  mock tests
```

The page, the gamepad, and any future autonomy mode all send requests to one controller. That controller decides what is allowed. Autonomy, GPS routes, and automatic cone spacing are not in this version. Manual control remains the path those features would have to use later.
