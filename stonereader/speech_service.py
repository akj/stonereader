"""Screen reader output via accessible_output2 with stdout fallback.

accessible_output2.Auto() handles detection across NVDA, JAWS, Windows
Narrator, and others. If import fails (package absent or incompatible),
all output goes to stdout (ref: DL-007).
"""

from __future__ import annotations


class SpeechService:
    """Screen reader output.

    Wraps accessible_output2.Auto for cross-reader output. Falls back to
    stdout when no screen reader is available.
    """

    def __init__(self) -> None:
        self._use_stdout = False
        try:
            from accessible_output2.outputs.auto import Auto

            candidate = Auto()
            if candidate.get_first_available_output() is None:
                self._use_stdout = True
                self._output = None
            else:
                self._output = candidate
        except Exception:
            self._use_stdout = True
            self._output = None

    def speak(self, text: str, interrupt: bool = True) -> None:
        """Send text to the screen reader."""
        if self._use_stdout or self._output is None:
            print(text)
            return
        try:
            self._output.speak(text, interrupt=interrupt)
        except Exception:
            print(text)

    def speak_queued(self, text: str) -> None:
        """Queue text after current speech without interrupting."""
        self.speak(text, interrupt=False)
