"""Stdlib logging configuration for StoneReader (D-16).

Call configure_logging() exactly once at app entry (stonereader/__main__.py).

The root logger is configured with two handlers:
- RotatingFileHandler at ~/.stonereader/stonereader.log (2MB cap, 3 backups)
- StreamHandler for stdout (mirrors all messages)

Default level is INFO. Set STONEREADER_DEBUG=1 to enable DEBUG.

Idempotent: subsequent calls do not duplicate handlers. Tests can monkeypatch
LOG_DIR to redirect output to a temporary directory.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

LOG_DIR = Path.home() / ".stonereader"
LOG_FILE_NAME = "stonereader.log"


def configure_logging() -> None:
    """Configure the root logger. Idempotent — safe to call more than once."""
    LOG_DIR.mkdir(exist_ok=True)
    level = (
        logging.DEBUG if os.environ.get("STONEREADER_DEBUG") == "1" else logging.INFO
    )

    fmt = logging.Formatter(
        "%(asctime)s %(name)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    log_path = LOG_DIR / LOG_FILE_NAME
    if not any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers
    ):
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    # StreamHandler is the parent class of RotatingFileHandler, so explicitly
    # exclude RotatingFileHandler instances when checking for an existing
    # console handler.
    if not any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.handlers.RotatingFileHandler)
        for h in root.handlers
    ):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        root.addHandler(console_handler)
