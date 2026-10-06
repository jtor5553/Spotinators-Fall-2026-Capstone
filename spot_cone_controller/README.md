# Spotinators Fall 2026 Capstone

Run the program from this folder. The setup guide, safety rules, and Jetson steps are in the repository guide: [Spotinators Fall 2026 Capstone](../README.md). The Orin Nano walkthrough is in [Jetson setup](../JETSON_SETUP.md).

## Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py --mock-dispenser
```

Open http://127.0.0.1:8000. Type any robot IP, press Connect to Spot, then try Stand, Sit, Stop, and a half-second cone drop.

To drive that same mock session with a PG-9083S, pair it in PC mode first: hold Home and X until the LED flashes, then add it in Windows Bluetooth settings. Android mode is invisible to this program. Start with:

```powershell
.\.venv\Scripts\python main.py --mock-dispenser --gamepad
```

The controller card should say `Xbox 360 Controller`. Push a stick to walk. The right trigger raises the top speed. A drops a cone, the right bumper stands, the left bumper sits, and Start stops. Startup still says `Mode: MOCK`. Use `--real` when the Ethernet cable is plugged into Spot. `--mock` forces practice mode.

Check without the browser:

```powershell
.\.venv\Scripts\python main.py --self-test
```

## Jetson

Follow [Jetson setup](../JETSON_SETUP.md) before changing `config/config.yaml`. The short first run is:

```bash
sudo apt-get install -y python3-dev gcc
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-jetson.txt
bash scripts/system_check.sh
.venv/bin/python main.py --mock-dispenser --gamepad
```

The first run does not move Spot or power the cone motor. `--gamepad` reads a paired PS5 DualSense. If the system check says `hid-playstation: NOT FOUND`, Bluetooth DualSense will not appear. Do not continue the PS5 steps. Follow the repository guide before changing `config/config.yaml`.
