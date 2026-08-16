from __future__ import annotations


class FakeSpeech:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def speak(self, text: str, interrupt: bool = True) -> None:
        self.calls.append((text, interrupt))
