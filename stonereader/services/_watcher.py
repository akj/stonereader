"""Watch Power.log via wx.Timer (D-01) — tail bytes, decode lines, detect rotation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional

import wx

from stonereader.services._line_reader import _LineReader

logger = logging.getLogger(__name__)

POLL_INTERVAL_MS = 150
MAX_BUFFERED_LINES = 100_000
BACKWARD_SCAN_CHUNK = 4096
BACKWARD_SCAN_MAX_BYTES = 1_048_576  # 1 MB cap
CREATE_GAME_NEEDLE = b"GameState.DebugPrintPower() - CREATE_GAME"


def _is_gamestate_line(line: str) -> bool:
    """Pre-filter at the watcher layer (defense in depth — hslog also filters)."""
    if len(line) < 22 or not line.startswith("D "):
        return False
    return "GameState." in line[:80]


class PowerLogWatcher:
    """Tail Power.log via a wx.Timer; emit lines via on_lines callback."""

    def __init__(
        self,
        path_provider: Callable[[], Optional[Path]],
        on_lines: Callable[[List[str]], None],
        on_reset: Callable[[], None],
    ) -> None:
        self._path_provider = path_provider
        self._on_lines = on_lines
        self._on_reset = on_reset
        self._timer: Optional[wx.Timer] = None
        self._line_reader = _LineReader()
        self._offset = 0
        self._current_path: Optional[Path] = None

    def start(self, parent: "wx.EvtHandler") -> None:
        """Create and start the Timer parented on `parent`. Pitfall 9: call AFTER frame.Show()."""
        if self._timer is not None:
            return  # already started
        self._timer = wx.Timer(parent)
        parent.Bind(wx.EVT_TIMER, lambda evt: self._tick(), self._timer)
        self._timer.Start(POLL_INTERVAL_MS)

    def stop(self) -> None:
        """Stop the Timer cleanly. D-19: idempotent."""
        if self._timer is not None:
            self._timer.Stop()
            self._timer = None
        self._line_reader.reset()
        self._offset = 0
        self._current_path = None

    def _tick(self) -> None:
        try:
            self._do_tick()
        except Exception:
            # D-04: log and continue — Timer keeps ticking on next interval.
            logger.exception("watcher tick failed")

    def _do_tick(self) -> None:
        path = self._path_provider()
        if path is None or not path.exists():
            if self._current_path is not None:
                self._handle_reset()
            return

        if path != self._current_path:
            # New log file (Hearthstone restart spawned a new subdirectory)
            self._handle_reset()
            self._current_path = path
            self._offset = self._maybe_backward_scan(path)

        try:
            size = path.stat().st_size
        except OSError:
            self._handle_reset()
            return

        if size < self._offset:
            # Truncation — Hearthstone rotated/reset (Pitfall 1, LOG-03)
            self._handle_reset()
            self._current_path = path
            self._offset = self._maybe_backward_scan(path)
            try:
                size = path.stat().st_size
            except OSError:
                return
        if size == self._offset:
            return

        try:
            with path.open("rb") as fp:
                fp.seek(self._offset)
                chunk = fp.read(size - self._offset)
        except OSError:
            logger.exception("watcher could not read %s", path)
            return

        lines = self._line_reader.feed(chunk)
        lines = [ln for ln in lines if _is_gamestate_line(ln)]
        if len(lines) > MAX_BUFFERED_LINES:
            # D-15: cap per-tick line buffer at 100k. Drop oldest, keep tail.
            logger.warning(
                "watcher dropping %d lines beyond cap",
                len(lines) - MAX_BUFFERED_LINES,
            )
            lines = lines[-MAX_BUFFERED_LINES:]

        self._offset = size
        if lines:
            self._on_lines(lines)

    def _handle_reset(self) -> None:
        self._offset = 0
        self._line_reader.reset()
        self._current_path = None
        self._on_reset()

    def _maybe_backward_scan(self, path: Path) -> int:
        """Return the byte offset of the latest CREATE_GAME line, or file size if none found.

        D-13: scan backward in 4 KB chunks up to 1 MB. If no CREATE_GAME found,
        jump to EOF (mirrors HDT behavior).
        """
        try:
            file_size = path.stat().st_size
        except OSError:
            return 0
        if file_size == 0:
            return 0
        scanned = 0
        tail_buffer = b""
        while scanned < BACKWARD_SCAN_MAX_BYTES and scanned < file_size:
            read_offset = max(0, file_size - scanned - BACKWARD_SCAN_CHUNK)
            read_bytes = min(BACKWARD_SCAN_CHUNK, file_size - read_offset - scanned)
            if read_bytes <= 0:
                break
            try:
                with path.open("rb") as fp:
                    fp.seek(read_offset)
                    chunk = fp.read(read_bytes)
            except OSError:
                break
            # Concatenate with previously-saved tail (in case CREATE_GAME spans
            # a chunk boundary).
            searchable = chunk + tail_buffer
            idx = searchable.rfind(CREATE_GAME_NEEDLE)
            if idx >= 0:
                # Find the start-of-line for that match
                line_start = searchable.rfind(b"\n", 0, idx)
                if line_start == -1:
                    return read_offset  # CREATE_GAME at file start
                return read_offset + line_start + 1
            # Save the first portion of `chunk` in case the needle spans the next read
            tail_buffer = chunk[: len(CREATE_GAME_NEEDLE)]
            scanned += read_bytes
            if read_offset == 0:
                break
        # No CREATE_GAME found within cap: jump to EOF and wait for next game (D-13)
        return file_size
