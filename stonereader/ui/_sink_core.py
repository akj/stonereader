"""wx-free input-state decisions used by the frame adapter (ADR-0010)."""

from __future__ import annotations

from collections.abc import Callable

from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import ACCEPT_OFFER_CHORD, Chord
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.text_mode import TextSession

BARE_CTRL_HELP_PHRASE = "Ctrl: stop game audio"


class _SinkCore:
    """Route normalized chords without depending on wx event objects."""

    def __init__(self, announcer: Announcer, stop_audio: Callable[[], None]) -> None:
        self._announcer = announcer
        self._stop_audio = stop_audio
        self._active_registry: CommandRegistry | None = None
        self._text_session: TextSession | None = None
        self._capture_chord: Callable[[Chord], None] | None = None
        self._capture_escape: Callable[[], None] | None = None
        self._ctrl_tap_candidate = False
        self._offer: Callable[[], None] | None = None
        self._seen_offer_subjects: set[str] = set()

    @property
    def text_mode_active(self) -> bool:
        return self._text_session is not None

    @property
    def capture_mode_active(self) -> bool:
        return self._capture_chord is not None

    def set_active(self, registry: CommandRegistry) -> None:
        self._active_registry = registry

    def enter_text_mode(self, session: TextSession) -> None:
        assert self._capture_chord is None, "Text and Capture modes are exclusive"
        self._offer = None
        self._text_session = session

    def exit_text_mode(self) -> None:
        self._text_session = None

    def enter_capture_mode(
        self,
        on_chord: Callable[[Chord], None],
        prompt_escape: Callable[[], None],
    ) -> None:
        assert self._text_session is None, "Text and Capture modes are exclusive"
        assert self._capture_chord is None, "Capture mode is already active"
        self._offer = None
        self._capture_chord = on_chord
        self._capture_escape = prompt_escape

    def exit_capture_mode(self) -> None:
        self._capture_chord = None
        self._capture_escape = None

    def arm_offer(
        self,
        subject: str,
        on_accept: Callable[[], None],
        *,
        resolicit: bool = False,
    ) -> bool:
        """Arm once per subject, and only in navigation state.

        A solicited trigger (the User explicitly asked for the check that
        produced this proposition) passes resolicit=True: ADR-0014's
        once-per-subject rule governs unsolicited re-triggering only.
        """
        if resolicit:
            self._seen_offer_subjects.discard(subject)
        if (
            self._text_session is not None
            or self._capture_chord is not None
            or subject in self._seen_offer_subjects
        ):
            return False
        self._seen_offer_subjects.add(subject)
        self._offer = on_accept
        return True

    def mark_offer_subject_seen(self, subject: str) -> None:
        """Record an Offer subject without arming it."""
        self._seen_offer_subjects.add(subject)

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

        if self._capture_chord is not None:
            if chord == Chord("escape"):
                escape = self._capture_escape
                if escape is not None:
                    escape()
            else:
                self._capture_chord(chord)
            return True

        # ADR-0007: a Lane-1 keypress drops pending Lane-2 narration, whether
        # or not the command it reaches goes on to speak. Text and Capture
        # modes returned above: typing is not a Lane-1 keypress.
        self._announcer.drop_narration()

        if self._offer is not None:
            offer = self._offer
            self._offer = None
            if chord == ACCEPT_OFFER_CHORD:
                offer()
                return True

        if self._active_registry is None:
            return False
        result = self._active_registry.dispatch(chord)
        if result.announce is not None:
            self._announcer.noop(result.announce)
        elif result.noop_slot is not None:
            self._announcer.slot_noop(result.noop_slot)
        return result.handled
