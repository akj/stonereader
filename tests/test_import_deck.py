"""Tests for ImportDeckPresenter."""

from __future__ import annotations

import sqlite3

from stonereader.db import get_connection, init_db, get_all_decks
from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.import_deck import ImportDeckPresenter
from tests.conftest import MockSpeechService

_next_dbf_id = 8000


def _make_card(
    name: str = "Test Card",
    cost: int = 1,
    card_class: str = "NEUTRAL",
    dbf_id: int | None = None,
) -> Card:
    global _next_dbf_id
    if dbf_id is None:
        _next_dbf_id += 1
        dbf_id = _next_dbf_id
    return Card(
        id=f"TEST_{name.upper().replace(' ', '_')}",
        dbf_id=dbf_id,
        name=name,
        cost=cost,
        attack=None,
        health=None,
        text="",
        rarity="COMMON",
        card_class=card_class,
        card_type="MINION",
        card_set="CORE",
        collectible=True,
    )


def _make_db(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    return conn


def _make_card_db_with_cards(cards: list[Card]) -> CardDatabase:
    db = CardDatabase()
    for card in cards:
        db.cards_by_id[card.id] = card
        db.cards_by_dbf_id[card.dbf_id] = card
    return db


def test_empty_deckstring_shows_error(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    errors: list[str] = []
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    presenter.set_on_show_error(lambda msg, title: errors.append(msg))
    result = presenter.validate_and_import("", "My Deck")
    assert result is False
    assert "Enter a deck code to import" in errors[0]
    conn.close()


def test_empty_name_shows_error(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    errors: list[str] = []
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    presenter.set_on_show_error(lambda msg, title: errors.append(msg))
    result = presenter.validate_and_import("AAECAf0EAA==", "")
    assert result is False
    assert "Enter a name for this deck" in errors[0]
    conn.close()


def test_whitespace_only_deckstring_shows_error(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    errors: list[str] = []
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    presenter.set_on_show_error(lambda msg, title: errors.append(msg))
    result = presenter.validate_and_import("   ", "My Deck")
    assert result is False
    assert "Enter a deck code to import" in errors[0]
    conn.close()


def test_invalid_deckstring_shows_error(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    errors: list[str] = []
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    presenter.set_on_show_error(lambda msg, title: errors.append(msg))
    result = presenter.validate_and_import("not-a-deckstring", "My Deck")
    assert result is False
    assert "Invalid deck code" in errors[0]
    conn.close()


def test_missing_cards_shows_error(tmp_path):
    """Deckstring references cards not in the card database -> ValueError."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    errors: list[str] = []
    # Empty card database -- all card DBF IDs will be "missing"
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    presenter.set_on_show_error(lambda msg, title: errors.append(msg))
    # This is a real deckstring format but the card DB is empty
    # parse_deckstring will succeed but from_deckstring will raise ValueError
    # because all card DBF IDs are unknown
    result = presenter.validate_and_import(
        "AAECAf0GAA/pBu0GkAeODsIPwxaFF+CsAsmrA/2wA5GxA5O6A8O8A/fRA4fhAwA=",
        "Missing Cards Deck",
    )
    assert result is False
    # Should get either "not found" or "Invalid" error
    assert len(errors) > 0
    conn.close()


def test_successful_import_saves_to_db(tmp_path):
    """A valid deckstring with known cards saves successfully."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    # Create a card DB that matches the deckstring cards
    # AAECAZICAAAAAA== is a valid Druid deck with 0 cards, hero DBF ID 274
    card_db = CardDatabase()
    hero = _make_card(name="Malfurion", card_class="DRUID", dbf_id=274)
    card_db.cards_by_dbf_id[274] = hero
    card_db.cards_by_id[hero.id] = hero

    presenter = ImportDeckPresenter(speech, conn, card_db)
    result = presenter.validate_and_import("AAECAZICAAAAAA==", "Empty Druid")
    assert result is True
    assert "Empty Druid imported" in speech.last_speech

    decks = get_all_decks(conn)
    assert len(decks) == 1
    assert decks[0].name == "Empty Druid"
    conn.close()


def test_import_success_fires_callback(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    card_db = CardDatabase()
    # AAECAZICAAAAAA== is a valid Druid deck with hero DBF ID 274
    hero = _make_card(name="Malfurion", card_class="DRUID", dbf_id=274)
    card_db.cards_by_dbf_id[274] = hero
    card_db.cards_by_id[hero.id] = hero

    callbacks: list[str] = []
    presenter = ImportDeckPresenter(speech, conn, card_db)
    presenter.set_on_import_success(lambda: callbacks.append("success"))
    presenter.validate_and_import("AAECAZICAAAAAA==", "Callback Test")
    assert callbacks == ["success"]
    conn.close()


def test_key_map_is_empty(tmp_path):
    """Import screen uses Tab navigation, no hotkey map."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    assert presenter.get_key_map() == {}
    conn.close()


def test_error_fallback_to_speech_when_no_callback(tmp_path):
    """Without on_show_error callback, errors fall back to speech."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    # No on_show_error set
    presenter.validate_and_import("", "My Deck")
    assert "Enter a deck code to import" in speech.last_speech
    conn.close()
