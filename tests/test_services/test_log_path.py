"""Tests for stonereader.services._log_path."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest


def test_picks_newest_subdirectory_by_mtime(tmp_path: Path) -> None:
    from stonereader.services._log_path import discover_power_log_path

    logs = tmp_path / "Logs"
    old = logs / "Hearthstone_2026_01_01_12_00_00"
    new = logs / "Hearthstone_2026_03_15_18_30_00"
    for d in (old, new):
        d.mkdir(parents=True)
        (d / "Power.log").write_text("data", encoding="utf-8")
    # Force older mtime on `old` so `new` is unambiguously newest.
    old_time = time.time() - 3600
    os.utime(old, (old_time, old_time))
    result = discover_power_log_path(install_dir=tmp_path)
    assert result == new / "Power.log"


def test_falls_back_to_flat_path(tmp_path: Path) -> None:
    from stonereader.services._log_path import discover_power_log_path

    logs = tmp_path / "Logs"
    logs.mkdir()
    flat = logs / "Power.log"
    flat.write_text("data", encoding="utf-8")
    result = discover_power_log_path(install_dir=tmp_path)
    assert result == flat


def test_returns_none_when_not_found(tmp_path: Path) -> None:
    from stonereader.services._log_path import discover_power_log_path

    # Logs/ exists but contains no Power.log anywhere
    (tmp_path / "Logs").mkdir()
    result = discover_power_log_path(install_dir=tmp_path)
    assert result is None


def test_returns_none_when_logs_dir_missing(tmp_path: Path) -> None:
    from stonereader.services._log_path import discover_power_log_path

    result = discover_power_log_path(install_dir=tmp_path)
    assert result is None


def test_subdirs_without_power_log_are_skipped(tmp_path: Path) -> None:
    """A Hearthstone_* subdir without Power.log must not be selected."""
    from stonereader.services._log_path import discover_power_log_path

    logs = tmp_path / "Logs"
    bare = logs / "Hearthstone_2026_05_01_09_00_00"
    bare.mkdir(parents=True)
    # No Power.log inside `bare`.
    older_with_log = logs / "Hearthstone_2026_01_01_09_00_00"
    older_with_log.mkdir(parents=True)
    (older_with_log / "Power.log").write_text("data", encoding="utf-8")
    # Make `bare` newer so it would be picked first if not for the filter.
    new_time = time.time() + 60
    os.utime(bare, (new_time, new_time))
    result = discover_power_log_path(install_dir=tmp_path)
    assert result == older_with_log / "Power.log"


def test_non_hearthstone_subdirs_are_ignored(tmp_path: Path) -> None:
    """Subdirectories not starting with 'Hearthstone_' are filtered out."""
    from stonereader.services._log_path import discover_power_log_path

    logs = tmp_path / "Logs"
    # A subdirectory that does NOT match the prefix — must be skipped.
    foreign = logs / "SomeOtherTool_2026_05_01_09_00_00"
    foreign.mkdir(parents=True)
    (foreign / "Power.log").write_text("imposter", encoding="utf-8")
    # No matching Hearthstone_* subdirs and no flat Power.log.
    result = discover_power_log_path(install_dir=tmp_path)
    assert result is None
