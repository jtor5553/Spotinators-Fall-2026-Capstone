# Jetson Orin Nano setup

This is the setup for the trailer computer. An NVIDIA Jetson Orin Nano runs the program. The Spot tablet is only a touchscreen. It opens the page in a browser. It does not drive the robot, and closing the tablet does not stop the program.

Do these steps in order. Stop at the first check that fails. The program starts disarmed, with the cone motor off. Leave `mock_mode: true` until a supervised test in a clear area has passed. Spot's physical E-stop, and the mushroom E-stop on the trailer, still have to cut power. The software E-stop does not replace them.

The Spot password is typed on the page and kept in memory. Do not put it in `config.yaml` or in this guide.

The short Windows practice and the button list are in [README.md](README.md).

## What you need

- A Jetson Orin Nano with a monitor, keyboard, and mouse, or an SSH session, for the first setup.
- JetPack 6 if the PS5 controller will connect over Bluetooth. JetPack 6 includes the `hid-playstation` kernel module. JetPack 5 usually does not, and this program cannot add that driver.
- The Orin Nano Developer Kit does not include Wi-Fi or Bluetooth unless a card or a USB adapter was added. Ethernet to Spot does not need those radios.
- A PS5 DualSense, already charged.
- An Ethernet cable for Spot, used only in the Spot section below.
- Internet on the Jetson once, for `apt` and `pip`. After that, the operator page does not need internet.

## 1. Confirm the board

On the Jetson:

```bash
cat /proc/device-tree/model
cat /etc/nv_tegra_release
uname -r
python3 --version
```

`/proc/device-tree/model` should name an Orin Nano. Remember the kernel version. You will compare it with the hardware check in step 4.

## 2. Install Git and clone the repository

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip python3-dev gcc
git clone https://github.com/jtor5553/Spotinators-Fall-2026-Capstone.git
cd Spotinators-Fall-2026-Capstone/spot_cone_controller
```

`python3-dev` and `gcc` are required so `evdev` can build inside the virtual environment. Do not install `evdev` with `apt` and expect the virtual environment to see it. The environment below installs it with `pip`.

If a shell script later fails with `$'\r': command not found`, the file has Windows line endings. From `spot_cone_controller` run:

```bash
sed -i 's/\r$//' scripts/system_check.sh scripts/setup_hotspot.sh
```

## 3. Create the virtual environment

Stay in `spot_cone_controller`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-jetson.txt
.venv/bin/python -c "import evdev; print('evdev ok')"
```

The last line should print `evdev ok`. `requirements-jetson.txt` installs the same packages as Windows, plus `evdev`. The Windows `requirements.txt` file does not include `evdev`.

## 4. Run the hardware check before changing anything

This check only reads the board. It does not install packages, pair a controller, or change Wi-Fi or Bluetooth.

```bash
bash scripts/system_check.sh
```

Save the whole output. Read these lines before continuing:

| Line | What to do |
| --- | --- |
| `Ethernet: AVAILABLE` | You can cable Spot later. `NOT FOUND` means that port is missing. |
| `Wi-Fi: NOT FOUND` | Do not create a hotspot. There is no radio to configure. |
| `Bluetooth adapter: NOT FOUND` | Skip the PS5 section. The page can still run in mock mode. |
| `hid-playstation: NOT FOUND` | Bluetooth DualSense will not appear. Do not continue the PS5 steps. JetPack 6 includes this module. JetPack 5 usually does not. |
| `hid-playstation: AVAILABLE, not loaded yet` | Continue. The module loads when the controller connects. |
| `input group: NO` | Expected before step 6. The DualSense cannot be read until this is `YES` and you have logged in again. |
| `bluetooth group: NO` | Expected before step 6. |
| `evdev (venv): IMPORTABLE` | Step 3 worked. `NOT IMPORTABLE` or `NO VENV` means repeat step 3 from `spot_cone_controller`. |
| `DualSense gamepad node: NOT FOUND` | Expected until the controller is connected. |

## 5. Open the page in mock mode

This run does not move Spot and does not power the cone motor.

```bash
.venv/bin/python main.py --mock-dispenser
```

Leave that terminal open. On the Jetson, open a browser to:

http://127.0.0.1:8000

The startup text should include `Mode: MOCK` and `Dispenser: READY`. Then:

1. Type any numbers into Robot IP. Mock mode does not use a real address. The username can stay `user2`.
2. Leave the password blank and press **Connect to Spot**.
3. Press **Stand**, then **Sit**, then **Stop**.
4. Press and hold **Hold to drop cone** for half a second. The count goes from 4 to 3. Holding longer does not drop a second cone.
5. Press **Emergency stop**. The page says EMERGENCY STOP ACTIVE immediately. Stand is refused until you press **Reset E-stop**.

Press Ctrl+C in the terminal when you want to quit. Without `--mock-dispenser`, the dispenser stays `DISABLED` and cone drops are refused.

Check the same path without a browser:

```bash
.venv/bin/python main.py --self-test
```

