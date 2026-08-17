"""The one wx-facing frame input adapter (ADR-0008, ADR-0010, ADR-0014)."""

from __future__ import annotations

from collections.abc import Callable

import wx

from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import ACCEPT_OFFER_CHORD, Chord, chord_from_key
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.text_mode import TextSession


_WXK_CONTROL = 308


class InputSink:
    """Bind the frame once and delegate normalized input to the pure core."""

    def __init__(
        self,
        frame: wx.Frame,
        announcer: Announcer,
        stop_audio: Callable[[], None],
    ) -> None:
        self._core = _SinkCore(announcer, stop_audio)
        self._offer_armed = False
        frame.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        frame.Bind(wx.EVT_KEY_UP, self._on_key_up)

    def set_active(self, registry: CommandRegistry) -> None:
        self._core.set_active(registry)

    def enter_text_mode(self, session: TextSession) -> None:
        self._offer_armed = False
        self._core.enter_text_mode(session)

    def exit_text_mode(self) -> None:
        self._core.exit_text_mode()

    def enter_capture_mode(
        self,
        on_chord: Callable[[Chord], None],
        prompt_escape: Callable[[], None],
    ) -> None:
        self._offer_armed = False
        self._core.enter_capture_mode(on_chord, prompt_escape)

    def exit_capture_mode(self) -> None:
        self._core.exit_capture_mode()

    def arm_offer(
        self,
        subject: str,
        on_accept: Callable[[], None],
        *,
        resolicit: bool = False,
    ) -> bool:
        def accept_if_still_armed() -> None:
            if not self._offer_armed:
                return
            self._offer_armed = False
            on_accept()

        armed = self._core.arm_offer(
            subject,
            accept_if_still_armed,
            resolicit=resolicit,
        )
        if armed:
            self._offer_armed = True
        return armed

    def mark_offer_subject_seen(self, subject: str) -> None:
        self._core.mark_offer_subject_seen(subject)

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        keycode = event.GetKeyCode()
        if keycode == _WXK_CONTROL:
            self._core.control_down()
            return
        chord = chord_from_key(
            keycode,
            ctrl=event.ControlDown(),
            shift=event.ShiftDown(),
            alt=event.AltDown(),
        )
        if chord is None:
            self._offer_armed = False
            self._core.cancel_control_tap()
            event.Skip()
            return
        if chord != ACCEPT_OFFER_CHORD:
            self._offer_armed = False
        if not self._core.handle_chord(chord):
            event.Skip()

    def _on_key_up(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == _WXK_CONTROL:
            if self._core.control_up():
                self._offer_armed = False
                return
        event.Skip()
