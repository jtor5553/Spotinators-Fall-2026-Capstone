"""Rotating logs so a long run cannot fill the Jetson disk."""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _RedactFilter(logging.Filter):
    def filter(self, record):
        text = record.getMessage()
        text = re.sub(r"(?i)(password\s*[=:]\s*)(\S+)", r"\1***", text)
        record.msg = text
        record.args = ()
        return True


def setup_logging(config, root):
    logger = logging.getLogger("spot_cone")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    logger.addFilter(_RedactFilter())

    directory = Path(config.get("directory", "logs"))
    if not directory.is_absolute():
        directory = Path(root) / directory
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "spot_cone.log"

    formatter = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=int(config.get("max_bytes", 1_000_000)),
        backupCount=int(config.get("backup_count", 5)),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if config.get("to_console", True):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
    return logger


def flush_logs():
    logger = logging.getLogger("spot_cone")
    for handler in logger.handlers:
        handler.flush()
