"""The single speech-template and lane seam (ADR-0007, ADR-0010)."""

from __future__ import annotations

from enum import Enum, auto
from typing import Protocol


class SpeechOutput(Protocol):
    """The narrow part of SpeechService the Announcer consumes."""

    def speak(self, text: str, interrupt: bool = True) -> None: ...


class Lane(Enum):
    """Speech priority classes."""

    USER = auto()
    NARRATION = auto()


class Announcer:
    """Own all UI utterance templates and lane routing."""

    def __init__(self, speech: SpeechOutput) -> None:
        self._speech = speech

    def context_entry(
        self,
        label: str,
        title: str,
        position: int,
        count: int,
        *,
        queued: bool = False,
    ) -> None:
        self._speak(
            Lane.NARRATION if queued else Lane.USER,
            f"{label}, {title}, {position} of {count}",
        )

    def context_entry_menu(
        self,
        label: str,
        option: str,
        *,
        queued: bool = False,
    ) -> None:
        self._speak(
            Lane.NARRATION if queued else Lane.USER,
            f"{label}, {option}",
        )

    def context_empty(self, label: str, *, queued: bool = False) -> None:
        self._speak(
            Lane.NARRATION if queued else Lane.USER,
            f"{label}: empty",
        )

    def moved(self, text: str, *, queued: bool = False) -> None:
        self._speak(Lane.NARRATION if queued else Lane.USER, text)

    def boundary(self, text: str) -> None:
        self._speak(Lane.USER, text)

    def confirmation(self, text: str) -> None:
        # ADR-0007: when the action changed what is under the cursor, follow
        # with a re-fired context entry passing queued=True.
        self._speak(Lane.USER, text)

    def offer(self, text: str) -> None:
        """Speak an ephemeral Offer on Lane 1 exactly as supplied."""
        self._speak(Lane.USER, text)

    def query(self, subject: str, value: str) -> None:
        self._speak(Lane.USER, f"{subject}, {value}")

    def noop(self, text: str) -> None:
        self._speak(Lane.USER, text)

    def narrate(self, text: str) -> None:
        self._speak(Lane.NARRATION, text)

    def _speak(self, lane: Lane, text: str) -> None:
        self._speech.speak(text, interrupt=lane is Lane.USER)
