"""Discover an installed Hearthstone directory for game audio."""

from __future__ import annotations

import os
from pathlib import Path


def detect_install(custom_path: Path | None = None) -> Path | None:
    """Return a valid custom path or the first standard Windows install."""
    if custom_path is not None and custom_path.exists():
        return custom_path
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        root = os.environ.get(variable)
        if not root:
            continue
        candidate = Path(root) / "Hearthstone"
        if candidate.exists():
            return candidate
    return None
