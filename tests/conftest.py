"""Shared test fixtures."""

from __future__ import annotations

from stonereader.speech_service import SpeechService


class MockSpeechService(SpeechService):
    """SpeechService that captures speech output for testing."""

    def __init__(self) -> None:
        self._use_stdout = True
        self._output = None
        self.spoken: list[tuple[str, bool]] = []

    def speak(self, text: str, interrupt: bool = True) -> None:
        self.spoken.append((text, interrupt))

    @property
    def last_speech(self) -> str:
        return self.spoken[-1][0] if self.spoken else ""
