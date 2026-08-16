from __future__ import annotations

from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.text_mode import TextSession

from .conftest import FakeSpeech


def make_session(
    speech: FakeSpeech,
    *,
    initial: str = "",
    commits: list[str] | None = None,
    abandons: list[str] | None = None,
) -> TextSession:
    commit_log = [] if commits is None else commits
    abandon_log = [] if abandons is None else abandons
    return TextSession(
        "Deck code",
        initial,
        Announcer(speech),
        commit_log.append,
        lambda: abandon_log.append("abandoned"),
    )


def test_typing_echoes_and_honors_shift_and_base64_symbols() -> None:
    speech = FakeSpeech()
    session = make_session(speech)
    for chord in [
        Chord("a"),
        Chord("b", shift=True),
        Chord("space"),
        Chord("=", shift=True),
        Chord("/"),
        Chord("="),
    ]:
        assert session.handle(chord) is True
    assert session.text == "aB +/="
    assert session.caret == 6
    assert [text for text, _interrupt in speech.calls] == list("aB +/=")


def test_backspace_erases_and_speaks_character() -> None:
    speech = FakeSpeech()
    session = make_session(speech, initial="abc")
    session.handle(Chord("backspace"))
    assert session.text == "ab"
    assert session.caret == 2
    assert speech.calls == [("c", True)]


def test_caret_movement_speaks_crossed_character_and_boundaries_are_silent() -> None:
    speech = FakeSpeech()
    session = make_session(speech, initial="ab")
    session.handle(Chord("right"))
    session.handle(Chord("left"))
    session.handle(Chord("left"))
    session.handle(Chord("left"))
    session.handle(Chord("right"))
    assert [text for text, _interrupt in speech.calls] == ["b", "a", "a"]


def test_home_and_end_move_without_inventing_speech() -> None:
    speech = FakeSpeech()
    session = make_session(speech, initial="abc")
    session.handle(Chord("home"))
    assert session.caret == 0
    session.handle(Chord("end"))
    assert session.caret == 3
    assert speech.calls == []


def test_enter_commits_final_text_and_escape_abandons() -> None:
    speech = FakeSpeech()
    commits: list[str] = []
    abandons: list[str] = []
    session = make_session(speech, initial="code", commits=commits, abandons=abandons)
    session.handle(Chord("enter"))
    session.handle(Chord("escape"))
    assert commits == ["code"]
    assert abandons == ["abandoned"]


def test_f1_rescue_is_exact_and_does_not_leave() -> None:
    speech = FakeSpeech()
    session = make_session(speech)
    assert session.handle(Chord("f1")) is True
    assert speech.calls == [
        ("Typing in Deck code. Enter commits, Escape cancels.", True)
    ]


def test_unlisted_chord_is_consumed_and_ignored() -> None:
    speech = FakeSpeech()
    session = make_session(speech, initial="x")
    assert session.handle(Chord("q", ctrl=True)) is True
    assert session.text == "x"
    assert speech.calls == []
