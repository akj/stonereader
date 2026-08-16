"""Shared fixtures for stonereader.services tests."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "log"


class FakeClock:
    """Manual time.monotonic substitute for TTL cache tests (D-03 process detect)."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class MockProcessDetector:
    """Test double for ProcessDetector — scriptable is_running result.

    Skips the parent __init__ so the double never touches the real psutil API.
    """

    def __init__(self, running: bool = False, exe_dir: Optional[Path] = None) -> None:
        self._running = running
        self._exe_dir = exe_dir

    def is_running(self) -> tuple[bool, Optional[object]]:
        return (self._running, None if not self._running else object())

    def get_install_dir(self) -> Optional[Path]:
        return self._exe_dir if self._running else None

    def set_running(self, running: bool, exe_dir: Optional[Path] = None) -> None:
        self._running = running
        self._exe_dir = exe_dir


@pytest.fixture
def power_log_fixture():
    """Returns a callable that loads a captured Power.log fixture by name.

    Usage:
        def test_x(power_log_fixture):
            path = power_log_fixture("mid_game.log")
            text = path.read_text(encoding="utf-8")
    """
    def _load(name: str) -> Path:
        path = FIXTURE_DIR / name
        if not path.exists():
            pytest.skip(f"fixture not yet captured: {name} (Wave 5 task)")
        return path
    return _load


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def mock_process_detector() -> MockProcessDetector:
    return MockProcessDetector()
