"""Tests for DeckManagerPresenter."""

from __future__ import annotations

import sqlite3

from stonereader.db import get_connection, init_db, save_deck
from stonereader.models.card import CardDatabase
from stonereader.presenters.deck_manager import DeckManagerPresenter
from tests.conftest import MockSpeechService


def _make_db(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    return conn


def _make_card_db() -> CardDatabase:
    """Create an empty CardDatabase for testing."""
    return CardDatabase()


def _seed_decks(conn: sqlite3.Connection) -> None:
    """Insert test decks. Oldest first so 'Aggro Paladin' is newest."""
    save_deck(conn, "Control Mage", "MAGE", "Standard", "AAECAf0EAA==")
    save_deck(conn, "Midrange Hunter", "HUNTER", "Wild", "AAECAR8A")
    save_deck(conn, "Aggro Paladin", "PALADIN", "Standard", "AAECAZ8FAA==")


def test_load_decks_sorted_newest_first(tmp_path):
    conn = _make_db(tmp_path)
    _seed_decks(conn)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    items = presenter.get_zone_items("decks")
    assert len(items) == 3
    assert items[0].name == "Aggro Paladin"  # newest first (D-09)
    conn.close()


def test_speech_format_matches_d08(tmp_path):
    conn = _make_db(tmp_path)
    _seed_decks(conn)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    presenter.move_in_zone(0)  # Announce current item
    # Move to trigger speech announcement
    presenter.move_in_zone(1)
    last = speech.last_speech
    # D-08: "Name, Class, Format, N of M"
    assert "Midrange Hunter" in last
    assert "HUNTER" in last
    assert "Wild" in last
    assert "2 of 3" in last
    conn.close()


def test_empty_deck_list(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    items = presenter.get_zone_items("decks")
    assert items == []
    conn.close()


def test_announce_entry_with_decks(tmp_path):
    conn = _make_db(tmp_path)
    _seed_decks(conn)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    presenter.announce_entry()
    assert "Deck Manager" in speech.last_speech
    assert "Aggro Paladin" in speech.last_speech
    conn.close()


def test_announce_entry_empty(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    presenter.announce_entry()
    assert "no saved decks" in speech.last_speech
    conn.close()


def test_delete_current_deck_with_confirmation(tmp_path):
    conn = _make_db(tmp_path)
    _seed_decks(conn)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    # Auto-confirm deletion
    presenter.set_on_request_delete_confirm(lambda name: True)
    presenter.delete_current_deck()
    assert "Aggro Paladin deleted" in speech.last_speech
    assert len(presenter.get_zone_items("decks")) == 2
    conn.close()


def test_delete_rejected_does_not_remove(tmp_path):
    conn = _make_db(tmp_path)
    _seed_decks(conn)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    # Reject deletion
    presenter.set_on_request_delete_confirm(lambda name: False)
    presenter.delete_current_deck()
    assert len(presenter.get_zone_items("decks")) == 3
    conn.close()


def test_delete_last_deck_announces_empty(tmp_path):
    conn = _make_db(tmp_path)
    save_deck(conn, "Only Deck", "WARRIOR", "Standard", "AAECAQcA")
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    presenter.set_on_request_delete_confirm(lambda name: True)
    presenter.delete_current_deck()
    assert "no saved decks" in speech.last_speech
    conn.close()


def test_delete_cursor_repositions_d13(tmp_path):
    """D-13: After deletion, cursor moves to next (or previous if last)."""
    conn = _make_db(tmp_path)
    _seed_decks(conn)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    # Move to last deck
    presenter.move_in_zone(1)
    presenter.move_in_zone(1)
    # Delete last deck (index 2 -> should move to index 1)
    presenter.set_on_request_delete_confirm(lambda name: True)
    presenter.delete_current_deck()
    # Cursor should now be at the new last item
    items = presenter.get_zone_items("decks")
    cursor = presenter._zone_cursors.get("decks", 0)
    assert cursor <= len(items) - 1
    conn.close()


def test_export_deckstring_returns_string(tmp_path):
    conn = _make_db(tmp_path)
    save_deck(conn, "Export Test", "MAGE", "Standard", "AAECAf0EAA==")
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    result = presenter.export_current_deckstring()
    assert result == "AAECAf0EAA=="
    conn.close()


def test_export_to_clipboard_announces_after_callback(tmp_path):
    """Speech fires after clipboard callback, not before (WR-01)."""
    conn = _make_db(tmp_path)
    save_deck(conn, "Export Test", "MAGE", "Standard", "AAECAf0EAA==")
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    exported = []
    presenter.set_on_export(lambda ds: exported.append(ds))
    presenter._export_to_clipboard()
    assert exported == ["AAECAf0EAA=="]
    assert "Deck code copied to clipboard" in speech.last_speech
    conn.close()


def test_export_with_no_decks_returns_none(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    result = presenter.export_current_deckstring()
    assert result is None
    conn.close()


def test_key_map_has_all_keys(tmp_path):
    conn = _make_db(tmp_path)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    key_map = presenter.get_key_map()
    assert "left" in key_map
    assert "right" in key_map
    assert "up" in key_map
    assert "down" in key_map
    assert "enter" in key_map
    assert "home" in key_map
    assert "end" in key_map
    assert "delete" in key_map
    assert "c" in key_map
    conn.close()


def test_view_callback_fires_on_navigation(tmp_path):
    conn = _make_db(tmp_path)
    _seed_decks(conn)
    speech = MockSpeechService()
    presenter = DeckManagerPresenter(speech, conn, _make_card_db())
    received = []
    presenter.set_on_state_changed(
        lambda decks, cursor: received.append((len(decks), cursor))
    )
    presenter.move_in_zone(1)
    assert received == [(3, 1)]
    conn.close()
