"""Tests for stonereader.services._process_detect."""

from __future__ import annotations

import psutil


class _FakeProc:
    """Stand-in for psutil.Process used by monkeypatched process_iter."""

    def __init__(self, name: str, exe_path: str) -> None:
        self.info = {"name": name}
        self._exe = exe_path

    def exe(self) -> str:
        return self._exe


def test_detects_running_process(monkeypatch) -> None:
    from stonereader.services._process_detect import ProcessDetector

    fake = _FakeProc("Hearthstone.exe", r"C:\Program Files\Hearthstone\Hearthstone.exe")
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter([fake]))
    detector = ProcessDetector()
    running, proc = detector.is_running()
    assert running is True
    assert proc is fake


def test_returns_false_when_absent(monkeypatch) -> None:
    from stonereader.services._process_detect import ProcessDetector

    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter([]))
    detector = ProcessDetector()
    running, proc = detector.is_running()
    assert running is False
    assert proc is None


def test_caches_within_ttl(monkeypatch, fake_clock) -> None:
    from stonereader.services._process_detect import ProcessDetector

    call_count = {"n": 0}

    def fake_iter(attrs=None):
        call_count["n"] += 1
        return iter([])

    monkeypatch.setattr(psutil, "process_iter", fake_iter)
    detector = ProcessDetector(cache_ttl_seconds=2.0, clock=fake_clock.monotonic)
    detector.is_running()  # first scan
    assert call_count["n"] == 1
    fake_clock.advance(0.5)
    detector.is_running()  # within TTL — should reuse cached result
    assert call_count["n"] == 1
    fake_clock.advance(2.0)  # past TTL
    detector.is_running()
    assert call_count["n"] == 2


def test_match_is_case_insensitive(monkeypatch) -> None:
    """Pitfall A1: Windows process names are case-insensitive."""
    from stonereader.services._process_detect import ProcessDetector

    fake = _FakeProc("HEARTHSTONE.EXE", r"C:\HS\HEARTHSTONE.EXE")
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter([fake]))
    detector = ProcessDetector()
    running, proc = detector.is_running()
    assert running is True
    assert proc is fake


def test_get_install_dir_returns_parent_of_exe(monkeypatch) -> None:
    from stonereader.services._process_detect import ProcessDetector

    fake = _FakeProc("Hearthstone.exe", r"C:\Program Files\Hearthstone\Hearthstone.exe")
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter([fake]))
    detector = ProcessDetector()
    install_dir = detector.get_install_dir()
    assert install_dir is not None
    # Path comparison must work cross-platform; check the final segment.
    assert install_dir.name == "Hearthstone"


def test_get_install_dir_returns_none_when_not_running(monkeypatch) -> None:
    from stonereader.services._process_detect import ProcessDetector

    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter([]))
    detector = ProcessDetector()
    assert detector.get_install_dir() is None


def test_skips_processes_that_disappear_during_iteration(monkeypatch) -> None:
    """psutil.NoSuchProcess from .info access must not abort the scan."""
    from stonereader.services._process_detect import ProcessDetector

    class _GoneProc:
        @property
        def info(self):
            raise psutil.NoSuchProcess(pid=999)

    real = _FakeProc(
        "Hearthstone.exe", r"C:\Program Files\Hearthstone\Hearthstone.exe"
    )
    monkeypatch.setattr(
        psutil, "process_iter", lambda attrs=None: iter([_GoneProc(), real])
    )
    detector = ProcessDetector()
    running, proc = detector.is_running()
    assert running is True
    assert proc is real


def test_invalidate_cache_forces_rescan(monkeypatch, fake_clock) -> None:
    from stonereader.services._process_detect import ProcessDetector

    call_count = {"n": 0}

    def fake_iter(attrs=None):
        call_count["n"] += 1
        return iter([])

    monkeypatch.setattr(psutil, "process_iter", fake_iter)
    detector = ProcessDetector(cache_ttl_seconds=2.0, clock=fake_clock.monotonic)
    detector.is_running()
    assert call_count["n"] == 1
    detector.invalidate_cache()
    detector.is_running()
    assert call_count["n"] == 2
