import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_controller(tmp_path, dispenser_enabled=True):
    from core.app_controller import AppController
    from core.config import load_config

    config = load_config()
    config["system"]["mock_mode"] = True
    config["controller"]["mock"] = True
    config["dispenser"]["enabled"] = dispenser_enabled
    config["dispenser"]["mock"] = True
    config["logging"]["to_console"] = False
    config["logging"]["directory"] = str(tmp_path)
    config["_paths"]["operator"] = str(Path(tmp_path) / "operator.yaml")
    config["spot"]["hostname"] = ""
    config["spot"]["username"] = ""
    config["saved_password"] = ""
    return AppController(config, verbose=False)
