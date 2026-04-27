"""Tests for stonereader.services._global_hotkey.GlobalHotkeyService.

Tests do NOT register real OS hotkeys — they monkeypatch
wx.Frame.RegisterHotKey / wx.Frame.UnregisterHotKey to scriptable bools.
Real OS-level WM_HOTKEY dispatch is verified manually per VALIDATION.md
§"Manual-Only Verifications".

Covers register/dispatch/clear_all/callback-isolation/repeated-register-
after-failure per 03-VALIDATION.md + 03-REVIEWS.md MEDIUM 03-04.
"""

from __future__ import annotations

import logging

import pytest


def test_register_returns_status(monkeypatch, caplog) -> None:
    """register returns True on success and False on conflict; failed accumulates."""
    wx = pytest.importorskip("wx")
    from stonereader.services._global_hotkey import GlobalHotkeyService

    app = wx.App()
    try:
        frame = wx.Frame(None)
        try:
            results = [True, False]
            calls: list = []

            def fake_register(hkid, mods, vk):
                calls.append((hkid, mods, vk))
                return results.pop(0)

            monkeypatch.setattr(frame, "RegisterHotKey", fake_register)

            service = GlobalHotkeyService(frame)
            with caplog.at_level(logging.WARNING):
                ok1 = service.register(
                    wx.MOD_CONTROL | wx.MOD_SHIFT,
                    ord("R"),
                    lambda: None,
                    "Remaining Deck",
                )
                ok2 = service.register(
                    wx.MOD_CONTROL | wx.MOD_SHIFT,
                    ord("O"),
                    lambda: None,
                    "Opponent Hand",
                )

            assert ok1 is True
            assert ok2 is False
            assert service.failed == ["Opponent Hand"]
            base = wx.MOD_CONTROL | wx.MOD_SHIFT
            assert calls[0][1] == base | 0x4000
            assert calls[1][1] == base | 0x4000
            assert any(
                "RegisterHotKey failed" in rec.message for rec in caplog.records
            )
        finally:
            frame.Destroy()
    finally:
        app.Destroy()


def test_browse_open_dispatch(monkeypatch) -> None:
    """_on_hotkey looks up the callback by id and invokes it."""
    wx = pytest.importorskip("wx")
    from stonereader.services._global_hotkey import GlobalHotkeyService

    app = wx.App()
    try:
        frame = wx.Frame(None)
        try:
            monkeypatch.setattr(frame, "RegisterHotKey", lambda *a, **kw: True)
            monkeypatch.setattr(frame, "UnregisterHotKey", lambda *a, **kw: True)

            service = GlobalHotkeyService(frame)
            fired: list = []
            service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT,
                ord("R"),
                lambda: fired.append("R"),
                "Remaining Deck",
            )

            class FakeEvent:
                def GetId(self) -> int:
                    return 1000

            service._on_hotkey(FakeEvent())  # type: ignore[arg-type]
            assert fired == ["R"]

            # Unknown id → no-op, no exception.
            class UnknownEvent:
                def GetId(self) -> int:
                    return 9999

            service._on_hotkey(UnknownEvent())  # type: ignore[arg-type]
            assert fired == ["R"]
        finally:
            frame.Destroy()
    finally:
        app.Destroy()


def test_clear_all_idempotent(monkeypatch) -> None:
    """clear_all unregisters every registered chord; safe to call twice.

    Also verifies `failed` survives clear_all (cumulative lifetime).
    """
    wx = pytest.importorskip("wx")
    from stonereader.services._global_hotkey import GlobalHotkeyService

    app = wx.App()
    try:
        frame = wx.Frame(None)
        try:
            # First register: success. Second: failure. Third: success.
            results = [True, False, True]

            def fake_register(*a, **kw):
                return results.pop(0)

            monkeypatch.setattr(frame, "RegisterHotKey", fake_register)
            unreg_calls: list = []
            monkeypatch.setattr(
                frame,
                "UnregisterHotKey",
                lambda hkid: unreg_calls.append(hkid) or True,
            )

            service = GlobalHotkeyService(frame)
            service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT, ord("R"), lambda: None, "R-label"
            )
            service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT, ord("O"), lambda: None, "O-label"
            )
            service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT, ord("D"), lambda: None, "D-label"
            )

            # Two successes (R-label at id 1000, D-label at id 1002), one
            # failure (O-label at id 1001).
            assert service.failed == ["O-label"]
            service.clear_all()
            # Both successful chords unregistered.
            assert unreg_calls == [1000, 1002]
            # `failed` survives clear_all (cumulative).
            assert service.failed == ["O-label"]
            # Second call: no-op for unregister, failed still preserved.
            service.clear_all()
            assert unreg_calls == [1000, 1002]
            assert service.failed == ["O-label"]
        finally:
            frame.Destroy()
    finally:
        app.Destroy()


