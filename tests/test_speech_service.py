from __future__ import annotations

from stonereader.speech_service import SpeechService


class RecordingOutput:
    """Stand in for the screen reader so the suite never speaks aloud."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []
        self.silences = 0

    def speak(self, text: str, interrupt: bool = True) -> None:
        self.calls.append((text, interrupt))

    def silence(self) -> None:
        self.silences += 1


class BrokenOutput:
    def speak(self, text: str, interrupt: bool = True) -> None:
        raise RuntimeError("screen reader went away")

    def silence(self) -> None:
        raise RuntimeError("screen reader went away")


def test_speech_service_creates_without_error():
    assert SpeechService(RecordingOutput()) is not None


def test_speak_reaches_the_output_and_interrupts_by_default():
    output = RecordingOutput()
    svc = SpeechService(output)
    svc.speak("first")
    svc.speak("second", interrupt=False)
    assert output.calls == [("first", True), ("second", False)]


def test_silence_cuts_and_discards():
    output = RecordingOutput()
    svc = SpeechService(output)
    svc.silence()
    assert output.silences == 1


def test_a_failing_output_falls_back_to_stdout_without_raising(capsys):
    svc = SpeechService(BrokenOutput())
    svc.speak("hello")
    svc.silence()
    assert "hello" in capsys.readouterr().out
