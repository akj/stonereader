"""Detect whether Hearthstone.exe is running (D-03).

Used by GameTracker to auto-start polling and to derive the install dir for
Power.log path discovery (D-12 step 1). TTL-cached so per-tick cost stays
microsecond-level (Pitfall 2 in 02-RESEARCH.md).

The detector wraps psutil so the rest of the codebase never imports it
directly. ``clock`` injection lets tests use a FakeClock without monkeypatching
``time.monotonic``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)

HEARTHSTONE_EXE = "Hearthstone.exe"
DEFAULT_TTL_SECONDS = 2.0


class ProcessDetector:
    """Detect whether Hearthstone.exe is running, with TTL cache.

    Calling ``is_running()`` more than once within ``cache_ttl_seconds`` returns
    the cached result without re-enumerating processes. The first call ALWAYS
    scans (the constructor seeds ``_last_check`` with ``-inf`` so the very
    first comparison always exceeds the TTL).
    """

    def __init__(
        self,
        cache_ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = cache_ttl_seconds
        self._clock = clock
        self._last_check: float = -float("inf")
        self._last_result: Tuple[bool, Optional[psutil.Process]] = (False, None)

    def is_running(self) -> Tuple[bool, Optional[psutil.Process]]:
        """Return ``(running, process)``. Cached for ``cache_ttl_seconds``.

        ``process`` is the matching ``psutil.Process`` (so callers can call
        ``proc.exe()`` for install-dir derivation). When not running, the
        second tuple element is ``None``.
        """
        now = self._clock()
        if now - self._last_check < self._ttl:
            return self._last_result
        self._last_check = now

        target = HEARTHSTONE_EXE.lower()
        try:
            iterator = psutil.process_iter(["name"])
        except Exception:
            logger.exception("psutil.process_iter failed")
            self._last_result = (False, None)
            return self._last_result

        for proc in iterator:
            try:
                name = proc.info.get("name") or ""
                if name.lower() == target:
                    self._last_result = (True, proc)
                    return self._last_result
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process disappeared between enumeration and inspection;
                # skip it and keep scanning the rest.
                continue

        self._last_result = (False, None)
        return self._last_result

    def get_install_dir(self) -> Optional[Path]:
        """Return the parent directory of Hearthstone.exe, or None if not running.

        Used by ``_log_path.discover_power_log_path()`` per D-12 step 1.
        """
        running, proc = self.is_running()
        if not running or proc is None:
            return None
        try:
            return Path(proc.exe()).parent
        except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
            return None

    def invalidate_cache(self) -> None:
        """Force the next ``is_running()`` call to re-scan.

        Used by the tracker after a process-gone reset so the next tick
        immediately picks up a fresh Hearthstone restart instead of waiting
        the full TTL window.
        """
        self._last_check = -float("inf")
