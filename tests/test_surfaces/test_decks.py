from __future__ import annotations

import sqlite3
from pathlib import Path

from stonereader.db import delete_deck, get_all_decks
from stonereader.ui.chords import Chord

from .conftest import Harness
from .records_harness import (
    RecordsContext,
    make_records_harness,
    option_titles,
    save_full_deck,
    save_game,
)


def _decks(db_conn: sqlite3.Connection, tmp_path: Path) -> Harness[RecordsContext]:
    harness = make_records_harness(db_conn, tmp_path / "replays")
    return harness


def test_options_are_all_decks_saved_decks_other_games_then_import(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _decks(db_conn, tmp_path)
    store = harness.context.store
    hunter = save_full_deck(db_conn, "Odd Hunter", "HUNTER")
    knight = save_full_deck(
        db_conn, "Blood Control", "DEATHKNIGHT", format_name="Wild", cards=29
    )
    save_full_deck(db_conn, "Empty Mage", "MAGE")
    gone = save_full_deck(db_conn, "Gone", "PRIEST")
    delete_deck(db_conn, gone)
    save_game(store, deck_id=hunter, result="WON")
    save_game(store, deck_id=hunter, result="LOST")
    save_game(store, deck_id=knight, result="WON")
    save_game(store, deck_id=knight, result="WON")
    save_game(store, deck_id=knight, result="TIED")
    save_game(store, deck_id=gone, deck_name="Gone", result="LOST")
    save_game(store, result="LOST")
    save_game(store, deck_id=hunter, in_stats=False)

    harness.nav.jump("Decks")

    assert option_titles(harness, "Decks") == [
        "All decks, 3 wins, 3 losses, 1 tie",
        "Empty Mage, no games yet",
        "Blood Control, Death Knight, Wild, 29 cards, 2 wins, 0 losses, 1 tie",
        "Odd Hunter, 1 win, 1 loss",
        "Other games, 0 wins, 2 losses",
        "Import deck…",
    ]
    assert harness.titles[-1] == "Decks — StoneReader"
    assert harness.speech.calls[-1] == (
        "Decks, All decks, 3 wins, 3 losses, 1 tie",
        True,
    )


def test_other_games_appears_only_when_the_corpus_holds_some(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _decks(db_conn, tmp_path)
    harness.nav.jump("Decks")

    assert option_titles(harness, "Decks") == [
        "All decks, no games yet",
        "Import deck…",
    ]


def test_enter_opens_the_deck_page_for_each_record_and_import(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _decks(db_conn, tmp_path)
    save_full_deck(db_conn, "Odd Hunter", "HUNTER")
    save_game(harness.context.store)
    harness.nav.jump("Decks")

    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Decks", "Deck")
    assert harness.titles[-1] == "All decks — StoneReader"
    assert harness.speech.calls[-1] == (
        "All decks, Games, 1 win, 0 losses, 100 percent",
        True,
    )

    harness.press(Chord("escape"))
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert harness.titles[-1] == "Odd Hunter — StoneReader"
    assert harness.speech.calls[-1] == ("Odd Hunter, Cards, 30", True)

    harness.press(Chord("escape"))
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert harness.titles[-1] == "Other games — StoneReader"
    assert harness.speech.calls[-1] == (
        "Other games, Games, 1 win, 0 losses, 100 percent",
        True,
    )

    harness.press(Chord("escape"))
    harness.press(Chord("end"))
    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Decks", "Import Deck")


def test_armed_delete_move_disarms_then_repeat_deletes_with_continuing_reentry(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _decks(db_conn, tmp_path)
    save_full_deck(db_conn, "Aggro Shaman", "SHAMAN")
    harness.nav.jump("Decks")
    harness.press(Chord("down"))
    harness.speech.calls.clear()

    harness.press(Chord("delete"))
    harness.press(Chord("down"))
    harness.press(Chord("up"))
    harness.press(Chord("delete"))
    harness.press(Chord("delete"))

    assert get_all_decks(db_conn) == []
    assert harness.speech.calls == [
        ("Press Delete again to delete Aggro Shaman", True),
        ("Import deck…", True),
        ("Aggro Shaman, no games yet", True),
        ("Press Delete again to delete Aggro Shaman", True),
        ("Aggro Shaman deleted", True),
        ("Decks, Import deck…", False),
    ]


def test_shift_delete_is_immediate(db_conn: sqlite3.Connection, tmp_path: Path) -> None:
    harness = _decks(db_conn, tmp_path)
    save_full_deck(db_conn, "Tempo Mage", "MAGE")
    harness.nav.jump("Decks")
    harness.press(Chord("down"))
    harness.speech.calls.clear()

    harness.press(Chord("delete", shift=True))

    assert get_all_decks(db_conn) == []
    assert harness.speech.calls == [
        ("Tempo Mage deleted", True),
        ("Decks, Import deck…", False),
    ]


def test_copy_confirms_marks_seen_and_own_copy_never_offers(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _decks(db_conn, tmp_path)
    save_full_deck(db_conn, "Copy Me", "MAGE")
    code = get_all_decks(db_conn)[0].deckstring
    harness.nav.jump("Decks")
    harness.press(Chord("down"))
    harness.speech.calls.clear()

    harness.press(Chord("c"))

    assert harness.context.copied == [code]
    assert harness.speech.calls == [("Deck code copied", True)]
    assert harness.sink.arm_offer(code, lambda: None) is False


def test_non_deck_options_get_exact_delete_and_copy_noops(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    harness = _decks(db_conn, tmp_path)
    save_game(harness.context.store)
    harness.nav.jump("Decks")
    harness.speech.calls.clear()

    for _option in ("All decks", "Other games", "Import deck…"):
        for chord in (Chord("delete"), Chord("delete", shift=True), Chord("c")):
            harness.press(chord)
        harness.press(Chord("down"))

    assert harness.speech.calls == [
        ("Nothing to delete here", True),
        ("Nothing to delete here", True),
        ("Nothing to copy here", True),
        ("Other games, 1 win, 0 losses", True),
        ("Nothing to delete here", True),
        ("Nothing to delete here", True),
        ("Nothing to copy here", True),
        ("Import deck…", True),
        ("Nothing to delete here", True),
        ("Nothing to delete here", True),
        ("Nothing to copy here", True),
        ("Import deck…", True),
    ]
