# Spot cone controller

Run the program from this folder. Pick the guide for the computer you are using.

- **[Windows setup](../WINDOWS_SETUP.md).** Practice the page and the PG-9083S.
- **[Jetson setup](../JETSON_SETUP.md).** The Orin Nano, the PS5 controller, Spot, and the cone motor.
- **[Project overview](../README.md).** What this repository is, and the safety rules.

## Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py --mock-dispenser
```

Open http://127.0.0.1:8000. The full click path and the gamepad steps are in the Windows guide.

## Jetson

```bash
sudo apt-get install -y python3-dev gcc
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-jetson.txt
bash scripts/system_check.sh
.venv/bin/python main.py --mock-dispenser
```

This first run does not move Spot or power the cone motor. Follow the Jetson guide before pairing the PS5 controller or changing `config/config.yaml`.
