"""Tests for stonereader.services._watcher."""
from __future__ import annotations

import pytest

pytest.importorskip("stonereader.services._watcher")

from stonereader.services import _watcher
from stonereader.services._watcher import PowerLogWatcher


def test_appended_lines_picked_up_within_one_tick(tmp_path):
    log = tmp_path / "Power.log"
    log.write_bytes(b"")
    emitted = []
    w = PowerLogWatcher(
        path_provider=lambda: log,
        on_lines=emitted.extend,
        on_reset=lambda: None,
    )
    # First tick — file is empty
    w._do_tick()
    assert emitted == []
    # Append a GameState line
    log.write_bytes(
        b"D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME\n"
    )
    w._do_tick()
    assert any("CREATE_GAME" in ln for ln in emitted)


def test_powertasklist_lines_filtered(tmp_path):
    log = tmp_path / "Power.log"
    log.write_bytes(
        b"D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME\n"
        b"D 13:00:00.0000000 PowerTaskList.DebugPrintPower() - CREATE_GAME\n"
    )
    emitted = []
    w = PowerLogWatcher(lambda: log, emitted.extend, lambda: None)
    # Backward scan will land on CREATE_GAME line, but tick reads from offset onward;
    # for a fresh file we must scan-then-tick:
    w._do_tick()  # initializes offset via backward scan
    # The backward scan landed at the CREATE_GAME line; subsequent reads start there.
    # All emitted lines must NOT contain "PowerTaskList"
    assert all("PowerTaskList" not in ln for ln in emitted)


def test_truncation_resets_offset_and_parser(tmp_path):
    log = tmp_path / "Power.log"
    log.write_bytes(
        b"D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME\n" * 10
    )
    reset_count = {"n": 0}
    w = PowerLogWatcher(
        lambda: log,
        lambda lines: None,
        lambda: reset_count.__setitem__("n", reset_count["n"] + 1),
    )
    w._do_tick()
    # Truncate
    log.write_bytes(
        b"D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME\n"
    )
    w._do_tick()
    assert reset_count["n"] >= 1


def test_reset_clears_partial_line_buffer(tmp_path):
    log = tmp_path / "Power.log"
    # Write a partial line (no trailing newline)
    log.write_bytes(b"D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GA")
    emitted = []
    w = PowerLogWatcher(lambda: log, emitted.extend, lambda: None)
    w._do_tick()
    # Truncate and start over — partial buffer should be flushed
    log.write_bytes(
        b"D 13:00:01.0000000 GameState.DebugPrintPower() - CREATE_GAME\n"
    )
    w._do_tick()
    # Emitted line must be the new CREATE_GAME, not a corrupted "CREATE_GA" + new content concat
    assert any("13:00:01" in ln and "CREATE_GAME" in ln for ln in emitted)
    assert not any("CREATE_GAD" in ln for ln in emitted)  # corruption signature


def test_buffer_cap_drops_oldest_lines(tmp_path, monkeypatch):
    # Lower the cap for the test
    monkeypatch.setattr(_watcher, "MAX_BUFFERED_LINES", 5)
    log = tmp_path / "Power.log"
    line = b"D 13:00:00.0000000 GameState.DebugPrintPower() - msg\n"
    log.write_bytes(line * 10)
    emitted = []
    w = _watcher.PowerLogWatcher(lambda: log, emitted.extend, lambda: None)
    w._do_tick()
    assert len(emitted) <= 5


def test_backward_scan_finds_create_game(tmp_path):
    log = tmp_path / "Power.log"
    prefix = b"D 13:00:00.0000000 GameState.DebugPrintPower() - garbage\n" * 100
    create = b"D 13:00:01.0000000 GameState.DebugPrintPower() - CREATE_GAME\n"
    suffix = b"D 13:00:02.0000000 GameState.DebugPrintPower() - tag\n" * 50
    log.write_bytes(prefix + create + suffix)
    emitted = []
    w = PowerLogWatcher(lambda: log, emitted.extend, lambda: None)
    w._do_tick()
    # First emitted line should be CREATE_GAME (or one near it from suffix)
    assert any("CREATE_GAME" in ln for ln in emitted)
    # Lines from `prefix` (before CREATE_GAME) must NOT be emitted
    assert not any("garbage" in ln for ln in emitted)