def test_callback_exception_isolation(monkeypatch, caplog) -> None:
    """A callback that raises is logged and isolated; subsequent dispatches still work."""
    wx = pytest.importorskip("wx")
    from stonereader.services._global_hotkey import GlobalHotkeyService

    app = wx.App()
    try:
        frame = wx.Frame(None)
        try:
            monkeypatch.setattr(frame, "RegisterHotKey", lambda *a, **kw: True)
            monkeypatch.setattr(frame, "UnregisterHotKey", lambda *a, **kw: True)

            service = GlobalHotkeyService(frame)
            fired_good: list = []

            def bad_callback():
                raise RuntimeError("boom from bad callback")

            def good_callback():
                fired_good.append("good")

            service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT, ord("R"), bad_callback, "Bad"
            )
            service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT, ord("O"), good_callback, "Good"
            )

            class FakeEvent:
                def __init__(self, hkid: int) -> None:
                    self._hkid = hkid

                def GetId(self) -> int:
                    return self._hkid

            # Bad callback raises — service must catch and log.
            with caplog.at_level(logging.ERROR):
                service._on_hotkey(FakeEvent(1000))  # bad
            # Good callback still works after the bad one raised.
            service._on_hotkey(FakeEvent(1001))  # good
            # Bad callback can be invoked again (state not poisoned).
            service._on_hotkey(FakeEvent(1000))  # bad again

            assert fired_good == ["good"]
            assert any(
                "global hotkey callback raised" in rec.message
                for rec in caplog.records
            )
        finally:
            frame.Destroy()
    finally:
        app.Destroy()


def test_repeated_register_after_failure(monkeypatch) -> None:
    """A failed register() does NOT poison subsequent register() calls.

    After a failure, registering a different chord should succeed and
    be dispatchable normally.
    """
    wx = pytest.importorskip("wx")
    from stonereader.services._global_hotkey import GlobalHotkeyService

    app = wx.App()
    try:
        frame = wx.Frame(None)
        try:
            # First call fails, second succeeds.
            results = [False, True]
            monkeypatch.setattr(
                frame,
                "RegisterHotKey",
                lambda *a, **kw: results.pop(0),
            )

            service = GlobalHotkeyService(frame)
            ok1 = service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT,
                ord("R"),
                lambda: None,
                "Failed-Chord",
            )
            ok2 = service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT,
                ord("O"),
                lambda: None,
                "Success-Chord",
            )

            assert ok1 is False
            assert ok2 is True
            assert service.failed == ["Failed-Chord"]
            # The second registration's id is 1001 (the failed one consumed 1000).
            fired: list = []
            # Re-register a third chord with a callback we can verify.
            results2 = [True]
            monkeypatch.setattr(
                frame,
                "RegisterHotKey",
                lambda *a, **kw: results2.pop(0),
            )
            ok3 = service.register(
                wx.MOD_CONTROL | wx.MOD_SHIFT,
                ord("D"),
                lambda: fired.append("D"),
                "D-Chord",
            )
            assert ok3 is True

            class FakeEvent:
                def GetId(self) -> int:
                    return 1002  # third registration's id

            service._on_hotkey(FakeEvent())  # type: ignore[arg-type]
            assert fired == ["D"]
        finally:
            frame.Destroy()
    finally:
        app.Destroy()
