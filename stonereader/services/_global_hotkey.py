"""Global hotkey service: wraps wx.Frame.RegisterHotKey for system-wide chords.

D-01: hybrid model with shared Ctrl+Shift+<letter> modifier prefix.
Pitfall 4: registration failures (chord held by another app) are logged
    and accumulated in `failed` so the caller can announce them at startup.
    `failed` is CUMULATIVE for the service lifetime — `clear_all()` does
    NOT reset it, so startup-failure announcements remain available even
    after re-registration attempts.
Pitfall 5: MOD_NOREPEAT (0x4000) is OR'd into modifier flags by default
    so a held chord doesn't flood the speech queue.
Pitfall 3 / T-2-04: a callback that raises is logged and isolated; other
    chords continue to work.

Application hotkey id space (Win32 RegisterHotKey docs): 0x0000–0xBFFF.
We allocate ids starting at 1000 and increment per registration. A FAILED
registration still consumes an id (the counter advances) so the next call
receives a fresh id.

EVT_HOTKEY binding: bound once in __init__; never unbound. Frame Destroy()
releases the binding automatically. This is appropriate because the
service's lifetime is tied to the parent frame's lifetime.

The engine layer (Phase 2) NEVER imports wx — keeping `_global_hotkey` in
services/ is intentional: it lives next to the other private wx-frame-bound
services (`_watcher.py`, `_tracker.py`).
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Tuple

import wx

logger = logging.getLogger(__name__)

# Win32 MOD_NOREPEAT — wxPython 4.2.5 does not expose this as wx.MOD_NOREPEAT,
# but RegisterHotKey accepts arbitrary modifier flags (per MSDN), so OR'ing
# the integer literal works.
_MOD_NOREPEAT = 0x4000

# Win32 application hotkey id space starts at 0x0000; we leave room for any
# caller-supplied ids by starting at 1000.
_ID_BASE = 1000


class GlobalHotkeyService:
    """Register and dispatch system-wide hotkeys via wx.Frame.RegisterHotKey.

    Lifecycle:
        hotkeys = GlobalHotkeyService(frame)
        hotkeys.register(wx.MOD_CONTROL | wx.MOD_SHIFT, ord("R"), callback, "Remaining Deck")
        ...
        hotkeys.clear_all()  # call from MainWindow._on_close BEFORE Destroy()
    """

    def __init__(self, frame: wx.Frame) -> None:
        self._frame = frame
        self._next_id = _ID_BASE
        self._callbacks: Dict[int, Callable[[], None]] = {}
        self._registered: List[Tuple[int, str]] = []
        # Cumulative for service lifetime; not reset by clear_all() so
        # startup-failure announcements remain readable.
        self._failed: List[str] = []
        frame.Bind(wx.EVT_HOTKEY, self._on_hotkey)

    # ----------------------------------------------------------- Public API

    def register(
        self,
        modifiers: int,
        vk: int,
        callback: Callable[[], None],
        label: str = "",
    ) -> bool:
        """Register a global hotkey.

        Returns True on success, False on Win32 conflict (chord held by
        another app — ERROR_HOTKEY_ALREADY_REGISTERED). On failure, the
        label is appended to `failed` for caller-driven user-facing
        announcement (Pitfall 4).

        MOD_NOREPEAT (0x4000) is OR'd into `modifiers` automatically.

        Failures do NOT poison subsequent calls: `_next_id` advances even
        on failure, so the next `register()` call starts from a fresh id
        and proceeds normally.
        """
        mods = modifiers | _MOD_NOREPEAT
        hkid = self._next_id
        self._next_id += 1
        ok = self._frame.RegisterHotKey(hkid, mods, vk)
        if not ok:
            logger.warning(
                "RegisterHotKey failed for %s (mods=0x%x vk=0x%x); skipping",
                label or f"id={hkid}",
                mods,
                vk,
            )
            self._failed.append(label or f"mod=0x{mods:x} vk=0x{vk:x}")
            return False
        self._callbacks[hkid] = callback
        self._registered.append((hkid, label))
        logger.info("Registered global hotkey: %s", label or f"id={hkid}")
        return True

    def clear_all(self) -> None:
        """Unregister every registered hotkey. Idempotent.

        Call from MainWindow._on_close BEFORE Destroy() so the OS hotkey
        table is cleaned up cleanly (Runtime State Inventory).

        Does NOT clear `_failed` — failure labels are cumulative for the
        service lifetime so callers can read them at any point.
        """
        for hkid, _label in self._registered:
            try:
                self._frame.UnregisterHotKey(hkid)
            except Exception:
                logger.exception("UnregisterHotKey failed for id=%d", hkid)
        self._registered.clear()
        self._callbacks.clear()

    @property
    def failed(self) -> List[str]:
        """Labels of chords that failed to register (e.g. held by another app).

        Cumulative for the service lifetime. `clear_all()` does NOT reset.
        """
        return list(self._failed)

    # ----------------------------------------------------------- Internals

    def _on_hotkey(self, event: "wx.Event") -> None:
        hkid = event.GetId()
        callback = self._callbacks.get(hkid)
        if callback is None:
            return
        try:
            callback()
        except Exception:
            logger.exception("global hotkey callback raised; ignoring")