The last line should say `25 / 25 checks passed`.

## 6. Pair the PS5 DualSense

Skip this whole section if the hardware check said Bluetooth was `NOT FOUND`, or if `hid-playstation` was `NOT FOUND`.

The controller uses Bluetooth only. Pair it once. After that, the program connects a controller that is already paired. It does not scan, pair, or trust a new one.

1. On the DualSense, hold the PS button and the Create button together until the light bar flashes. Create is the small button to the left of the touchpad.
2. On the Jetson:

```bash
bluetoothctl
```

3. At the `bluetoothctl` prompt:

```text
power on
agent on
default-agent
scan on
```

4. Wait until a device appears named DualSense or Wireless Controller. Copy its address. It looks like `AA:BB:CC:DD:EE:FF`. Then, using that address:

```text
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
scan off
quit
```

`trust` is what lets the Jetson connect again after a reboot. `pair` is only done this once.

5. Let this user read input devices, and install the udev rule. From `spot_cone_controller`:

```bash
sudo usermod -aG input,bluetooth "$USER"
sudo cp deploy/99-dualsense.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

The rule matches DualSense nodes with vendor `054c` and product `0ce6`, and gives them to the `input` group.

6. Log out of the Jetson and log back in. A group change does not apply to a terminal that was already open. You can confirm with:

```bash
id -nG
```

`input` and `bluetooth` should both be in the list.

7. Connect the controller if it is not already connected, then run the hardware check again:

```bash
bash scripts/system_check.sh
```

`input group` and `bluetooth group` should be `YES`. `DualSense gamepad node` should name the controller. A line that only mentions Motion Sensors or Touchpad does not count. Those nodes are not the gamepad.

8. Start practice with the real controller. Spot and the cone motor stay mocked:

```bash
.venv/bin/python main.py --mock-dispenser --gamepad
```

Open http://127.0.0.1:8000. The controller card should show the DualSense name, not a mock controller. Stick numbers should move before you enable driving. Then:

1. Type any Robot IP, leave the password blank, and press **Connect to Spot**.
2. Press **Stand**, then **Enable driving**.
3. Push the left stick to walk and the right stick to turn. Releasing the sticks stops.
4. Pull R2. **Boost** should show Held with a percent.
5. Hold Cross for half a second to drop one cone.
6. R1 stands, L1 sits, and Options stops.

Startup still says `Mode: MOCK`. `--gamepad` turns the mock controller off for that run. Setting `controller.mock: false` in `config/config.yaml` does the same thing on every start. `--mock` forces the fake controller even if `--gamepad` is also present.

The Search paired button on the page only lists controllers Linux already knows. It does not pair a new one.

If the card says the DualSense is present but cannot be read, the user is not in the `input` group in this login. Repeat the `usermod` line, install the udev rule again, and log out and back in.

## 7. Connect Spot

Do this only after mock Stand, Sit, Stop, and Emergency stop have been practiced. Stay in a clear area with Spot's physical E-stop in reach. Leave the dispenser disabled for this test.

1. While the Jetson still has internet, install the Spot SDK into the same virtual environment:

```bash
.venv/bin/python -m pip install bosdyn-client
```

2. Plug the Jetson's Ethernet port into Spot.
3. Start the program so it will use the real robot. Keep the dispenser off:

```bash
.venv/bin/python main.py --real --gamepad
```

`--real` sets mock mode off for that run. `--mock` still forces practice mode if both are present. You can instead set `system.mock_mode: false` in `config/config.yaml`. Do that only when a supervised test is the goal. The boot service in step 10 does not pass `--real`, so a crash restart stays in mock mode until that file is changed.

4. Open the page. The username starts as `user2`. Type Spot's IP and password, then press **Connect to Spot**. Check **Remember IP and username on this computer** if the next start should fill those two fields in. That writes only the IP and username to `config/operator.yaml` on that Jetson. The password is cleared from the page after each attempt.
5. Confirm the battery and posture. Then press **Stand**, **Sit**, and **Stop**.

A failed connection stays on the page. The usual causes are a disconnected Ethernet cable, the wrong IP, or the wrong password.

Connecting registers this program as Spot's software E-stop endpoint and allows motion. A hardware E-stop still latches the page until that button is released and you press **Reset E-stop**. Stand is the step that takes control of Spot. If Spot drops the control lease, the page says so. Press **Stand** to take control again.

After Stop, or after the controller disconnects, press **Resume** and then **Enable driving** before the sticks will move Spot again.

## 8. Cone motor

Do not enable the real motor until mock drops, the half-second hold, and Emergency stop have been practiced.

The trailer uses one motor on channel 1 of a Cytron MDD10A. Channel 2 is unused. Direction and PWM pin numbers stay empty until the wiring is finished. The program will not energize the motor while those pins are empty.

`Jetson.GPIO` comes with JetPack. This program uses BOARD pin numbers, which are the physical header pin numbers, not the BCM numbers printed on some breakout boards.

When the pins are known, set them in `config/config.yaml`, then set:

```yaml
dispenser:
  enabled: true
  mock: false
  dir_pin: 0
  pwm_pin: 0
