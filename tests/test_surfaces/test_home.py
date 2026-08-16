from __future__ import annotations

from collections.abc import Callable

from stonereader.surfaces.home import build_home
from stonereader.ui.chords import Chord

from .conftest import Harness, make_harness


def make_home() -> Harness[list[str]]:
    actions: list[str] = []
    harness = make_harness(actions)
    names = ["Live Game", "Decks", "Cards", "Replays", "Settings"]
    targets: dict[str, Callable[[], None]] = {
        name: lambda name=name: actions.append(name) for name in names
    }
    harness.set_surface(
        build_home(harness.announcer, [], harness.nav, targets)
    )
    return harness


def test_options_are_in_order_and_letters_activate_targets() -> None:
    harness = make_home()
    assert harness.vertical.options_snapshot() == (
        ["Live Game", "Decks", "Cards", "Replays", "Settings"],
        0,
    )

    for letter in ("l", "d", "c", "r", "s"):
        assert harness.press(Chord(letter)) is True

    assert harness.context == ["Live Game", "Decks", "Cards", "Replays", "Settings"]


def test_enter_acts_on_current_option() -> None:
    harness = make_home()
    harness.press(Chord("down"))
    harness.press(Chord("down"))
    assert harness.press(Chord("enter")) is True
    assert harness.context == ["Cards"]


def test_entry_utterance_is_exact() -> None:
    harness = make_home()
    harness.vertical.on_landing()
    assert harness.speech.calls == [("Home, Live Game", True)]


def test_reserved_and_nonuniversal_unbound_keys_are_silent() -> None:
    harness = make_home()
    for chord in (Chord("b"), Chord("o"), Chord("delete"), Chord("space")):
        assert harness.press(chord) is False
    assert harness.speech.calls == []


def test_unfilled_slots_announce_their_defaults() -> None:
    harness = make_home()
    for chord in (Chord("tab"), Chord("pageup"), Chord("f", ctrl=True)):
        assert harness.press(chord) is True
    assert harness.speech.calls == [
        ("No groups on this screen", True),
        ("No pages on this screen", True),
        ("No search on this screen", True),
    ]


def test_boundary_and_orientation_reread_use_vertical_menu_speech() -> None:
    harness = make_home()
    assert harness.press(Chord("up")) is True
    assert harness.press(Chord("up", shift=True)) is True
    assert harness.speech.calls == [
        ("Live Game", True),
        ("Home, Live Game", True),
    ]
