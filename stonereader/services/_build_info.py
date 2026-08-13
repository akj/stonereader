"""Best-effort discovery of the running Hearthstone client build number.

HSReplay documents can carry the client build that produced their Power.log.
Blizzard writes that value to ``.build.info`` in the Hearthstone install root,
while the live log sits several directories below it. Keeping discovery in a
small UI-free service gives the replay recorder an injectable provider and
keeps filesystem and registry failures from ever blocking live tracking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from stonereader.services._log_path import discover_power_log_path


def read_build(log_path: Optional[Path]) -> Optional[int]:
    """Read ``BuildId`` from the nearest ancestor ``.build.info`` file.

    Blizzard's first line is a pipe-separated typed header such as
    ``BuildId!STRING:0``; the actual column name is the text before ``!``.
    Discovery is metadata enrichment only, so missing paths, malformed rows,
    decoding problems, and conversion errors all deliberately return ``None``.
    """
    if log_path is None:
        return None
    try:
        for parent in Path(log_path).parents:
            build_info = parent / ".build.info"
            if not build_info.is_file():
                continue
            lines = build_info.read_text(encoding="utf-8").splitlines()
            if len(lines) < 2:
                return None
            headers = [token.split("!", 1)[0] for token in lines[0].split("|")]
            values = lines[1].split("|")
            build_index = headers.index("BuildId")
            return int(values[build_index])
    except Exception:
        return None
    return None


def current_build() -> Optional[int]:
    """Return the live Hearthstone build, or ``None`` if it is undiscoverable."""
    try:
        return read_build(discover_power_log_path())
    except Exception:
        return None
