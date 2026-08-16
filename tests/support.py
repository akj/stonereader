from __future__ import annotations


class FakeSpeech:
    """Record what the Announcer hands the TTS, including lane drops."""

    def __init__(self, events: list[str] | None = None) -> None:
        self.calls: list[tuple[str, bool]] = []
        self.silences = 0
        self._events = events

    def speak(self, text: str, interrupt: bool = True) -> None:
        self.calls.append((text, interrupt))
        if self._events is not None:
            self._events.append(f"speech:{text}")

    def silence(self) -> None:
        self.silences += 1
        if self._events is not None:
            self._events.append("silence")
