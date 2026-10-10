from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from stonereader.services._replay_loader import ReplayLoadError
from stonereader.ui.chords import Chord

from .conftest import Harness
from .records_harness import (
    RecordsContext,
    make_records_harness,
    option_titles,
    save_full_deck,
    save_game,
)


def _odd_hunter_games(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> Harness[RecordsContext]:
    """Open Odd Hunter's Games row from Decks, as the User would."""
    harness = make_records_harness(db_conn, tmp_path / "replays")
    store = harness.context.store
    deck_id = save_full_deck(db_conn, "Odd Hunter", "HUNTER")
    for result, opponent_class, played_at in (
        ("WON", "MAGE", "2026-08-16T15:36:00"),
        ("LOST", "MAGE", "2026-08-15T21:10:00"),
        ("WON", "WARRIOR", "2026-08-12T09:05:00"),
    ):
        save_game(
            store,
            result=result,
            opponent_class=opponent_class,
            deck_id=deck_id,
            deck_name="Odd Hunter",
            played_at=played_at,
        )
    harness.nav.jump("Decks")
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    return harness


def test_enter_opens_the_replay_through_the_shared_open_path(
    db_conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = _odd_hunter_games(db_conn, tmp_path)
    opened: list[Path] = []
    loaded = object()

    def load(path: Path, _card_db: object) -> object:
        opened.append(path)
        return loaded

    monkeypatch.setattr("stonereader.surfaces._replay_rows.load_replay", load)
    harness.press(Chord("down"))

    harness.press(Chord("enter"))

    newest_second = harness.context.store.all_replays()[1]
    assert opened == [Path(newest_second.file_path)]
    assert harness.context.current_replay.get() is loaded
    assert harness.nav.stack == ("Home", "Decks", "Deck", "Games", "Replay Viewer")


def test_an_invalid_replay_is_announced_without_navigation(
    db_conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = _odd_hunter_games(db_conn, tmp_path)

    def fail(_path: Path, _card_db: object) -> object:
        raise ReplayLoadError("bad replay")

    monkeypatch.setattr("stonereader.surfaces._replay_rows.load_replay", fail)
    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home", "Decks", "Deck", "Games")
    assert harness.speech.calls[-1] == (
        "Could not open replay; the file may be invalid",
        True,
    )


def test_armed_delete_removes_the_game_and_the_deck_page_follows(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter_games(db_conn, tmp_path)
    newest = harness.context.store.all_replays()[0]
    harness.speech.calls.clear()

    harness.press(Chord("delete"))
    harness.press(Chord("down"))
    harness.press(Chord("up"))
    harness.press(Chord("delete"))
    harness.press(Chord("delete"))

    remaining = [meta.id for meta in harness.context.store.all_replays()]
    assert len(remaining) == 2
    assert newest.id not in remaining
    assert not Path(newest.file_path).exists()
    assert harness.speech.calls == [
        ("Press Delete again to delete this replay", True),
        ("Lost to Mage in 8 turns, yesterday 9:10 PM", True),
        ("Won against Mage in 8 turns, today 3:36 PM", True),
        ("Press Delete again to delete this replay", True),
        ("Replay deleted", True),
        ("Odd Hunter games, Lost to Mage in 8 turns, yesterday 9:10 PM", False),
    ]

    harness.press(Chord("escape"))
    assert harness.speech.calls[-1] == (
        "Odd Hunter, Games, 1 win, 1 loss, 50 percent",
        True,
    )


def test_shift_delete_is_immediate_and_an_emptied_list_says_so(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter_games(db_conn, tmp_path)
    harness.press(Chord("escape"))
    harness.press(Chord("end"))
    harness.press(Chord("up"))
    harness.press(Chord("up"))
    harness.press(Chord("enter"))
    assert option_titles(harness, "Games") == [
        "Won against Warrior in 8 turns, Wednesday",
    ]
    harness.speech.calls.clear()

    harness.press(Chord("delete", shift=True))

    assert len(harness.context.store.all_replays()) == 2
    assert harness.speech.calls == [
        ("Replay deleted", True),
        ("Odd Hunter versus Warrior: empty", False),
    ]


def test_space_and_d_are_unbound_and_silent(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter_games(db_conn, tmp_path)
    harness.speech.calls.clear()

    assert harness.press(Chord("space")) is False
    assert harness.press(Chord("d")) is False
    assert harness.speech.calls == []
    assert all(meta.in_stats for meta in harness.context.store.all_replays())
