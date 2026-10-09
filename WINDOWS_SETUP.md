# Windows setup

This is the practice computer. A Windows PC runs the same operator page you will use on the trailer. Spot and the cone motor stay mocked here. The trailer computer is the Jetson, and that setup is in [Jetson setup](JETSON_SETUP.md).

The on-screen title is **Spot Cone Placement System**. The page opens at http://127.0.0.1:8000. The Spot password is typed on the page. **Remember** stores the IP, username, and password in `config/operator.yaml`. Do not put the password in `config.yaml`.

## What you need

- Windows 10 or 11.
- Python 3, available as `python` in PowerShell. Check with `python --version`.
- This repository, already copied or cloned onto the PC.
- A PG-9083S gamepad, only if you want to drive with sticks. The page works without it.

The Windows install uses `requirements.txt`. It does not use `requirements-jetson.txt`. That file is for the Jetson, and `evdev` does not install on Windows.

## 1. Install and start

Open PowerShell in the repository folder, then run:

```powershell
cd spot_cone_controller
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py --mock --mock-dispenser
```

`--mock` keeps this run in practice. It does not stand Spot even if a password was remembered. The gamepad is still read.

Leave that window open. In a browser, open:

http://127.0.0.1:8000

The startup text should include `Mode: MOCK` and `Dispenser: READY`. If you start without `--mock-dispenser`, the dispenser stays `DISABLED` and cone drops are refused. That is the safe default.

Then:

1. Check **Mock mode**. Practice does not use a real address.
2. Type any numbers into Robot IP. The username can stay `user2`. Leave the password blank and press **Connect to Spot**.
3. Press **Stand**, then **Sit**, then **Stop**.
4. Press and hold **Hold to drop cone** for half a second. The count goes from 4 to 3. Holding longer does not drop a second cone.
5. Press **Emergency stop**. The page says EMERGENCY STOP ACTIVE immediately. Stand is refused until you press **Reset E-stop**.

Press Ctrl+C in PowerShell when you want to quit.

## 2. Check without a browser

From `spot_cone_controller`:

```powershell
.\.venv\Scripts\python main.py --self-test
```

The last line should say `25 / 25 checks passed`.

Run the automated tests the same way:

```powershell
.\.venv\Scripts\python -m pytest
```

## 3. Pair the PG-9083S

Skip this section if you are only using the buttons on the page.

The pad has to be in PC mode before the program starts. Android mode and DirectInput mode are invisible to this program.

1. Hold Home and X together until the LED flashes.
2. Open Windows Settings, then Bluetooth and devices, then Add device.
3. Select the pad when it appears.
4. Start the program:

```powershell
.\.venv\Scripts\python main.py --mock --mock-dispenser
```

Open http://127.0.0.1:8000. The controller card should say `Xbox 360 Controller`. That name is what Windows XInput reports for this pad. Stick numbers should move when you push the sticks. Pull the right trigger and **Boost** should show Held with a percent.

Startup still says `Mode: MOCK`. The real gamepad is read on every start. `--mock` selects practice Spot and does not switch back to the fake controller.

Then:

1. Check **Mock mode**. Type any Robot IP, leave the password blank, and press **Connect to Spot**.
2. Press **Stand**, then **Enable driving**.
3. Push the left stick to walk and the right stick to turn. Speed follows how far each stick is pushed. Hold the right trigger to raise the top speed. Releasing the sticks stops.
4. Hold A for half a second to drop one cone.
5. The right bumper stands, the left bumper sits, and Start stops.

After Stop, or after the controller disconnects, press **Resume** and then **Enable driving** before the sticks will move the mock robot again.

| PG-9083S | PS5 on the Jetson | What it does |
| --- | --- | --- |
| Left stick | Left stick | Walk. Speed follows how far you push it. |
| Right stick | Right stick | Turn. |
| Right trigger | R2 | Hold to go faster. |
| Left bumper | L1 | Sit |
| Right bumper | R1 | Stand |
| A (bottom) | Cross | Hold for half a second to drop one cone. |
| Start | Options | Stop |

The same list is on the operator page under **Controller buttons**.

## 4. What the page buttons do

| Control | What it does |
| --- | --- |
| Stand | The robot stands. On a manual connect this is the first command that takes control. A process start with a remembered password stands by itself. |
| Sign out | Powers the motors off, releases the lease, and returns to the login page. |
| Sit | The robot sits. |
| Stop | Speed goes to zero and the cone motor turns off. The robot stays in its current posture. |
| Enable driving | Arms the sticks. Required after Stand, and again after Resume. |
| Resume | Clears a stop. Does not start driving by itself. |
| Emergency stop | Stops immediately. There is no confirmation question. |
| Reset E-stop | Clears the software E-stop. Driving stays off. |
| Hold to drop cone | Hold for half a second. A tap does nothing. Holding longer does not drop a second cone. |

With the right trigger released, the caps are 0.6 m/s forward, 0.4 m/s sideways, and 0.6 rad/s turning. A full right-trigger pull raises those caps to 1.2 m/s forward, 0.8 m/s sideways, and 1.2 rad/s turning.

## 5. Stay in practice mode

This PC does not power the cone motor and does not use the PS5 controller. Bluetooth DualSense setup, Spot's Ethernet connection, the tablet hotspot, and starting at boot are all in [Jetson setup](JETSON_SETUP.md).

Leave **Mock mode** checked for practice. Do not point this practice PC at the real robot unless a supervised test says to. If that test is on Windows, install the SDK into this same virtual environment while the PC has internet:

```powershell
.\.venv\Scripts\python -m pip install bosdyn-client
.\.venv\Scripts\python main.py
```

Leave **Mock mode** unchecked, type the IP and password, and press **Connect to Spot**. Check **Remember** if the next time this program starts should connect, take the lease, and stand. Driving stays off until **Enable driving**. Start with `--mock` when a run must stay in practice even though a password is saved.

## If something looks wrong

| What you see | What to do |
| --- | --- |
| `python` is not recognized | Install Python 3 and enable "Add python.exe to PATH", then open a new PowerShell window. |
| `Mode: MOCK` | This is practice mode. That is what this PC should say. |
| Dispenser says DISABLED | Start with `--mock-dispenser`. |
| The page does not open | The PowerShell window must still be running `main.py`. Use http://127.0.0.1:8000 on this PC. |
| evdev is not installed | Expected on Windows. The PG-9083S is read through XInput. Do not install the Jetson requirements file here. |
| Gamepad not found | Put the PG-9083S in PC mode (hold Home and X) and pair it again in Bluetooth settings, then start the program again. |
| The controller card stays on the mock controller | `controller.mock` is true in the config. The default is false. `--mock` does not select the fake controller. |
| Sticks move on the card but the robot stays still | Press Stand, then Enable driving. After Stop, press Resume and then Enable driving again. |
| Boost stays Released | Pull the right trigger. |
| Emergency stop will not clear | Press Reset E-stop, then Resume, then Enable driving. |
