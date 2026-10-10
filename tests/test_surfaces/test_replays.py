from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from stonereader.db import delete_deck, get_all_decks
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


def _replays(db_conn: sqlite3.Connection, tmp_path: Path) -> Harness[RecordsContext]:
    return make_records_harness(db_conn, tmp_path / "replays")


def test_rows_are_newest_first_title_lines_then_import(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _replays(db_conn, tmp_path)
    store = harness.context.store
    save_game(
        store,
        result="WON",
        opponent_class="MAGE",
        deck_name="Odd Hunter",
        played_at="2026-08-16T15:36:00",
    )
    save_game(
        store,
        result="LOST",
        opponent_class="DEATHKNIGHT",
        turns=1,
        game_type="CASUAL",
        format_type="WILD",
        source="manual_import",
        in_stats=False,
        played_at="2026-08-15T21:10:00",
    )
    save_game(
        store,
        result="TIED",
        opponent_class="PRIEST",
        turns=12,
        game_type="",
        format_type="",
        played_at="2026-08-12T09:05:00",
    )
    save_game(
        store,
        result="UNKNOWN",
        opponent_class="WARRIOR",
        turns=5,
        game_type="VS_AI",
        format_type="UNKNOWN",
        played_at="2026-08-09T23:59:00",
    )
    save_game(
        store,
        result="WON",
        opponent_class="DEMONHUNTER",
        game_type="UNKNOWN",
        played_at="2025-12-31T08:00:00",
    )

    harness.nav.jump("Replays")

    assert option_titles(harness, "Replays") == [
        "Won against Mage in 8 turns, today 3:36 PM, Odd Hunter",
        "Lost to Death Knight in 1 turn, yesterday 9:10 PM, Casual, Wild, "
        "imported, not counted",
        "Tied with Priest in 12 turns, Wednesday",
        "Result unknown against Warrior in 5 turns, August 9, Practice",
        "Won against Demon Hunter in 8 turns, December 31, 2025",
        "Import replays…",
    ]
    assert harness.titles[-1] == "Replays — StoneReader"
    assert harness.speech.calls[-1] == (
        "Replays, Won against Mage in 8 turns, today 3:36 PM, Odd Hunter",
        True,
    )


def test_a_utc_stamp_is_spoken_in_local_time(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _replays(db_conn, tmp_path)
    # Live-recorded games are stamped in UTC; 3:36 PM here is some UTC time.
    local = datetime(2026, 8, 16, 15, 36).astimezone()
    save_game(
        harness.context.store,
        played_at=local.astimezone(timezone.utc).isoformat(),
    )

    harness.nav.jump("Replays")

    assert option_titles(harness, "Replays")[0] == (
        "Won against Mage in 8 turns, today 3:36 PM"
    )


def test_space_toggles_cursor_neutrally_and_import_row_is_noop(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _replays(db_conn, tmp_path)
    replay = save_game(harness.context.store, in_stats=False)
    harness.nav.jump("Replays")
    harness.speech.calls.clear()

    harness.press(Chord("space"))
    assert harness.context.store.all_replays()[0].in_stats is True
    assert option_titles(harness, "Replays")[0] == (
        "Won against Mage in 8 turns, today 3:36 PM"
    )
    assert harness.speech.calls == [("Included in stats", True)]

    harness.press(Chord("space"))
    assert harness.context.store.all_replays()[0].in_stats is False
    assert option_titles(harness, "Replays")[0] == (
        "Won against Mage in 8 turns, today 3:36 PM, not counted"
    )
    assert harness.speech.calls[-1] == ("Excluded from stats", True)
    assert harness.menu("Replays").cursor == 0

    harness.press(Chord("end"))
    harness.press(Chord("space"))
    assert harness.speech.calls[-1] == ("Nothing to count here", True)
    assert Path(replay.file_path).exists()


def test_armed_delete_lifecycle_and_shift_delete_reenter(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _replays(db_conn, tmp_path)
    store = harness.context.store
    first = save_game(store, played_at="2026-08-16T15:36:00")
    second = save_game(store, result="LOST", played_at="2026-08-15T21:10:00")
    harness.nav.jump("Replays")
    harness.speech.calls.clear()

    harness.press(Chord("delete"))
    harness.press(Chord("down"))
    harness.press(Chord("up"))
    harness.press(Chord("delete"))
    harness.press(Chord("delete"))

    assert [meta.id for meta in store.all_replays()] == [second.id]
    assert not Path(first.file_path).exists()
    assert harness.speech.calls[-2:] == [
        ("Replay deleted", True),
        ("Replays, Lost to Mage in 8 turns, yesterday 9:10 PM", False),
    ]

    harness.press(Chord("delete", shift=True))
    assert store.all_replays() == []
    assert harness.speech.calls[-2:] == [
        ("Replay deleted", True),
        ("Replays, Import replays…", False),
    ]

    harness.press(Chord("delete"))
    assert harness.speech.calls[-1] == ("Nothing to delete here", True)


def test_enter_opens_the_replay_or_import_and_search_is_a_noop(
    db_conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = _replays(db_conn, tmp_path)
    meta = save_game(harness.context.store)
    opened: list[Path] = []
    loaded = object()

    def load(path: Path, _card_db: object) -> object:
        opened.append(path)
        return loaded

    monkeypatch.setattr("stonereader.surfaces._replay_rows.load_replay", load)
    harness.nav.jump("Replays")

    harness.press(Chord("enter"))
    assert opened == [Path(meta.file_path)]
    assert harness.context.current_replay.get() is loaded
    assert harness.nav.stack == ("Home", "Replays", "Replay Viewer")

    harness.nav.back()
    harness.press(Chord("end"))
    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Replays", "Import Replays")

    harness.nav.back()
    harness.press(Chord("f", ctrl=True))
    assert harness.speech.calls[-1] == ("No search on this screen", True)


def test_invalid_replay_is_announced_without_navigation(
    db_conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = _replays(db_conn, tmp_path)
    save_game(harness.context.store)

    def fail(_path: Path, _card_db: object) -> object:
        raise ReplayLoadError("bad replay")

    monkeypatch.setattr("stonereader.surfaces._replay_rows.load_replay", fail)
    harness.nav.jump("Replays")
    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home", "Replays")
    assert harness.speech.calls[-1] == (
        "Could not open replay; the file may be invalid",
        True,
    )


def test_d_opens_the_deck_page_of_a_saved_deck(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _replays(db_conn, tmp_path)
    deck_id = save_full_deck(db_conn, "Odd Hunter", "HUNTER")
    save_game(harness.context.store, deck_id=deck_id, deck_name="Odd Hunter")
    harness.nav.jump("Replays")

    harness.press(Chord("d"))

    assert harness.nav.stack == ("Home", "Replays", "Deck")
    assert harness.titles[-1] == "Odd Hunter — StoneReader"
    assert harness.speech.calls[-1] == ("Odd Hunter, Cards, 30", True)

    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Replays", "Deck", "Games")

    harness.press(Chord("escape"))
    harness.press(Chord("delete", shift=True))
    assert get_all_decks(db_conn) == []
    assert harness.nav.stack == ("Home", "Replays")
    assert harness.speech.calls[-2:] == [
        ("Odd Hunter deleted", True),
        ("Replays, Won against Mage in 8 turns, today 3:36 PM, Odd Hunter", False),
    ]


def test_d_without_a_saved_deck_announces_and_stays(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _replays(db_conn, tmp_path)
    store = harness.context.store
    gone = save_full_deck(db_conn, "Gone", "MAGE")
    delete_deck(db_conn, gone)
    save_game(store, deck_id=gone, deck_name="Gone", played_at="2026-08-16T15:36:00")
    save_game(store, played_at="2026-08-16T14:00:00")
    harness.nav.jump("Replays")
    harness.speech.calls.clear()

    harness.press(Chord("d"))
    harness.press(Chord("down"))
    harness.press(Chord("d"))
    harness.press(Chord("down"))
    harness.press(Chord("d"))

    assert harness.nav.stack == ("Home", "Replays")
    assert harness.speech.calls == [
        ("No saved deck for this game", True),
        ("Won against Mage in 8 turns, today 2:00 PM", True),
        ("No saved deck for this game", True),
        ("Import replays…", True),
        ("Nothing to open here", True),
    ]
