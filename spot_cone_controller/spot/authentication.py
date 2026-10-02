"""Spot username/password login. The password is not stored."""

from core.exceptions import SpotConnectionError


def authenticate(robot, username, password, timeout_sec=10):
    try:
        robot.authenticate(username, password)
        robot.time_sync.wait_for_sync(timeout_sec=timeout_sec)
    except Exception as exc:
        text = str(exc)
        if password:
            text = text.replace(password, "***")
        raise SpotConnectionError(text) from exc
