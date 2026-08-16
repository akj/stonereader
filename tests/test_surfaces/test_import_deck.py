from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from stonereader.db import get_all_decks, save_deck
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.import_deck import ImportDeckField, build_import_deck
from stonereader.ui.chords import Chord

from .conftest import Harness, make_card, make_card_db, make_deckstring, make_harness


@dataclass
class ImportDeckContext:
    field: ImportDeckField
    code: str


def make_navigation(
    conn: sqlite3.Connection,
) -> Harness[ImportDeckContext]:
    hero = make_card(274, "Malfurion", card_class="DRUID", card_type="HERO")
    card_db = make_card_db(hero)
    code = make_deckstring([])
    field = ImportDeckField()
    harness = make_harness(ImportDeckContext(field, code))
    data = DeckData(conn, card_db)
    current = CurrentDeck()
    harness.nav.register(
        "Decks",
        lambda: build_decks(
            harness.announcer,
            [],
            harness.nav,
            conn,
            data,
            current,
            harness.sink,
            lambda _text: None,
        ),
    )
    harness.nav.register(
        "Import Deck",
        lambda: build_import_deck(
            harness.announcer,
            [],
            harness.nav,
            conn,
            card_db,
            harness.sink,
            field,
        ),
    )
    return harness


def enter_import_from_empty_decks(harness: Harness[ImportDeckContext]) -> None:
    harness.nav.jump("Decks")
    harness.press(Chord("enter"))


def test_text_mode_commit_abandon_and_successful_import_queues_back_entry(
    db_conn: sqlite3.Connection,
) -> None:
    harness = make_navigation(db_conn)
    enter_import_from_empty_decks(harness)
    assert harness.vertical.options_snapshot() == (
        ["Deck code, edit text", "Import"],
        0,
    )

    harness.press(Chord("enter"))
    assert harness.sink.text_mode_active is True
    harness.type(harness.context.code)
    harness.press(Chord("enter"))
    assert harness.sink.text_mode_active is False
    assert harness.context.field.value == harness.context.code
    assert harness.speech.calls[-1] == ("Import Deck, Deck code, edit text", True)

    harness.press(Chord("enter"))
    harness.type("x")
    harness.press(Chord("escape"))
    assert harness.context.field.value == harness.context.code
    assert harness.speech.calls[-1] == ("Import Deck, Deck code, edit text", True)

    harness.press(Chord("down"))
    harness.press(Chord("enter"))

    assert [deck.name for deck in get_all_decks(db_conn)] == ["Druid deck"]
    assert harness.nav.stack == ("Home", "Decks")
    assert harness.speech.calls[-2:] == [
        ("Druid deck imported", True),
        ("Decks, Druid deck, 1 of 3", False),
    ]


def test_failure_keeps_field_contents(db_conn: sqlite3.Connection) -> None:
    harness = make_navigation(db_conn)
    enter_import_from_empty_decks(harness)
    harness.context.field.set("not-a-deck-code")

    harness.press(Chord("down"))
    harness.press(Chord("enter"))

    assert harness.context.field.value == "not-a-deck-code"
    assert get_all_decks(db_conn) == []
    assert harness.speech.calls[-1] == ("Deck code not recognized", True)


def test_derived_name_uses_next_available_suffix(db_conn: sqlite3.Connection) -> None:
    harness = make_navigation(db_conn)
    save_deck(db_conn, "Druid deck", "DRUID", "Standard", harness.context.code)
    save_deck(db_conn, "Druid deck 2", "DRUID", "Standard", harness.context.code)
    harness.nav.jump_path(["Home", "Decks", "Import Deck"])
    harness.context.field.set(harness.context.code)

    harness.press(Chord("down"))
    harness.press(Chord("enter"))

    assert get_all_decks(db_conn)[0].name == "Druid deck 3"


def test_offer_accept_sets_field_and_resets_exact_stack(
    db_conn: sqlite3.Connection,
) -> None:
    harness = make_navigation(db_conn)
    harness.nav.jump("Decks")
    harness.nav.drill_down("Import Deck")
    harness.nav.back()
    assert harness.nav.stack == ("Home", "Decks")

    def accept() -> None:
        harness.context.field.set(harness.context.code)
        harness.nav.jump_path(["Home", "Decks", "Import Deck"])

    assert harness.sink.arm_offer(harness.context.code, accept) is True
    harness.announcer.clipboard_deck_offer()
    harness.press(Chord("enter", ctrl=True))

    assert harness.context.field.value == harness.context.code
    assert harness.nav.stack == ("Home", "Decks", "Import Deck")
    assert harness.speech.calls[-2:] == [
        ("Deck code on clipboard — press Control Enter to import", True),
        ("Import Deck, Deck code, edit text", True),
    ]
