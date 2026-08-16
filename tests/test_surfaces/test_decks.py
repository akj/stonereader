from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from stonereader.db import get_all_decks, insert_replay, save_deck
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.decks import build_decks
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.chords import Chord

from .conftest import (
    Harness,
    make_card,
    make_card_db,
    make_deckstring,
    make_harness,
    placeholder_surface,
)


class SeenSink:
    def __init__(self) -> None:
        self.subjects: list[str] = []

    def mark_offer_subject_seen(self, subject: str) -> None:
        self.subjects.append(subject)


@dataclass
class DecksContext:
    current: CurrentDeck
    copied: list[str]
    offer_sink: SeenSink | _SinkCore


def make_surface(
    conn: sqlite3.Connection,
    *,
    offer_sink: SeenSink | _SinkCore | None = None,
) -> Harness[DecksContext]:
    hero = make_card(274, "Jaina", card_class="MAGE", card_type="HERO")
    card = make_card(1000, "Arcane Bolt")
    card_db = make_card_db(hero, card)
    copied: list[str] = []
    current = CurrentDeck()
    actual_offer_sink = offer_sink or SeenSink()
    harness = make_harness(DecksContext(current, copied, actual_offer_sink))
    harness.nav.register(
        "Deck detail", lambda: placeholder_surface("Deck detail")
    )
    harness.nav.register("Import Deck", lambda: placeholder_surface("Import Deck"))
    harness.nav.register("Statistics", lambda: placeholder_surface("Statistics"))
    harness.set_surface(
        build_decks(
            harness.announcer,
            [],
            harness.nav,
            conn,
            DeckData(conn, card_db),
            current,
            actual_offer_sink,
            copied.append,
        )
    )
    return harness


def seed_decks(conn: sqlite3.Connection) -> tuple[str, str, int, int]:
    code_one = make_deckstring([(1000, 1)])
    code_two = make_deckstring([(1000, 2)])
    first_id = save_deck(conn, "First", "Mage", "Standard", code_one)
    second_id = save_deck(conn, "Second", "Mage", "Standard", code_two)
    return code_one, code_two, first_id, second_id


def test_rows_are_decks_then_actions_with_every_detail_line(
    db_conn: sqlite3.Connection,
) -> None:
    _first_code, _second_code, _first_id, second_id = seed_decks(db_conn)
    insert_replay(
        db_conn,
        file_path="second.hsreplay",
        checksum="second",
        source="manual_import",
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="WON",
        turns=8,
        deck_id=second_id,
        played_at="2026-08-15T22:10:00",
    )
    harness = make_surface(db_conn)

    assert harness.horizontal.items_snapshot() == (
        ["Second", "First", "Import deck…", "Statistics…"],
        0,
        ["Mage, Standard", "2 cards", "Last played 2026-08-15"],
    )
    harness.press(Chord("right"))
    assert harness.horizontal.items_snapshot()[2] == [
        "Mage, Standard",
        "1 cards",
        "Never played",
    ]
    harness.press(Chord("right"))
    assert harness.horizontal.items_snapshot()[2] == []


def test_armed_delete_move_disarms_then_repeat_deletes_with_continuing_reentry(
    db_conn: sqlite3.Connection,
) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Aggro Shaman", "Mage", "Standard", code)
    harness = make_surface(db_conn)

    harness.press(Chord("delete"))
    harness.press(Chord("right"))
    harness.press(Chord("left"))
    harness.press(Chord("delete"))
    harness.press(Chord("delete"))

    assert get_all_decks(db_conn) == []
    assert harness.speech.calls == [
        ("Press Delete again to delete Aggro Shaman", True),
        ("Import deck…", True),
        ("Aggro Shaman", True),
        ("Press Delete again to delete Aggro Shaman", True),
        ("Aggro Shaman deleted", True),
        ("Decks, Import deck…, 1 of 2", False),
    ]


def test_shift_delete_is_immediate(db_conn: sqlite3.Connection) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Tempo Mage", "Mage", "Standard", code)
    harness = make_surface(db_conn)

    harness.press(Chord("delete", shift=True))

    assert get_all_decks(db_conn) == []
    assert harness.speech.calls == [
        ("Tempo Mage deleted", True),
        ("Decks, Import deck…, 1 of 2", False),
    ]


def test_copy_confirms_marks_seen_and_own_copy_never_offers(
    db_conn: sqlite3.Connection,
) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Copy Me", "Mage", "Standard", code)
    offer_harness = make_harness(None)
    harness = make_surface(
        db_conn,
        offer_sink=offer_harness.sink,
    )

    harness.press(Chord("c"))

    assert harness.context.copied == [code]
    assert harness.speech.calls == [("Deck code copied", True)]
    assert offer_harness.sink.arm_offer(code, lambda: None) is False


def test_enter_dispatches_for_deck_import_and_statistics_rows(
    db_conn: sqlite3.Connection,
) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Open Me", "Mage", "Standard", code)
    harness = make_surface(db_conn)
    harness.press(Chord("enter"))
    assert harness.context.current.get().name == "Open Me"
    assert harness.nav.stack == ("Home", "Deck detail")

    empty_conn = sqlite3.connect(":memory:")
    empty_conn.row_factory = sqlite3.Row
    from stonereader.db import init_db

    init_db(empty_conn)
    try:
        harness = make_surface(empty_conn)
        harness.press(Chord("enter"))
        assert harness.nav.stack == ("Home", "Import Deck")

        harness = make_surface(empty_conn)
        harness.press(Chord("right"))
        harness.press(Chord("enter"))
        assert harness.nav.stack == ("Home", "Statistics")
    finally:
        empty_conn.close()


def test_action_rows_get_exact_delete_and_copy_noops(
    db_conn: sqlite3.Connection,
) -> None:
    harness = make_surface(db_conn)
    for chord in (Chord("delete"), Chord("delete", shift=True), Chord("c")):
        harness.press(chord)
    assert harness.speech.calls == [
        ("Nothing to delete here", True),
        ("Nothing to delete here", True),
        ("Nothing to copy here", True),
    ]
