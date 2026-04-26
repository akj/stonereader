"""Hearthstone log.config bootstrap (D-11).

Idempotently ensures the [Power] section is present so Hearthstone writes
Power.log. Preserves all other sections written by other trackers (HDT,
Firestone) per Pitfall 5 — RawConfigParser does no % interpolation, and
optionxform=str preserves the case-sensitive key names that Hearthstone reads.
"""

from __future__ import annotations

import configparser
import logging
import os
from pathlib import Path
from typing import Optional

from stonereader.services._exceptions import ServicesError

logger = logging.getLogger(__name__)

REQUIRED_POWER_SECTION = {
    "LogLevel": "1",
    "FilePrinting": "True",
    "ConsolePrinting": "False",
    "ScreenPrinting": "False",
    "Verbose": "True",
}


def log_config_path() -> Path:
    """Return the canonical Windows path %LOCALAPPDATA%\\Blizzard\\Hearthstone\\log.config.

    On non-Windows hosts (or if LOCALAPPDATA is unset) returns a best-effort
    fallback under ~/AppData/Local so callers can still pass an explicit
    override during testing.
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        local_appdata = str(Path.home() / "AppData" / "Local")
    return Path(local_appdata) / "Blizzard" / "Hearthstone" / "log.config"


def ensure_log_config(path: Optional[Path] = None) -> bool:
    """Write or update the [Power] section in log.config. Return True if changed.

    - Idempotent: a second call with an already-correct file returns False.
    - Preserves all other sections (HDT, Firestone, etc.) — Pitfall 5.
    - Uses RawConfigParser to avoid % interpolation surprises.
    - Sets optionxform = str to preserve key case.

    Raises:
        ServicesError: If the file cannot be written (PermissionError, OSError,
            disk full, read-only filesystem, etc.).  Callers are responsible for
            catching this and surfacing an appropriate error to the user.
    """
    path = path or log_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    parser = configparser.RawConfigParser()
    parser.optionxform = str  # type: ignore[assignment]  # preserve key case
    if path.exists():
        parser.read(path, encoding="utf-8")

    changed = False
    if not parser.has_section("Power"):
        parser.add_section("Power")
        changed = True
    for key, value in REQUIRED_POWER_SECTION.items():
        if parser.get("Power", key, fallback=None) != value:
            parser.set("Power", key, value)
            changed = True

    if changed:
        try:
            with path.open("w", encoding="utf-8") as f:
                parser.write(f)
        except OSError as exc:
            logger.error("Failed to write log.config at %s: %s", path, exc)
            raise ServicesError(f"Cannot write log.config: {exc}") from exc
        logger.info("Updated log.config at %s", path)
    return changed
