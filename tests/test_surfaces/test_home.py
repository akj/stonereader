from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from stonereader.models.game_state import GameState, Hero
from stonereader.surfaces.home import build_home
from stonereader.surfaces.live_game import CurrentGame
from stonereader.ui.chords import Chord

from .conftest import Harness, make_harness


def make_home(current_game: CurrentGame | None = None) -> Harness[list[str]]:
    actions: list[str] = []
    harness = make_harness(actions)
    names = ["Live Game", "Decks", "Cards", "Replays", "Settings"]
    targets: dict[str, Callable[[], None]] = {
        name: lambda name=name: actions.append(name) for name in names
    }
    harness.set_surface(
        build_home(
            harness.announcer,
            [],
            harness.nav,
            targets,
            current_game or CurrentGame(),
        )
    )
    return harness


def _game(turn: int) -> GameState:
    return GameState(
        turn=turn,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=Hero("p", "Jaina", 30, 0, "", "MAGE"),
        opponent_hero=Hero("o", "The Lich King", 30, 0, "", "DEATHKNIGHT"),
    )


def test_options_are_in_order_and_letters_activate_targets() -> None:
    harness = make_home()
    assert harness.vertical.options_snapshot() == (
        [
            "Live Game, waiting for a game",
            "Decks",
            "Cards",
            "Replays",
            "Settings",
        ],
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
    assert harness.speech.calls == [("Home, Live Game, waiting for a game", True)]


def test_live_game_option_follows_the_running_game_silently() -> None:
    current_game = CurrentGame()
    harness = make_home(current_game)
    renders: list[str] = []
    harness.vertical.subscribe(
        lambda: renders.append(harness.vertical.options_snapshot()[0][0])
    )

    current_game.on_state(None, _game(0))
    current_game.on_state(_game(0), _game(5))
    harness.vertical.on_landing()
    current_game.on_state(_game(5), replace(_game(6), game_state="COMPLETE"))

    # The mulligan reads as turn 1, the number the Replay Viewer gives it.
    # Landing redraws too, since a landing can follow unseen changes.
    assert renders == [
        "Live Game, turn 1 versus Death Knight",
        "Live Game, turn 5 versus Death Knight",
        "Live Game, turn 5 versus Death Knight",
        "Live Game, waiting for a game",
    ]
    assert harness.speech.calls == [
        ("Home, Live Game, turn 5 versus Death Knight", True)
    ]


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
        ("Live Game, waiting for a game", True),
        ("Home, Live Game, waiting for a game", True),
    ]
