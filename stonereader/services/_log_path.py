"""Discover the path to the live Hearthstone Power.log file (D-12).

Strategy (must call every tick — see Pitfall 1 in 02-RESEARCH.md):
  1. Use install_dir from caller (typically derived from running process exe).
  2. Else read HKLM\\SOFTWARE\\Blizzard\\Hearthstone\\InstallPath via winreg.
  3. Pick newest Logs/Hearthstone_*/Power.log subdirectory by mtime.
  4. Fall back to flat Logs/Power.log.

Hearthstone creates a fresh ``Logs/Hearthstone_YYYY_MM_DD_HH_MM_SS/`` directory
each session, so callers MUST re-invoke ``discover_power_log_path()`` after a
process restart rather than caching the returned path.

T-2-01 (path traversal): inputs come from either the running Hearthstone
process's own ``exe()`` path or the user's HKLM registry — both trust
boundaries owned by the user. This module only READS filesystem paths;
it never opens, writes, or executes them. Subdirectory iteration filters by
``startswith("Hearthstone_")`` rather than glob, so traversal entries (``..``)
are excluded.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SUBDIR_PREFIX = "Hearthstone_"
_POWER_LOG_NAME = "Power.log"
_LOGS_DIR_NAME = "Logs"


def discover_power_log_path(install_dir: Optional[Path] = None) -> Optional[Path]:
    """Return absolute path to the live Power.log, or None if not found.

    Args:
        install_dir: The Hearthstone install directory (e.g.
            ``C:\\Program Files (x86)\\Hearthstone``). When ``None``, the
            registry is consulted (Windows only). Callers wanting D-12 step 1
            (derive from the running process exe) should resolve that
            themselves and pass the resulting Path.

    Returns:
        Absolute Path to the live ``Power.log`` if one can be located,
        otherwise ``None``.
    """
    if install_dir is None:
        install_dir = _path_from_registry()
    if install_dir is None:
        return None

    logs_dir = install_dir / _LOGS_DIR_NAME
    if not logs_dir.is_dir():
        return None

    latest = _newest_session_log(logs_dir)
    if latest is not None:
        return latest

    # Fallback: flat layout (older Hearthstone format).
    flat = logs_dir / _POWER_LOG_NAME
    return flat if flat.exists() else None


def _newest_session_log(logs_dir: Path) -> Optional[Path]:
    """Return ``Logs/Hearthstone_YYYY_MM_DD_HH_MM_SS/Power.log`` with newest mtime.

    Returns ``None`` when no matching subdirectory contains a Power.log.
    """
    candidates: list[tuple[float, Path]] = []
    try:
        entries = list(logs_dir.iterdir())
    except OSError as exc:
        logger.warning("could not list %s: %s", logs_dir, exc)
        return None

    for entry in entries:
        if not entry.is_dir():
            continue
        if not entry.name.startswith(_SUBDIR_PREFIX):
            continue
        power_log = entry / _POWER_LOG_NAME
        if not power_log.exists():
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, power_log))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _path_from_registry() -> Optional[Path]:
    """Read ``HKLM\\SOFTWARE\\Blizzard\\Hearthstone\\InstallPath``. Windows only.

    Returns ``None`` on non-Windows platforms or when the key is absent.
    Both 64-bit and 32-bit (WOW6432Node) hives are tried.
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return None
    for hive, subkey in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Blizzard\Hearthstone"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Blizzard\Hearthstone"),
    ):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "InstallPath")
                if value:
                    return Path(value)
        except OSError:
            continue
    return None
