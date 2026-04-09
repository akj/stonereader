"""Hotkey registration lifecycle management via wx.EVT_CHAR_HOOK.

EVT_CHAR_HOOK fires at the frame level before native control handlers run.
This is critical because NVDA/JAWS install WH_KEYBOARD_LL hooks that
intercept WM_KEYDOWN before it reaches the app, causing EVT_KEY_DOWN
and EVT_CHAR to silently fail on list/tree controls.

Key routing priority:
1. Text mode (TextCtrl focused) -> event.Skip()
2. Ctrl or Alt held -> event.Skip()
3. Key in active map -> call callback, consume key
4. Everything else -> event.Skip()
"""

from __future__ import annotations

from typing import Callable, Dict

import wx

_KEY_NAMES: Dict[int, str] = {
    wx.WXK_LEFT: "left",
    wx.WXK_RIGHT: "right",
    wx.WXK_UP: "up",
    wx.WXK_DOWN: "down",
    wx.WXK_RETURN: "enter",
    wx.WXK_NUMPAD_ENTER: "enter",
    wx.WXK_ESCAPE: "escape",
    wx.WXK_BACK: "back",
    wx.WXK_HOME: "home",
    wx.WXK_END: "end",
    wx.WXK_SPACE: "space",
}


def _key_spec_from_event(event: wx.KeyEvent) -> str:
    """Build a key spec string matching the format used in presenter key maps."""
    keycode = event.GetKeyCode()
    name = _KEY_NAMES.get(keycode)
    if name is None and 32 < keycode < 127:
        name = chr(keycode).lower()
    if name is None:
        return ""
    # Shift prefix for letter keys only — not arrows, enter, etc.
    if event.ShiftDown() and name not in _KEY_NAMES.values():
        name = f"shift+{name}"
    return name


class InputLayer:
    """Per-view hotkey set manager.

    Maintains one active key map at a time. Swapping views replaces the
    key map. Text mode disables all hotkey processing so keystrokes reach
    TextCtrl widgets.
    """

    def __init__(self, main_window: wx.Frame) -> None:
        self._current_key_map: Dict[str, Callable[[], None]] = {}
        self._text_mode = False
        main_window.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        main_window.Bind(wx.EVT_ACTIVATE, self._on_activate)

    def activate_view(self, name: str, key_map: Dict[str, Callable[[], None]]) -> None:
        """Replace the active key map."""
        self._current_key_map = key_map
        self._text_mode = False

    def enter_text_mode(self) -> None:
        """Disable hotkey processing so keystrokes reach TextCtrl."""
        self._text_mode = True

    def exit_text_mode(self) -> None:
        """Re-enable hotkey processing."""
        self._text_mode = False

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        # Rule 1: text mode passes everything through
        if self._text_mode:
            event.Skip()
            return
        # Rule 2: never intercept Ctrl or Alt combos
        if event.ControlDown() or event.AltDown():
            event.Skip()
            return
        # Rule 3: check active key map
        spec = _key_spec_from_event(event)
        callback = self._current_key_map.get(spec)
        if callback is not None:
            callback()
        else:
            # Rule 4: unmatched keys pass through
            event.Skip()

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        """Unstick text mode when window activates without TextCtrl focused."""
        event.Skip()
        if not self._text_mode:
            return
        window = wx.Window.FindFocus()
        if not isinstance(window, wx.TextCtrl):
            self.exit_text_mode()
