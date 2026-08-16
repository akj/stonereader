from __future__ import annotations

from collections.abc import Callable

from stonereader.surfaces.home import build_home
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController

from tests.test_ui.conftest import FakeSpeech


def make_home() -> tuple[ActiveSurface, _SinkCore, FakeSpeech, list[str]]:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    navigation = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda _surface: None,
    )
    actions: list[str] = []
    names = ["Live Game", "Decks", "Cards", "Replays", "Settings"]
    targets: dict[str, Callable[[], None]] = {
        name: lambda name=name: actions.append(name) for name in names
    }
    surface = build_home(announcer, [], navigation, targets)
    sink = _SinkCore(announcer, lambda: None)
    sink.set_active(surface.registry)
    return surface, sink, speech, actions


def test_options_are_in_order_and_letters_activate_targets() -> None:
    surface, sink, _speech, actions = make_home()
    assert isinstance(surface.engine, VerticalMenuEngine)
    assert surface.engine.options_snapshot() == (
        ["Live Game", "Decks", "Cards", "Replays", "Settings"],
        0,
    )

    for letter in ("l", "d", "c", "r", "s"):
        assert sink.handle_chord(Chord(letter)) is True

    assert actions == ["Live Game", "Decks", "Cards", "Replays", "Settings"]


def test_enter_acts_on_current_option() -> None:
    _surface, sink, _speech, actions = make_home()
    sink.handle_chord(Chord("down"))
    sink.handle_chord(Chord("down"))
    assert sink.handle_chord(Chord("enter")) is True
    assert actions == ["Cards"]


def test_entry_utterance_is_exact() -> None:
    surface, _sink, speech, _actions = make_home()
    surface.engine.on_landing()
    assert speech.calls == [("Home, Live Game", True)]


def test_reserved_and_nonuniversal_unbound_keys_are_silent() -> None:
    _surface, sink, speech, _actions = make_home()
    for chord in (Chord("b"), Chord("o"), Chord("delete"), Chord("space")):
        assert sink.handle_chord(chord) is False
    assert speech.calls == []


def test_unfilled_slots_announce_their_defaults() -> None:
    _surface, sink, speech, _actions = make_home()
    for chord in (Chord("tab"), Chord("pageup"), Chord("f", ctrl=True)):
        assert sink.handle_chord(chord) is True
    assert speech.calls == [
        ("No groups on this screen", True),
        ("No pages on this screen", True),
        ("No search on this screen", True),
    ]


def test_boundary_and_orientation_reread_use_vertical_menu_speech() -> None:
    _surface, sink, speech, _actions = make_home()
    assert sink.handle_chord(Chord("up")) is True
    assert sink.handle_chord(Chord("up", shift=True)) is True
    assert speech.calls == [
        ("Live Game", True),
        ("Home, Live Game", True),
    ]
