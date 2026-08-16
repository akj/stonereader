from __future__ import annotations

from collections.abc import Callable
from typing import cast

import wx

from stonereader.ui.announcer import Announcer
from stonereader.ui.sink import InputSink

from tests.support import FakeSpeech


class _Frame:
    def __init__(self) -> None:
        self.bindings: dict[object, Callable[[object], None]] = {}

    def Bind(self, event_type, handler) -> None:  # noqa: N802 - wx-shaped fake
        self.bindings[event_type] = handler


class _KeyEvent:
    def __init__(self, keycode: int, *, ctrl: bool = False) -> None:
        self._keycode = keycode
        self._ctrl = ctrl
        self.skipped = False

    def GetKeyCode(self) -> int:  # noqa: N802 - wx-shaped fake
        return self._keycode

    def ControlDown(self) -> bool:  # noqa: N802 - wx-shaped fake
        return self._ctrl

    def ShiftDown(self) -> bool:  # noqa: N802 - wx-shaped fake
        return False

    def AltDown(self) -> bool:  # noqa: N802 - wx-shaped fake
        return False

    def Skip(self) -> None:  # noqa: N802 - wx-shaped fake
        self.skipped = True


def test_bare_ctrl_tap_disarms_offer_silently() -> None:
    accepted: list[str] = []
    stops: list[str] = []
    sink = InputSink(
        cast(wx.Frame, _Frame()),
        Announcer(FakeSpeech()),
        lambda: stops.append("stop"),
    )
    assert sink.arm_offer("code", lambda: accepted.append("accepted")) is True

    sink._on_char_hook(cast(wx.KeyEvent, _KeyEvent(wx.WXK_CONTROL)))
    sink._on_key_up(cast(wx.KeyEvent, _KeyEvent(wx.WXK_CONTROL)))
    sink._on_char_hook(
        cast(wx.KeyEvent, _KeyEvent(wx.WXK_RETURN, ctrl=True))
    )

    assert stops == ["stop"]
    assert accepted == []
