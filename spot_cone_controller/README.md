# Spotinators Fall 2026 Capstone

Run the program from this folder. The setup guide, safety rules, and Jetson steps are in the repository guide: [Spotinators Fall 2026 Capstone](../README.md).

## Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py --mock-dispenser
```

Open http://127.0.0.1:8000. Type any robot IP, press Connect to Spot, then try Stand, Sit, Stop, and a half-second cone drop.

Check without the browser:

```powershell
.\.venv\Scripts\python main.py --self-test
```

## Jetson

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --mock-dispenser
bash scripts/system_check.sh
```

The first run is mock mode. It does not move Spot or power the cone motor. Follow the repository guide before changing `config/config.yaml`.
