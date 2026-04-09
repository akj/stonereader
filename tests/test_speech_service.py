from stonereader.speech_service import SpeechService


def test_speech_service_creates_without_error():
    svc = SpeechService()
    assert svc is not None


def test_speak_does_not_raise(capsys):
    svc = SpeechService()
    svc.speak("hello")
    # On CI/dev without a screen reader, falls back to stdout
    captured = capsys.readouterr()
    assert "hello" in captured.out


def test_speak_queued_does_not_interrupt(capsys):
    svc = SpeechService()
    svc.speak_queued("queued text")
    captured = capsys.readouterr()
    assert "queued text" in captured.out


def test_speak_interrupt_default_is_true(capsys):
    svc = SpeechService()
    svc.speak("first")
    svc.speak("second")
    captured = capsys.readouterr()
    assert "first" in captured.out
    assert "second" in captured.out
