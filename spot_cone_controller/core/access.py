"""Local operator access code. This is not the Spot password."""

import os
import secrets
from pathlib import Path

COOKIE_NAME = "spot_operator"
PUBLIC_GET = {"/", "/favicon.ico"}


def access_path(config):
    operator = Path(config["_paths"]["operator"])
    return operator.with_name("operator.access")


def ensure_access_code(config):
    path = access_path(config)
    if path.is_file():
        code = path.read_text(encoding="utf-8").strip()
        if code:
            return code
    code = f"{secrets.randbelow(100_000_000):08d}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return code


def codes_match(stored, supplied):
    stored = (stored or "").strip()
    supplied = (supplied or "").strip()
    if not stored or len(stored) != len(supplied):
        return False
    return secrets.compare_digest(stored, supplied)


def request_allowed(method, path, cookie, expected):
    if method == "POST" and path == "/api/access":
        return True
    if method == "GET" and (path in PUBLIC_GET or path.startswith("/static/")):
        return True
    return codes_match(expected, cookie)
