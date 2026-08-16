"""Screen reader output via accessible_output2 with stdout fallback.

accessible_output2.Auto() handles detection across NVDA, JAWS, Windows
Narrator, and others. If import fails (package absent or incompatible),
all output goes to stdout (ref: DL-007).
"""

from __future__ import annotations

from typing import Any, Protocol


class SpeechOutput(Protocol):
    """The screen-reader surface SpeechService drives."""

    def speak(self, text: str, interrupt: bool = True) -> None: ...

    def silence(self) -> None: ...


class SpeechService:
    """Screen reader output.

    Wraps accessible_output2.Auto for cross-reader output. Falls back to
    stdout when no screen reader is available. Tests pass their own output
    so that running the suite never speaks through the User's screen reader.
    """

    def __init__(self, output: SpeechOutput | None = None) -> None:
        self._output = _detect_output() if output is None else output

    def speak(self, text: str, interrupt: bool = True) -> None:
        """Send text to the screen reader."""
        try:
            self._output.speak(text, interrupt=interrupt)
        except Exception:
            print(text)

    def silence(self) -> None:
        """Cut current speech and discard whatever is queued behind it."""
        try:
            self._output.silence()
        except Exception:
            pass


class _StdoutOutput:
    """The output used when no screen reader is running."""

    def speak(self, text: str, interrupt: bool = True) -> None:
        del interrupt
        print(text)

    def silence(self) -> None:
        pass


class _ScreenReaderOutput:
    """accessible_output2's Auto, plus the silence() its base class lacks."""

    def __init__(self, auto: Any) -> None:
        self._auto = auto

    def speak(self, text: str, interrupt: bool = True) -> None:
        self._auto.speak(text, interrupt=interrupt)

    def silence(self) -> None:
        output = self._auto.get_first_available_output()
        silence = getattr(output, "silence", None)
        if silence is not None:
            silence()


def _detect_output() -> SpeechOutput:
    try:
        from accessible_output2.outputs.auto import Auto

        auto = Auto()
        if auto.get_first_available_output() is None:
            return _StdoutOutput()
        return _ScreenReaderOutput(auto)
    except Exception:
        return _StdoutOutput()
