"""Shared view helpers and base widgets.

Text mode lifecycle: bind EVT_SET_FOCUS / EVT_KILL_FOCUS on TextCtrl widgets
to enter/exit text mode on the owning input sink. This ensures hotkeys are
suppressed while typing.
"""

from __future__ import annotations

from typing import Protocol

import wx


class TextModeOwner(Protocol):
    def enter_text_mode(self) -> None: ...

    def exit_text_mode(self) -> None: ...


def bind_text_mode(ctrl: wx.TextCtrl, input_layer: TextModeOwner) -> None:
    """Bind focus events on a TextCtrl to enter/exit text mode."""
    ctrl.Bind(wx.EVT_SET_FOCUS, lambda evt: (_enter_text(input_layer), evt.Skip()))
    ctrl.Bind(wx.EVT_KILL_FOCUS, lambda evt: (_exit_text(input_layer), evt.Skip()))


def _enter_text(input_layer: TextModeOwner) -> None:
    input_layer.enter_text_mode()


def _exit_text(input_layer: TextModeOwner) -> None:
    input_layer.exit_text_mode()


def make_labeled_text_ctrl(
    parent: wx.Window,
    sizer: wx.Sizer,
    label: str,
    input_layer: TextModeOwner,
    style: int = 0,
) -> wx.TextCtrl:
    """Create a labeled TextCtrl and add both to the sizer.

    Places a wx.StaticText immediately before the TextCtrl in the sizer
    so NVDA/JAWS read the label via MSAA sibling order.
    """
    static = wx.StaticText(parent, label=label)
    ctrl = wx.TextCtrl(parent, style=style)
    sizer.Add(static, 0, wx.ALL, 4)
    sizer.Add(ctrl, 0, wx.EXPAND | wx.ALL, 4)
    bind_text_mode(ctrl, input_layer)
    return ctrl
