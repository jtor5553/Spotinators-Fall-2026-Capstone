# Jetson Orin Nano setup

This is the setup for the trailer computer. An NVIDIA Jetson Orin Nano runs the program. The Spot tablet is only a touchscreen. It opens the page in a browser. It does not drive the robot, and closing the tablet does not stop the program. To stop it, see [Stop and start the program](#stop-and-start-the-program).

Do these steps in order. Stop at the first check that fails. The program starts disarmed, with the cone motor off. Leave `mock_mode: true` until a supervised test in a clear area has passed. Spot's physical E-stop, and the mushroom E-stop on the trailer, still have to cut power. The software E-stop does not replace them.

The Spot password is typed on the page. **Remember** stores it in `config/operator.secret`, which git ignores, and the page does not receive it again. Do not put it in `config.yaml` or in this guide. The page first asks for the operator access code printed when the program starts. That code is not the Spot password. On a Jetson that starts at boot, read it with `journalctl -u spot-cone-controller -n 80 --no-pager`.

Practice on a Windows PC is in [Windows setup](WINDOWS_SETUP.md). The project overview and safety rules are in [README.md](README.md).

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
.venv/bin/python main.py --mock --mock-dispenser
```

`--mock` keeps this run in practice. It does not stand Spot even if a password was remembered. The gamepad is still read.

Leave that terminal open. On the Jetson, open a browser to:

http://127.0.0.1:8000

The startup text should include `Mode: MOCK` and `Dispenser: READY`. Then:

1. Check **Mock mode**. Practice does not use a real address.
2. Type any numbers into Robot IP. The username can stay `user2`. Leave the password blank and press **Connect to Spot**.
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
.venv/bin/python main.py --mock --mock-dispenser
```

Open http://127.0.0.1:8000. The controller card should show the DualSense name, not a mock controller. Stick numbers should move before you enable driving. Then:

1. Check **Mock mode**. Type any Robot IP, leave the password blank, and press **Connect to Spot**.
2. Press **Stand**, then **Enable driving**.
3. Push the left stick to walk and the right stick to turn. Releasing the sticks stops.
4. Pull R2. **Boost** should show Held with a percent.
5. Hold Cross for half a second to drop one cone.
6. R1 stands, L1 sits, and Options stops.

Startup still says `Mode: MOCK`. The real gamepad is read on every start. `--mock` selects practice Spot and does not switch back to the fake controller. `controller.mock: false` in `config/config.yaml` is the default.

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
.venv/bin/python main.py
```

Leave **Mock mode** unchecked. `--mock` forces practice mode for that run and skips the saved-credential startup.

4. Open the page and type the operator access code from the terminal. The username starts as `user2`. Type Spot's IP and password, then press **Connect to Spot**. Check **Remember credentials on this machine** if the next time the program starts should connect, take the lease, and stand. That writes the IP and username to `config/operator.yaml` and the password to `config/operator.secret` on that Jetson. The password is not sent back to the page. This Connect does not stand by itself.
5. Confirm the battery and posture. Then press **Stand**, **Sit**, and **Stop**. **Sign out** powers the motors off, releases the lease, and returns to the login page. The robot stands again the next time the program starts, if the remembered identity is still there. Driving stays off until **Enable driving**.

A failed connection stays on the page. The usual causes are a disconnected Ethernet cable, the wrong IP, or the wrong password.

Connecting registers this program as Spot's software E-stop endpoint and allows motion. A hardware E-stop still latches the page until that button is released and you press **Reset E-stop**. A process start with a remembered password takes the lease and stands. If Spot drops the control lease, the page says so. Press **Stand** to take control again.

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

Leave `camera.resize_ratio` at `1.0`. This Spot refuses any other ratio, the log says `CAMERA FAILURE`, and the page lists the camera names with no picture. JPEG quality `50` is what keeps the frames small.

Change the rate in `config/config.yaml` under `camera` only after the page has already shown a picture at 5 frames per second.

## 10. Open the page on the Spot tablet

Use Spot's own Wi-Fi for this. The Jetson hotspot in the next section is only for a tablet that cannot join Spot's network.

The Jetson must be plugged into Spot with the Ethernet cable, and `main.py` must still be running. The page listens on port 8000 on every network interface. The tablet opens a normal web browser. It does not use the Spot drive app, and closing the browser does not stop the program.

1. On the Jetson, find the address on the Ethernet cable that goes to Spot. Spot itself is usually `192.168.80.3`, so the Jetson address is a different number on `192.168.80.0/24`.

```bash
ip -4 addr
```

Write that address down. Do not open `127.0.0.1` on the tablet. That address only works on the Jetson.

2. If the Spot cable has no IPv4 address, add one on Spot's network. Use the interface name from the command above if it is not `eth0`. Do not use `192.168.80.3`. That address is Spot.

```bash
sudo ip addr add 192.168.80.50/24 dev eth0
```

This lasts until the Jetson reboots. If the tablet cannot open the page after a reboot, run the command again.

3. On the Spot tablet, open Wi-Fi settings and connect to Spot's Wi-Fi. Use the network name and password configured on the robot. This is the same Wi-Fi the tablet already uses to reach Spot. It is not `SPOT-CONE-CONTROL`.

4. Open the tablet's web browser and go to the Jetson address from step 1, port 8000. For the example address above, that is:

```text
http://192.168.80.50:8000
```

The operator page should load. Type Spot's IP and password there when you are ready to connect to the robot. The Wi-Fi password and the Spot password are different.

5. If the browser cannot open the page, the tablet and the Jetson are not on the same network. Use the hotspot in the next section instead.

## 11. Tablet hotspot

Skip this if the tablet already opens the page over Spot's Wi-Fi. Also skip it if the hardware check said `Wi-Fi: NOT FOUND`.

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

## 12. Start when the Jetson boots

From `spot_cone_controller`, run:

```bash
sudo bash scripts/install_boot.sh
```

That installs `deploy/spot-cone-controller.service` with this user and this folder, enables it for every boot, and opens http://127.0.0.1:8000 in Chromium when the desktop logs in. Automatic login is already set for this Jetson, so the page comes up after a restart with nobody at the keyboard.

The service waits for Bluetooth, runs the virtualenv Python, and adds the `input` and `bluetooth` groups. It reads the real gamepad on every start. It does not pass `--mock` or `--mock-dispenser`. If an IP, username, and password were remembered, a start connects to the real robot, takes the lease, and stands. Driving stays disabled, and the cone motor stays off unless the dispenser was enabled in `config.yaml`. The operator access code is printed in the service log.

To install the service by hand, replace `REPLACE_WITH_JETSON_USERNAME` and `REPLACE_WITH_APP_DIR` in `deploy/spot-cone-controller.service`, then:

```bash
sudo cp deploy/spot-cone-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now spot-cone-controller.service
sudo systemctl status spot-cone-controller.service
```

Stop, start, and disable that system service with:

```bash
sudo systemctl stop spot-cone-controller.service
sudo systemctl start spot-cone-controller.service
sudo systemctl disable spot-cone-controller.service
```

Copy `deploy/spot-cone-browser.desktop` to `~/.config/autostart/` and replace `REPLACE_WITH_APP_DIR` with the real `spot_cone_controller` folder so the browser still opens.

If the service fails, read the last log lines:

```bash
journalctl -u spot-cone-controller.service -n 50 --no-pager
```

### Stop and start the program

Closing the browser, or closing the Spot tablet, leaves the program running. On this Jetson it is a login service named `spot-cone-controller.service` for the desktop user `asl_lab`. The unit file is `~/.config/systemd/user/spot-cone-controller.service`. The process is `spot_cone_controller/.venv/bin/python main.py`. It starts when that user logs in. There is no terminal window to close.

Run these commands on the Jetson, logged in as `asl_lab`. Stop sends a shutdown signal. The program powers the motors off and releases the lease.

```bash
systemctl --user stop spot-cone-controller.service
```

Start it again:

```bash
systemctl --user start spot-cone-controller.service
```

See whether it is running:

```bash
systemctl --user status spot-cone-controller.service
```

The service stays enabled, so the next login starts it again. To leave it stopped until you start it yourself:

```bash
systemctl --user disable spot-cone-controller.service
```

Turn automatic login start back on:

```bash
systemctl --user enable --now spot-cone-controller.service
```

Read its log:

```bash
journalctl --user -u spot-cone-controller.service -n 50 --no-pager
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
| `Mode: MOCK` | This is practice mode. Leave **Mock mode** unchecked to use the real robot. Start with `--mock` when this run must not stand a remembered robot. |
| Dispenser says DISABLED | Start with `--mock-dispenser`, or set `dispenser.enabled: true` for a mock practice. |
| The page does not open | The terminal or the systemd service must still be running `main.py`. On the Jetson use http://127.0.0.1:8000. From the tablet, use the Jetson's `192.168.80` address and port 8000 while the tablet is on Spot's Wi-Fi. |
| The program is still running after the browser closes | Stop the login service: `systemctl --user stop spot-cone-controller.service`. See [Stop and start the program](#stop-and-start-the-program). |
| Camera names are listed and the picture stays blank | Set `camera.resize_ratio` to `1.0` and restart `main.py`. This Spot rejects a smaller ratio. |
| Only walk and Stand work | Update to this version and restart `main.py`. On the controller card, R1 should say Held when you press it, L1 when you press sit, and Options when you press stop. Right-stick left and right turns. R2 is boost. Hold Cross for half a second to drop one cone. |
| `evdev (venv): NOT IMPORTABLE` | From `spot_cone_controller`, repeat step 3. |
| `hid-playstation: NOT FOUND` | Bluetooth DualSense will not appear. Do not continue the PS5 steps. |
| DualSense is present but cannot be read | Add the user to the `input` group, install `deploy/99-dualsense.rules`, then log out and back in. |
| DualSense not found | Pair it once and trust it, then start the program again. The program ignores motion-sensor and touchpad nodes. |
| Sticks move on the card but Spot stays still | Press Stand, then Enable driving. After Stop, press Resume and then Enable driving again. |
| Boost stays Released | Pull R2. |
| SDK is not installed | Run `.venv/bin/python -m pip install bosdyn-client` while the Jetson has internet. |
| Wi-Fi NOT FOUND | Do not set up a hotspot. |
| Emergency stop will not clear | Press Reset E-stop, then Resume, then Enable driving. Also release Spot's physical E-stop if it is pressed. |
