"""Stub tests for Phase 3 GlobalHotkeyService (Wave 0 scaffolding).

Each stub names a behavior locked by 03-VALIDATION.md per-requirement test
map for LIVE-09, plus additional behaviors required by 03-REVIEWS.md
(callback exception isolation, repeated-register-after-failure).
Production code lands in plan 03-04; tests flip from xfail to passing
when that plan completes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    strict=False,
    reason="Wave 0 stub - implementation lands in plan 03-04",
)


def test_register_returns_status() -> None:
    """LIVE-09: GlobalHotkeyService.register returns True on success and
    False on conflict; failed labels accumulate in a `failed` list.
    Implementation target: plan 03-04.
    """
    pytest.importorskip("wx")
    pytest.xfail("not implemented yet — plan 03-04")


def test_browse_open_dispatch() -> None:
    """LIVE-09: Registered callback is dispatched on `_on_hotkey` event
    when the matching chord fires (browse-open hotkey example).
    Implementation target: plan 03-04.
    """
    pytest.importorskip("wx")
    pytest.xfail("not implemented yet — plan 03-04")


def test_clear_all_idempotent() -> None:
    """LIVE-09: `clear_all()` unregisters every chord and is idempotent —
    a second call after all chords are cleared must not raise.
    Implementation target: plan 03-04.
    """
    pytest.importorskip("wx")
    pytest.xfail("not implemented yet — plan 03-04")


def test_callback_exception_isolation() -> None:
    """LIVE-09 (NEW per 03-REVIEWS.md MEDIUM 03-04 #1): A registered
    callback that raises is logged and isolated; subsequent dispatches to
    the same chord (and other chords) still work.
    Implementation target: plan 03-04.
    """
    pytest.importorskip("wx")
    pytest.xfail("not implemented yet — plan 03-04")


def test_repeated_register_after_failure() -> None:
    """LIVE-09 (NEW per 03-REVIEWS.md MEDIUM 03-04 #2): After a failed
    `register()` (chord conflict), calling `register()` again with a
    different chord still returns True and the service remains usable.
    Implementation target: plan 03-04.
    """
    pytest.importorskip("wx")
    pytest.xfail("not implemented yet — plan 03-04")
