from __future__ import annotations

import sqlite3
from pathlib import Path

from stonereader.db import get_all_decks
from stonereader.ui.chords import Chord

from .conftest import Harness
from .records_harness import (
    RecordsContext,
    make_records_harness,
    option_titles,
    save_full_deck,
    save_game,
)

ODD_HUNTER_PAGE = [
    "Cards, 30",
    "Games, 2 wins, 1 loss, 1 tie, 67 percent",
    "Versus Mage, 1 win, 1 loss, 1 tie",
    "Versus Warrior, 1 win, 0 losses",
    "Copy deck code",
    "Delete deck",
]


def _odd_hunter(db_conn: sqlite3.Connection, tmp_path: Path) -> Harness[RecordsContext]:
    """Odd Hunter with four games, opened from Decks as the User would."""
    harness = make_records_harness(db_conn, tmp_path / "replays")
    store = harness.context.store
    deck_id = save_full_deck(db_conn, "Odd Hunter", "HUNTER")
    for result, opponent_class, played_at in (
        ("WON", "MAGE", "2026-08-16T15:36:00"),
        ("LOST", "MAGE", "2026-08-15T21:10:00"),
        ("WON", "WARRIOR", "2026-08-12T09:05:00"),
        ("TIED", "MAGE", "2026-08-01T12:00:00"),
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
    return harness


def _open_option(harness: Harness[RecordsContext], index: int) -> None:
    harness.menu("Deck").set_cursor(index)
    harness.press(Chord("enter"))


def test_saved_deck_page_lands_on_its_name_with_every_row(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)

    assert harness.nav.stack == ("Home", "Decks", "Deck")
    assert harness.titles[-1] == "Odd Hunter — StoneReader"
    assert harness.speech.calls[-1] == ("Odd Hunter, Cards, 30", True)
    assert option_titles(harness, "Deck") == ODD_HUNTER_PAGE


def test_every_record_row_opens_exactly_the_games_it_counts(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)

    _open_option(harness, 1)
    assert harness.nav.stack == ("Home", "Decks", "Deck", "Games")
    assert harness.titles[-1] == "Odd Hunter games — StoneReader"
    assert harness.speech.calls[-1] == (
        "Odd Hunter games, Won against Mage in 8 turns, today 3:36 PM",
        True,
    )
    assert option_titles(harness, "Games") == [
        "Won against Mage in 8 turns, today 3:36 PM",
        "Lost to Mage in 8 turns, yesterday 9:10 PM",
        "Won against Warrior in 8 turns, Wednesday",
        "Tied with Mage in 8 turns, August 1",
    ]

    harness.press(Chord("escape"))
    _open_option(harness, 2)
    assert harness.titles[-1] == "Odd Hunter versus Mage — StoneReader"
    assert option_titles(harness, "Games") == [
        "Won against Mage in 8 turns, today 3:36 PM",
        "Lost to Mage in 8 turns, yesterday 9:10 PM",
        "Tied with Mage in 8 turns, August 1",
    ]

    harness.press(Chord("escape"))
    _open_option(harness, 3)
    assert harness.speech.calls[-1] == (
        "Odd Hunter versus Warrior, Won against Warrior in 8 turns, Wednesday",
        True,
    )
    assert option_titles(harness, "Games") == [
        "Won against Warrior in 8 turns, Wednesday",
    ]


def test_back_from_games_finds_the_deck_page_as_left(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)
    harness.press(Chord("down"))
    harness.press(Chord("down"))
    harness.press(Chord("enter"))

    harness.press(Chord("escape"))

    assert harness.nav.stack == ("Home", "Decks", "Deck")
    assert harness.speech.calls[-1] == (
        "Odd Hunter, Versus Mage, 1 win, 1 loss, 1 tie",
        True,
    )


def test_last_20_games_appears_above_twenty_and_opens_those_twenty(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = make_records_harness(db_conn, tmp_path / "replays")
    store = harness.context.store
    deck_id = save_full_deck(db_conn, "Long", "WARRIOR")
    for day in range(2, 22):
        save_game(
            store,
            result="WON" if day % 2 else "LOST",
            opponent_class="PRIEST",
            deck_id=deck_id,
            played_at=f"2025-07-{day:02d}T12:00:00",
        )
    harness.nav.jump("Decks")
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert option_titles(harness, "Deck")[1:3] == [
        "Games, 10 wins, 10 losses, 50 percent",
        "Versus Priest, 10 wins, 10 losses",
    ]

    harness.press(Chord("escape"))
    save_game(
        store,
        result="WON",
        opponent_class="PRIEST",
        deck_id=deck_id,
        played_at="2025-07-01T12:00:00",
    )
    harness.press(Chord("enter"))
    assert option_titles(harness, "Deck")[1:4] == [
        "Games, 11 wins, 10 losses, 52 percent",
        "Last 20 games, 10 wins, 10 losses",
        "Versus Priest, 11 wins, 10 losses",
    ]

    _open_option(harness, 2)
    assert harness.titles[-1] == "Long, last 20 games — StoneReader"
    games = option_titles(harness, "Games")
    assert len(games) == 20
    assert games[0] == "Won against Priest in 8 turns, July 21, 2025"
    assert games[-1] == "Lost to Priest in 8 turns, July 2, 2025"
    assert "Won against Priest in 8 turns, July 1, 2025" not in games


def test_a_deck_with_no_games_says_so_and_enter_stays(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = make_records_harness(db_conn, tmp_path / "replays")
    save_full_deck(db_conn, "Fresh", "DRUID", cards=28)
    harness.nav.jump("Decks")
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert option_titles(harness, "Deck") == [
        "Cards, 28",
        "Games, none yet",
        "Copy deck code",
        "Delete deck",
    ]

    harness.press(Chord("down"))
    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home", "Decks", "Deck")
    assert harness.speech.calls[-1] == ("No games yet", True)


def test_games_with_no_decided_result_omit_the_percent(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = make_records_harness(db_conn, tmp_path / "replays")
    save_game(harness.context.store, result="UNKNOWN", opponent_class="DEATHKNIGHT")
    harness.nav.jump("Decks")
    harness.press(Chord("enter"))

    assert option_titles(harness, "Deck") == [
        "Games, 0 wins, 0 losses",
        "Versus Death Knight, 0 wins, 0 losses",
    ]


def test_all_decks_and_other_games_pages_name_their_games(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)
    save_game(
        harness.context.store,
        result="LOST",
        opponent_class="MAGE",
        game_type="CASUAL",
        played_at="2026-08-16T10:00:00",
    )
    harness.press(Chord("escape"))
    harness.press(Chord("home"))
    harness.press(Chord("enter"))
    assert harness.titles[-1] == "All decks — StoneReader"
    assert option_titles(harness, "Deck") == [
        "Games, 2 wins, 2 losses, 1 tie, 50 percent",
        "Versus Mage, 1 win, 2 losses, 1 tie",
        "Versus Warrior, 1 win, 0 losses",
    ]
    harness.press(Chord("enter"))
    assert harness.titles[-1] == "All games — StoneReader"
    assert option_titles(harness, "Games")[:2] == [
        "Won against Mage in 8 turns, today 3:36 PM, Odd Hunter",
        "Lost to Mage in 8 turns, today 10:00 AM, Casual",
    ]

    harness.press(Chord("escape"))
    harness.press(Chord("escape"))
    harness.press(Chord("end"))
    harness.press(Chord("up"))
    harness.press(Chord("enter"))
    assert harness.titles[-1] == "Other games — StoneReader"
    assert option_titles(harness, "Deck") == [
        "Games, 0 wins, 1 loss, 0 percent",
        "Versus Mage, 0 wins, 1 loss",
    ]
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == (
        "Other games versus Mage, Lost to Mage in 8 turns, today 10:00 AM, Casual",
        True,
    )


def test_pool_pages_announce_delete_and_copy_noops(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = make_records_harness(db_conn, tmp_path / "replays")
    harness.nav.jump("Decks")
    harness.press(Chord("enter"))
    harness.speech.calls.clear()

    for chord in (Chord("delete"), Chord("delete", shift=True), Chord("c")):
        harness.press(chord)

    assert harness.speech.calls == [
        ("Nothing to delete here", True),
        ("Nothing to delete here", True),
        ("Nothing to copy here", True),
    ]


def test_delete_deck_arms_on_enter_and_deletes_on_the_second(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)
    harness.press(Chord("end"))
    harness.speech.calls.clear()

    harness.press(Chord("enter"))
    harness.press(Chord("up"))
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert get_all_decks(db_conn) != []
    harness.press(Chord("enter"))

    assert get_all_decks(db_conn) == []
    assert harness.nav.stack == ("Home", "Decks")
    assert harness.titles[-1] == "Decks — StoneReader"
    assert harness.speech.calls == [
        ("Press Enter again to delete Odd Hunter", True),
        ("Copy deck code", True),
        ("Delete deck", True),
        ("Press Enter again to delete Odd Hunter", True),
        ("Odd Hunter deleted", True),
        ("Decks, Other games, 2 wins, 1 loss, 1 tie", False),
    ]


def test_delete_shift_delete_and_copy_work_anywhere_on_the_page(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)
    code = get_all_decks(db_conn)[0].deckstring
    harness.speech.calls.clear()

    harness.press(Chord("c"))
    harness.press(Chord("delete"))
    harness.press(Chord("delete"))

    assert harness.context.copied == [code]
    assert get_all_decks(db_conn) == []
    assert harness.speech.calls == [
        ("Deck code copied", True),
        ("Press Delete again to delete Odd Hunter", True),
        ("Odd Hunter deleted", True),
        ("Decks, Other games, 2 wins, 1 loss, 1 tie", False),
    ]

    save_full_deck(db_conn, "Burn Mage", "MAGE")
    harness.press(Chord("enter"))
    harness.press(Chord("down"))
    harness.speech.calls.clear()
    harness.press(Chord("delete", shift=True))

    assert get_all_decks(db_conn) == []
    assert harness.speech.calls == [
        ("Burn Mage deleted", True),
        ("Decks, Other games, 2 wins, 1 loss, 1 tie", False),
    ]


def test_copy_deck_code_option_copies(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)
    harness.press(Chord("end"))
    harness.press(Chord("up"))

    harness.press(Chord("enter"))

    assert harness.context.copied == [get_all_decks(db_conn)[0].deckstring]
    assert harness.speech.calls[-1] == ("Deck code copied", True)


def test_cards_opens_deck_detail_and_back_returns_to_the_page(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)

    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Decks", "Deck", "Deck detail")
    assert harness.titles[-1] == "Odd Hunter cards — StoneReader"
    assert harness.speech.calls[-1] == (
        "Odd Hunter cards, Arcane Shot x30, 1 of 1",
        True,
    )

    harness.press(Chord("escape"))
    assert harness.speech.calls[-1] == ("Odd Hunter, Cards, 30", True)


def test_each_open_starts_at_the_top(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _odd_hunter(db_conn, tmp_path)
    harness.press(Chord("down"))
    harness.press(Chord("down"))
    harness.press(Chord("escape"))

    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Odd Hunter, Cards, 30", True)

    save_full_deck(db_conn, "Burn Mage", "MAGE", cards=29)
    harness.press(Chord("down"))
    harness.press(Chord("escape"))
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Burn Mage, Cards, 29", True)
