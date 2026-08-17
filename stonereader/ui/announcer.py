"""The single speech-template and lane seam (ADR-0007, ADR-0010)."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto
from typing import Protocol

from stonereader.ui.registry import Slot


class SpeechOutput(Protocol):
    """The narrow part of SpeechService the Announcer consumes."""

    def speak(self, text: str, interrupt: bool = True) -> None: ...

    def silence(self) -> None: ...


class Lane(Enum):
    """Speech priority classes."""

    USER = auto()
    NARRATION = auto()


SLOT_NOOP_PHRASES: dict[Slot, str] = {
    Slot.ENTER: "Nothing to do here",
    Slot.GROUP_JUMP: "No groups on this screen",
    Slot.SEARCH: "No search on this screen",
    Slot.COARSE_AXIS: "No pages on this screen",
    Slot.LISTEN: "No card focused",
}


class Announcer:
    """Own all UI utterance templates and lane routing."""

    def __init__(self, speech: SpeechOutput) -> None:
        self._speech = speech
        self._narration_pending = False

    def context_entry(
        self,
        label: str,
        title: str,
        position: int,
        count: int,
        *,
        continues: bool = False,
    ) -> None:
        self._utter(
            Lane.USER,
            f"{label}, {title}, {position} of {count}",
            continues=continues,
        )

    def context_entry_menu(
        self,
        label: str,
        option: str,
        *,
        continues: bool = False,
    ) -> None:
        self._utter(Lane.USER, f"{label}, {option}", continues=continues)

    def context_empty(self, label: str, *, continues: bool = False) -> None:
        self._utter(Lane.USER, f"{label}: empty", continues=continues)

    def moved(self, text: str) -> None:
        self._utter(Lane.USER, text)

    def read_lines(self, lines: Sequence[str]) -> None:
        """Read several detail lines as one Lane-1 utterance.

        Shift+Down is user-initiated, so every line rides Lane 1: the first
        interrupts and the rest follow it, never interleaved with narration.
        """
        for index, line in enumerate(lines):
            self._utter(Lane.USER, line, continues=index > 0)

    def boundary(self, text: str) -> None:
        self._utter(Lane.USER, text)

    def confirmation(self, text: str) -> None:
        # ADR-0007: when the action changed what is under the cursor, follow
        # with a re-fired context entry passing continues=True.
        self._utter(Lane.USER, text)

    def clipboard_deck_offer(self) -> None:
        """Speak the ephemeral clipboard-deckstring Offer (ADR-0014)."""
        self._utter(
            Lane.USER,
            "Deck code on clipboard — press Control Enter to import",
        )

    def import_replays_result(
        self,
        imported: int,
        duplicates: int,
        failed: int,
    ) -> None:
        """Confirm a replay batch, omitting every zero-valued part."""
        parts = [
            phrase
            for count, phrase in (
                (imported, f"{imported} imported"),
                (duplicates, f"{duplicates} already in Replays"),
                (failed, f"{failed} failed"),
            )
            if count
        ]
        self._utter(Lane.USER, ", ".join(parts) if parts else "Nothing imported")

    def query(self, subject: str, value: str) -> None:
        self._utter(Lane.USER, f"{subject}, {value}")

    def noop(self, text: str) -> None:
        self._utter(Lane.USER, text)

    def slot_noop(self, slot: Slot) -> None:
        """Announce an unfilled universal slot's default no-op (ADR-0010)."""
        self._utter(Lane.USER, SLOT_NOOP_PHRASES[slot])

    def empty_zone(self, zone_label: str) -> None:
        """Announce a zone-switch no-op for a zone with nothing in it."""
        self._utter(Lane.USER, f"No {zone_label} on this screen")

    def already_home(self, home_title: str) -> None:
        """Announce back's no-op at the root of the stack (ADR-0006)."""
        self._utter(Lane.USER, f"{home_title} — already at the top")

    def game_logging_enabled(self) -> None:
        """Confirm the one-time Hearthstone log.config bootstrap."""
        self._utter(Lane.USER, "Hearthstone logging enabled")

    def hotkeys_unavailable(self, names: Sequence[str]) -> None:
        """Report system-wide hotkeys Windows refused to register."""
        self._utter(
            Lane.USER,
            "Could not register hotkeys: " + ", ".join(names) + ".",
        )

    def update_checking(self) -> None:
        self._utter(Lane.USER, "Checking for updates")

    def update_offer(self, version: str) -> None:
        """Speak the ephemeral update Offer (ADR-0014, ADR-0016)."""
        self._utter(
            Lane.USER,
            f"StoneReader {version} is available — "
            "press Control Enter to update",
        )

    def update_up_to_date(self, version: str) -> None:
        self._utter(
            Lane.USER,
            f"You're up to date. StoneReader {version} is the latest release",
        )

    def update_check_failed(self) -> None:
        self._utter(
            Lane.USER,
            "Couldn't check for updates. "
            "Check your internet connection and try again",
        )

    def update_check_unavailable(self) -> None:
        self._utter(Lane.USER, "Update checking isn't available in this build")

    def update_downloading(self, version: str) -> None:
        self._utter(Lane.USER, f"Downloading StoneReader {version}")

    def update_installing(self) -> None:
        self._utter(Lane.USER, "Installing update. StoneReader will restart")

    def update_download_failed(self) -> None:
        self._utter(
            Lane.USER,
            "The update couldn't be downloaded. Try again later",
        )

    def narrate(self, text: str) -> None:
        self._utter(Lane.NARRATION, text)

    def drop_narration(self) -> None:
        """Discard pending Lane-2 speech, cutting the utterance in flight.

        A Lane-1 keypress drops narration whether or not the command it runs
        speaks; when it does speak, its interrupting utterance is the same
        drop and this is a no-op (ADR-0007).
        """
        if not self._narration_pending:
            return
        self._narration_pending = False
        self._speech.silence()

    def _utter(self, lane: Lane, text: str, *, continues: bool = False) -> None:
        """Put one utterance on its lane (ADR-0007).

        A fresh Lane-1 utterance interrupts: it cuts whatever is speaking and
        takes the pending Lane-2 queue with it. A Lane-1 continuation — a
        multi-line read, or a context entry re-fired behind a confirmation —
        follows the utterance before it rather than cutting it. Lane 2 only
        ever queues, so narration can never cut Lane 1 and stays in order
        among itself.
        """
        if lane is Lane.NARRATION:
            self._narration_pending = True
            self._speech.speak(text, interrupt=False)
            return
        if continues:
            self._speech.speak(text, interrupt=False)
            return
        self._narration_pending = False
        self._speech.speak(text, interrupt=True)
