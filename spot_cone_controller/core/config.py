"""Load defaults, then the operator config. Passwords are never kept."""

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read_yaml(path):
    if not Path(path).is_file():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return data


def deep_merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(config_path=None):
    defaults = _read_yaml(ROOT / "config" / "defaults.yaml")
    user_path = Path(config_path) if config_path else ROOT / "config" / "config.yaml"
    user = _read_yaml(user_path)
    password_in_config = "password" in (user.get("spot") or {})
    if password_in_config:
        user = copy.deepcopy(user)
        user["spot"].pop("password", None)
    config = deep_merge(defaults, user)
    config["spot"].pop("password", None)
    config["_password_in_config"] = password_in_config
    config["_paths"] = {"root": str(ROOT), "config": str(user_path)}

    operator_path = ROOT / config["system"].get("operator_file", "config/operator.yaml")
    config["_paths"]["operator"] = str(operator_path)
    if operator_path.is_file():
        saved = _read_yaml(operator_path).get("spot") or {}
        if saved.get("hostname"):
            config["spot"]["hostname"] = str(saved["hostname"])
        if saved.get("username"):
            config["spot"]["username"] = str(saved["username"])
    return config


def save_operator_identity(config, hostname, username):
    """Remember the Spot IP and username. The password is not written."""
    path = Path(config["_paths"]["operator"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"spot": {"hostname": hostname, "username": username}}
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
    config["spot"]["hostname"] = hostname
    config["spot"]["username"] = username
