"""wx-free input-state decisions used by the frame adapter (ADR-0010)."""

from __future__ import annotations

from collections.abc import Callable

from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.text_mode import TextSession


_ACCEPT_OFFER = Chord("enter", ctrl=True)


class _SinkCore:
    """Route normalized chords without depending on wx event objects."""

    def __init__(self, announcer: Announcer, stop_audio: Callable[[], None]) -> None:
        self._announcer = announcer
        self._stop_audio = stop_audio
        self._active_registry: CommandRegistry | None = None
        self._text_session: TextSession | None = None
        self._ctrl_tap_candidate = False
        self._offer: Callable[[], None] | None = None
        self._seen_offer_subjects: set[str] = set()

    @property
    def text_mode_active(self) -> bool:
        return self._text_session is not None

    def set_active(self, registry: CommandRegistry) -> None:
        self._active_registry = registry

    def enter_text_mode(self, session: TextSession) -> None:
        self._offer = None
        self._text_session = session

    def exit_text_mode(self) -> None:
        self._text_session = None

    def arm_offer(self, subject: str, on_accept: Callable[[], None]) -> None:
        """Arm once per subject, and only in navigation state."""
        if self._text_session is not None or subject in self._seen_offer_subjects:
            return
        self._seen_offer_subjects.add(subject)
        self._offer = on_accept

    def control_down(self) -> None:
        self._ctrl_tap_candidate = True

    def cancel_control_tap(self) -> None:
        self._ctrl_tap_candidate = False

    def control_up(self) -> bool:
        """Finish a possible bare-Ctrl tap and report whether it fired."""
        fired = self._ctrl_tap_candidate
        self._ctrl_tap_candidate = False
        if fired:
            self._stop_audio()
        return fired

    def handle_chord(self, chord: Chord) -> bool:
        """Route a chord and report whether the frame should consume it."""
        self._ctrl_tap_candidate = False

        if self._text_session is not None:
            return self._text_session.handle(chord)

        if self._offer is not None:
            offer = self._offer
            self._offer = None
            if chord == _ACCEPT_OFFER:
                offer()
                return True

        if self._active_registry is None:
            return False
        result = self._active_registry.dispatch(chord)
        if result.announce is not None:
            self._announcer.noop(result.announce)
        return result.handled
