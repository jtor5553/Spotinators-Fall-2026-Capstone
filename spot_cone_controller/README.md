# Spot cone controller

Run the program from this folder. Pick the guide for the computer you are using.

- **[Windows setup](../WINDOWS_SETUP.md).** Practice the page and the PG-9083S.
- **[Jetson setup](../JETSON_SETUP.md).** The Orin Nano, the Unitree R3-1 remote, Spot, and the cone motor.
- **[Unitree R3 Bluetooth](../UNITREE_R3_BLUETOOTH.md).** RFCOMM pairing and R3-1 button map.
- **[Project overview](../README.md).** What this repository is, and the safety rules.

Mock Spot is selected only with the **Mock mode** checkbox on the connect page. There is no `--mock` flag.

## Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

Open http://127.0.0.1:8000. Check **Mock mode**, connect with any IP, then practice Stand / Sit / drop. The full click path and the gamepad steps are in the Windows guide.

## Jetson

```bash
sudo apt-get install -y python3-dev gcc
python3 -m venv .venv --system-site-packages
.venv/bin/python -m pip install -r requirements-jetson.txt
bash scripts/system_check.sh
.venv/bin/python main.py
```

Create the venv with `--system-site-packages` so `gpiod` / Jetson packages import. Check **Mock mode** on the page to practice without Spot; the cone motor still uses DIR pin 13 and PWM pin 32 when those pins are set in `config/config.yaml`. Lab Jetson config uses `controller.type: unitree_r3` for the Unitree R3-1 remote — follow the Jetson guide and [UNITREE_R3_BLUETOOTH.md](../UNITREE_R3_BLUETOOTH.md) before testing sticks.
