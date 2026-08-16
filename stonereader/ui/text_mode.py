"""Input-layer-owned Text mode editing (ADR-0004, ADR-0011)."""

from __future__ import annotations

from collections.abc import Callable

from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord


_SHIFTED_US_KEYS = {
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    "\\": "|",
    ";": ":",
    "'": '"',
    ",": "<",
    ".": ">",
    "/": "?",
    "`": "~",
}


class TextSession:
    """A complete, explicitly entered text-field interaction."""

    def __init__(
        self,
        field_label: str,
        initial: str,
        announcer: Announcer,
        on_commit: Callable[[str], None],
        on_abandon: Callable[[], None],
    ) -> None:
        self._field_label = field_label
        self._text = initial
        self._caret = len(initial)
        self._announcer = announcer
        self._on_commit = on_commit
        self._on_abandon = on_abandon

    @property
    def text(self) -> str:
        return self._text

    @property
    def caret(self) -> int:
        return self._caret

    def handle(self, chord: Chord) -> bool:
        """Consume every chord while Text mode owns the keyboard."""
        if chord == Chord("enter"):
            self._on_commit(self._text)
            return True
        if chord == Chord("escape"):
            self._on_abandon()
            return True
        if chord == Chord("f1"):
            self._announcer.moved(
                f"Typing in {self._field_label}. Enter commits, Escape cancels."
            )
            return True
        if chord == Chord("backspace"):
            self._backspace()
            return True
        if chord == Chord("left"):
            self._left()
            return True
        if chord == Chord("right"):
            self._right()
            return True
        if chord == Chord("home"):
            # ADR-0011 pins caret behavior, not an invented utterance.
            self._caret = 0
            return True
        if chord == Chord("end"):
            # ADR-0011 pins caret behavior, not an invented utterance.
            self._caret = len(self._text)
            return True

        character = _printable_character(chord)
        if character is not None:
            self._text = (
                self._text[: self._caret]
                + character
                + self._text[self._caret :]
            )
            self._caret += 1
            self._announcer.moved(character)
        return True

    def _backspace(self) -> None:
        if self._caret == 0:
            return
        erased = self._text[self._caret - 1]
        self._text = self._text[: self._caret - 1] + self._text[self._caret :]
        self._caret -= 1
        self._announcer.moved(erased)

    def _left(self) -> None:
        if self._caret == 0:
            return
        crossed = self._text[self._caret - 1]
        self._caret -= 1
        self._announcer.moved(crossed)

    def _right(self) -> None:
        if self._caret == len(self._text):
            return
        crossed = self._text[self._caret]
        self._caret += 1
        self._announcer.moved(crossed)


def _printable_character(chord: Chord) -> str | None:
    if chord.ctrl or chord.alt:
        return None
    if chord.key == "space":
        return " "
    if len(chord.key) != 1 or not 33 <= ord(chord.key) <= 126:
        return None
    if chord.key.isalpha():
        return chord.key.upper() if chord.shift else chord.key
    if chord.shift:
        return _SHIFTED_US_KEYS.get(chord.key, chord.key)
    return chord.key