```

Replace the zeros with the real header pins. Limit switches stay off unless both switch pins are installed. If the page says `Jetson.GPIO` is not available, the motor was not energized. On JetPack that library is already installed for the system Python. If the virtual environment cannot import it, create the environment again with access to the system packages:

```bash
deactivate 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv --system-site-packages
.venv/bin/python -m pip install -r requirements-jetson.txt
```

If GPIO permission is denied, add the user to the `gpio` group, then log out and back in:

```bash
sudo usermod -aG gpio "$USER"
```

The cone count starts at 4. Use minus, plus, or Reset when the trailer is reloaded. The count drops only after a drop finishes. A rejected or timed-out command does not change it.

## 9. Cameras

After Spot is connected, the page lists picture cameras and shows one at a time. Depth and projected-depth sources stay off the page. When Spot reports `frontleft_fisheye_image`, that camera is selected first. The starting size is 640 by 480 at 5 frames per second. Try 10 frames per second only if the page stays responsive. Do not assume the mock names front, left, right, and rear exist on the real robot.

Change the rate in `config/config.yaml` under `camera` only after the page has already shown a picture at 5 frames per second.

## 10. Tablet Wi-Fi

Skip this if the hardware check said `Wi-Fi: NOT FOUND`.

From `spot_cone_controller`, see the radios without changing them:

```bash
bash scripts/setup_hotspot.sh
```

If it says `Wi-Fi: NOT FOUND`, stop. There is nothing to configure.

When a Wi-Fi interface is present, create the network with the interface name and address you choose. `192.168.50.1` is only an example. The password must be at least 8 characters.

```bash
sudo bash scripts/setup_hotspot.sh --apply --interface wlan0 --address 192.168.50.1 --password 'choose-a-passphrase'
```

The tablet joins `SPOT-CONE-CONTROL` and opens `http://<that-address>:8000`. Confirm the address with:

```bash
ip addr show wlan0
```

Internet is not required for the tablet.

## 11. Start when the Jetson boots

Edit `deploy/spot-cone-controller.service` before copying it.

Replace `REPLACE_WITH_JETSON_USERNAME` in the `User` line and in both paths. The paths must be the real `spot_cone_controller` folder. If you cloned into the home directory, that folder is:

```text
/home/YOUR_USER/Spotinators-Fall-2026-Capstone/spot_cone_controller
```

The service waits for Bluetooth, runs the virtualenv Python with `--gamepad`, and adds the `input` and `bluetooth` groups. It does not pass `--real` or `--mock-dispenser`. Spot stays in mock mode until `mock_mode` is changed in `config.yaml`. A crash restart comes back disarmed, with the motor off.

```bash
sudo cp deploy/spot-cone-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now spot-cone-controller.service
sudo systemctl status spot-cone-controller.service
```

If the service fails, read the last log lines:

```bash
journalctl -u spot-cone-controller.service -n 50 --no-pager
```

The usual causes are a username or path that was not replaced, a virtual environment that was created in a different folder, or a user who is not in the `input` group.

## Order for a supervised test

1. Mock page, no controller. Step 5.
2. Mock page with the DualSense. Step 6.
3. Real Spot, dispenser still disabled. Step 7. Stand, sit, and stop only.
4. Real Spot with driving enabled, in a closed lot, not in traffic.
5. Real cone motor last. Step 8.

## If something looks wrong

| What you see | What to do |
| --- | --- |
| `Mode: MOCK` | This is practice mode. Set `mock_mode: false`, or start with `--real`, only when Spot is connected on purpose. |
| Dispenser says DISABLED | Start with `--mock-dispenser`, or set `dispenser.enabled: true` for a mock practice. |
| The page does not open | The terminal or the systemd service must still be running `main.py`. On the Jetson use http://127.0.0.1:8000. From the tablet use the Jetson's address and port 8000. |
| `evdev (venv): NOT IMPORTABLE` | From `spot_cone_controller`, repeat step 3. |
| `hid-playstation: NOT FOUND` | Bluetooth DualSense will not appear. Do not continue the PS5 steps. |
| DualSense is present but cannot be read | Add the user to the `input` group, install `deploy/99-dualsense.rules`, then log out and back in. |
| DualSense not found | Pair it once, trust it, and start with `--gamepad`. The program ignores motion-sensor and touchpad nodes. |
| Sticks move on the card but Spot stays still | Press Stand, then Enable driving. After Stop, press Resume and then Enable driving again. |
| Boost stays Released | Pull R2. |
| SDK is not installed | Run `.venv/bin/python -m pip install bosdyn-client` while the Jetson has internet. |
| Wi-Fi NOT FOUND | Do not set up a hotspot. |
| Emergency stop will not clear | Press Reset E-stop, then Resume, then Enable driving. Also release Spot's physical E-stop if it is pressed. |
