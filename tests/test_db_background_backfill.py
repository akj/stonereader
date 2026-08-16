import threading
from types import SimpleNamespace

from stonereader.db import (
    _SCHEMA_V1_LEGACY,
    _SCHEMA_V2,
    _wait_for_replay_deck_backfills,
    get_connection,
    get_schema_version,
    init_db,
    save_deck,
)
from stonereader.models.card import CardDatabase
from stonereader.services import _deck_detect, _replay_loader


def test_legacy_backfill_runs_after_schema_migration_returns(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    conn.executescript(_SCHEMA_V1_LEGACY)
    conn.executescript(_SCHEMA_V2)
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (2)")
    deck_id = save_deck(conn, "Legacy Deck", "MAGE", "Standard", "deck-code")
    conn.execute(
        """INSERT INTO replays
        (file_path, checksum, source, friendly_class, opponent_class,
         result, turns, played_at)
        VALUES ('legacy.hsreplay', 'legacy', 'live_auto', 'MAGE', 'WARRIOR',
                'WON', 8, '2026-08-16T09:30:00')"""
    )
    conn.commit()

    entered = threading.Event()
    release = threading.Event()

    def load_card_database(cls):
        entered.set()
        assert release.wait(timeout=2)
        return object()

    monkeypatch.setattr(CardDatabase, "load", classmethod(load_card_database))
    monkeypatch.setattr(
        _replay_loader,
        "load_replay",
        lambda path, card_db: SimpleNamespace(states=(object(),)),
    )
    monkeypatch.setattr(
        _deck_detect,
        "detect_deck",
        lambda state, decks, card_db: (deck_id, "Legacy Deck"),
    )

    init_db(conn)

    assert entered.wait(timeout=2)
    assert get_schema_version(conn) == 3
    assert (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='games'"
        ).fetchone()
        is None
    )
    assert (
        conn.execute(
            "SELECT deck_id FROM replays WHERE checksum = 'legacy'"
        ).fetchone()[0]
        is None
    )

    conn.execute("UPDATE replays SET result = 'LOST' WHERE checksum = 'legacy'")
    conn.commit()
    release.set()

    assert _wait_for_replay_deck_backfills(timeout=2)
    row = conn.execute(
        "SELECT deck_id, deck_name, result FROM replays WHERE checksum = 'legacy'"
    ).fetchone()
    assert tuple(row) == (deck_id, "Legacy Deck", "LOST")
    conn.close()


def test_init_db_resumes_interrupted_backfill_at_current_schema(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    deck_id = save_deck(conn, "Legacy Deck", "MAGE", "Standard", "deck-code")
    conn.execute(
        """INSERT INTO replays
        (file_path, checksum, source, friendly_class, opponent_class,
         result, turns, played_at)
        VALUES ('legacy.hsreplay', 'legacy', 'live_auto', 'MAGE', 'WARRIOR',
                'WON', 8, '2026-08-16T09:30:00')"""
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(CardDatabase, "load", classmethod(lambda cls: object()))
    monkeypatch.setattr(
        _replay_loader,
        "load_replay",
        lambda path, card_db: SimpleNamespace(states=(object(),)),
    )
    monkeypatch.setattr(
        _deck_detect,
        "detect_deck",
        lambda state, decks, card_db: (deck_id, "Legacy Deck"),
    )

    conn = get_connection(str(db_path))
    assert get_schema_version(conn) == 3
    init_db(conn)

    assert _wait_for_replay_deck_backfills(timeout=2)
    row = conn.execute(
        "SELECT deck_id, deck_name FROM replays WHERE checksum = 'legacy'"
    ).fetchone()
    assert tuple(row) == (deck_id, "Legacy Deck")
    conn.close()
