from __future__ import annotations

import sqlite3

from stonereader.db import get_all_decks, save_deck
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.import_deck import ImportDeckField, build_import_deck
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface, NavigationController

from tests.test_ui.conftest import FakeSpeech

from .conftest import make_card, make_card_db, make_deckstring


def type_text(sink: _SinkCore, text: str) -> None:
    for character in text:
        sink.handle_chord(
            Chord(character.lower(), shift=character.isalpha() and character.isupper())
        )


def make_navigation(
    conn: sqlite3.Connection,
) -> tuple[
    NavigationController,
    _SinkCore,
    FakeSpeech,
    ImportDeckField,
    str,
]:
    hero = make_card(274, "Malfurion", card_class="DRUID", card_type="HERO")
    card_db = make_card_db(hero)
    code = make_deckstring([])
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    field = ImportDeckField()
    navigation = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    data = DeckData(conn, card_db)
    current = CurrentDeck()
    navigation.register(
        "Decks",
        lambda: build_decks(
            announcer,
            [],
            navigation,
            conn,
            data,
            current,
            sink,
            lambda _text: None,
        ),
    )
    navigation.register(
        "Import Deck",
        lambda: build_import_deck(
            announcer,
            [],
            navigation,
            conn,
            card_db,
            sink,
            field,
        ),
    )
    return navigation, sink, speech, field, code


def enter_import_from_empty_decks(
    navigation: NavigationController,
    sink: _SinkCore,
) -> ActiveSurface:
    navigation.jump("Decks")
    sink.handle_chord(Chord("enter"))
    return navigation._surfaces["Import Deck"]


def test_text_mode_commit_abandon_and_successful_import_queues_back_entry(
    db_conn: sqlite3.Connection,
) -> None:
    navigation, sink, speech, field, code = make_navigation(db_conn)
    surface = enter_import_from_empty_decks(navigation, sink)
    assert surface.engine.options_snapshot() == (
        ["Deck code, edit text", "Import"],
        0,
    )

    sink.handle_chord(Chord("enter"))
    assert sink.text_mode_active is True
    type_text(sink, code)
    sink.handle_chord(Chord("enter"))
    assert sink.text_mode_active is False
    assert field.value == code
    assert speech.calls[-1] == ("Import Deck, Deck code, edit text", True)

    sink.handle_chord(Chord("enter"))
    type_text(sink, "x")
    sink.handle_chord(Chord("escape"))
    assert field.value == code
    assert speech.calls[-1] == ("Import Deck, Deck code, edit text", True)

    sink.handle_chord(Chord("down"))
    sink.handle_chord(Chord("enter"))

    assert [deck.name for deck in get_all_decks(db_conn)] == ["Druid deck"]
    assert navigation.stack == ("Home", "Decks")
    assert speech.calls[-2:] == [
        ("Druid deck imported", True),
        ("Decks, Druid deck, 1 of 3", False),
    ]


def test_failure_keeps_field_contents(db_conn: sqlite3.Connection) -> None:
    navigation, sink, speech, field, _code = make_navigation(db_conn)
    enter_import_from_empty_decks(navigation, sink)
    field.set("not-a-deck-code")

    sink.handle_chord(Chord("down"))
    sink.handle_chord(Chord("enter"))

    assert field.value == "not-a-deck-code"
    assert get_all_decks(db_conn) == []
    assert speech.calls[-1] == ("Deck code not recognized", True)


def test_derived_name_uses_next_available_suffix(db_conn: sqlite3.Connection) -> None:
    navigation, sink, _speech, field, code = make_navigation(db_conn)
    save_deck(db_conn, "Druid deck", "DRUID", "Standard", code)
    save_deck(db_conn, "Druid deck 2", "DRUID", "Standard", code)
    navigation.jump_path(["Home", "Decks", "Import Deck"])
    field.set(code)

    sink.handle_chord(Chord("down"))
    sink.handle_chord(Chord("enter"))

    assert get_all_decks(db_conn)[0].name == "Druid deck 3"


def test_offer_accept_sets_field_and_resets_exact_stack(
    db_conn: sqlite3.Connection,
) -> None:
    navigation, sink, speech, field, code = make_navigation(db_conn)
    navigation.jump("Decks")
    navigation.drill_down("Import Deck")
    navigation.back()
    assert navigation.stack == ("Home", "Decks")

    def accept() -> None:
        field.set(code)
        navigation.jump_path(["Home", "Decks", "Import Deck"])

    assert sink.arm_offer(code, accept) is True
    Announcer(speech).offer(
        "Deck code on clipboard — press Control Enter to import"
    )
    sink.handle_chord(Chord("enter", ctrl=True))

    assert field.value == code
    assert navigation.stack == ("Home", "Decks", "Import Deck")
    assert speech.calls[-2:] == [
        ("Deck code on clipboard — press Control Enter to import", True),
        ("Import Deck, Deck code, edit text", True),
    ]
