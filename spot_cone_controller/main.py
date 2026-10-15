"""Startup, banner, and the local web server."""

import argparse
import signal
import sys

from core.access import ensure_access_code
from core.app_controller import AppController
from core.config import load_config
from gui.server import create_app


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Spot cone placement controller")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Practice with mock Spot and skip the saved-credential startup",
    )
    parser.add_argument("--mock-dispenser", action="store_true", help="Enable the mock cone dispenser")
    parser.add_argument("--self-test", action="store_true", help="Run the mock manual-operation checks and exit")
    parser.add_argument("--config", default=None, help="Path to a config YAML file")
    return parser.parse_args(argv)


def apply_args(config, args):
    if args.mock:
        config["system"]["mock_mode"] = True
        config["_skip_auto_start"] = True
    if args.mock_dispenser:
        config["dispenser"]["mock"] = True
        config["dispenser"]["enabled"] = True
    return config


def print_banner(controller):
    info = controller.describe()
    print("===================================")
    print("Spot Cone Placement Controller")
    print("===================================")
    print()
    print(f"Version: {controller.config['system']['version']}")
    print()
    print("Starting system...")
    print()
    print(f"Mode: {info['mode']}")
    print(f"Spot: {info['spot']}")
    print(f"Controller: {info['controller']}")
    print(f"Dispenser: {info['dispenser']}")
    print("Web Interface: STARTING")
    print()
    print(f"Operator access code: {ensure_access_code(controller.config)}")
    print("Type this code on the operator page. It is not the Spot password.")
    print()
    print("System ready.")


def main(argv=None):
    args = parse_args(argv)
    config = apply_args(load_config(args.config), args)
    if args.self_test:
        from core.scenario import run_scenario

        return 0 if run_scenario(verbose=True) else 1

    controller = AppController(config, verbose=True)
    controller.startup()
    print_banner(controller)

    def _stop(signum, frame):
        del signum, frame
        controller.shutdown()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    import uvicorn

    network = config["network"]
    uvicorn.run(
        create_app(controller),
        host=network.get("gui_host", "0.0.0.0"),
        port=int(network.get("gui_port", 8000)),
        log_level="info",
    )
    controller.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
