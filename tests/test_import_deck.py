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


def test_missing_cards_imports_with_placeholders(tmp_path):
    """With allow_unknown=True (now the default in validate_and_import), a deckstring
    referencing unknown cards still imports successfully and records placeholders."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    # Empty card DB so every card is unknown.
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    # Deckstring with cards that resolve to non-empty but unknown DBF IDs.
    result = presenter.validate_and_import(
        "AAECAf0GAA/pBu0GkAeODsIPwxaFF+CsAsmrA/2wA5GxA5O6A8O8A/fRA4fhAwA=",
        "Unknown Cards Deck",
    )
    assert result is True
    assert "Unknown Cards Deck imported" in speech.last_speech
    assert "unknown card" in speech.last_speech
    decks = get_all_decks(conn)
    assert len(decks) == 1
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


def test_known_cards_only_omits_unknown_suffix(tmp_path):
    """With all cards resolved, success announcement has no unknown-card suffix."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    card_db = CardDatabase()
    hero = _make_card(name="Malfurion", card_class="DRUID", dbf_id=274)
    card_db.cards_by_dbf_id[274] = hero
    card_db.cards_by_id[hero.id] = hero
    presenter = ImportDeckPresenter(speech, conn, card_db)
    result = presenter.validate_and_import("AAECAZICAAAAAA==", "Empty Druid")
    assert result is True
    assert speech.last_speech == "Empty Druid imported"
    conn.close()


def test_singular_unknown_card_uses_singular_form(tmp_path):
    """One unknown card => 'imported, 1 unknown card' (no trailing s)."""
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    deckstring = write_deckstring(
        cards=[(99999, 1)],
        heroes=[274],
        format=FormatType.FT_STANDARD,
    )

    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    card_db = CardDatabase()
    hero = _make_card(name="Malfurion", card_class="DRUID", dbf_id=274)
    card_db.cards_by_dbf_id[274] = hero
    card_db.cards_by_id[hero.id] = hero
    presenter = ImportDeckPresenter(speech, conn, card_db)
    presenter.validate_and_import(deckstring, "One Unknown")
    assert speech.last_speech == "One Unknown imported, 1 unknown card"
    conn.close()


def test_format_missing_cards_message_includes_dbf_ids(tmp_path):
    """The diagnostic helper lists the actual DBF IDs in the error message."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    msg = presenter._format_missing_cards_message((99999, 88888, 77777))
    assert "99999" in msg
    assert "88888" in msg
    assert "77777" in msg
    assert "DBF IDs" in msg
    conn.close()


def test_format_missing_cards_message_empty_falls_back(tmp_path):
    """Empty tuple => generic message (no parenthesized empty list)."""
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = ImportDeckPresenter(speech, conn, CardDatabase())
    msg = presenter._format_missing_cards_message(())
    assert "DBF" not in msg or "(" not in msg
    assert "newer expansion" in msg
    conn.close()
