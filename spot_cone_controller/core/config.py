"""Load defaults, then the operator config. config.yaml never keeps a password."""

import copy
import os
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


def secret_path_for(operator_path):
    """Password file beside the operator file. Git ignores it."""
    return Path(operator_path).with_suffix(".secret")


def _write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _read_secret(path):
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    return text


def _write_operator(path, payload):
    _write_private(path, yaml.safe_dump(payload, sort_keys=False))


def _take_legacy_password(operator_path, saved):
    """Move a password out of operator.yaml and into the secret file."""
    spot = saved.get("spot") or {}
    if "password" not in spot:
        return _read_secret(secret_path_for(operator_path))
    legacy = str(spot.pop("password") or "")
    saved["spot"] = spot
    _write_operator(operator_path, saved)
    secret_path = secret_path_for(operator_path)
    if legacy and not secret_path.is_file():
        _write_private(secret_path, legacy + "\n")
    return _read_secret(secret_path)


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
    config["saved_password"] = ""
    config["_paths"] = {"root": str(ROOT), "config": str(user_path)}

    operator_path = ROOT / config["system"].get("operator_file", "config/operator.yaml")
    config["_paths"]["operator"] = str(operator_path)
    if operator_path.is_file():
        saved = _read_yaml(operator_path)
        spot = saved.get("spot") or {}
        if spot.get("hostname"):
            config["spot"]["hostname"] = str(spot["hostname"])
        if spot.get("username"):
            config["spot"]["username"] = str(spot["username"])
        config["saved_password"] = _take_legacy_password(operator_path, saved)
    return config


def save_operator_identity(config, hostname, username, password):
    """Remember the Spot IP and username. The password goes in the secret file."""
    path = Path(config["_paths"]["operator"])
    _write_operator(path, {"spot": {"hostname": hostname, "username": username}})
    secret_path = secret_path_for(path)
    if password:
        _write_private(secret_path, password + "\n")
    elif secret_path.is_file():
        secret_path.unlink()
    config["spot"]["hostname"] = hostname
    config["spot"]["username"] = username
    config["saved_password"] = password or ""


def clear_operator_identity(config):
    """Forget a remembered Spot IP, username, and password."""
    path = Path(config["_paths"]["operator"])
    secret_path = secret_path_for(path)
    if path.is_file():
        path.unlink()
    if secret_path.is_file():
        secret_path.unlink()
    config["spot"]["hostname"] = ""
    config["spot"]["username"] = ""
    config["saved_password"] = ""
