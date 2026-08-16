import sqlite3
from types import SimpleNamespace

import pytest

from stonereader.db import (
    _SCHEMA_V1_LEGACY,
    REPLAY_RESULTS,
    REPLAY_SOURCES,
    delete_deck,
    get_all_decks,
    get_connection,
    get_schema_version,
    init_db,
    save_deck,
)


def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "decks" in tables
    assert "games" not in tables
    assert "replays" in tables
    assert "schema_version" in tables
    conn.close()


def test_schema_version_is_three(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    assert get_schema_version(conn) == 3
    conn.close()


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    init_db(conn)  # second call should not raise or duplicate
    assert get_schema_version(conn) == 3
    conn.close()


def test_decks_table_schema(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    conn.execute(
        "INSERT INTO decks (name, hero_class, format, deckstring) VALUES (?, ?, ?, ?)",
        ("Test Deck", "MAGE", "Standard", "AAECAf0EAA=="),
    )
    row = conn.execute("SELECT * FROM decks").fetchone()
    assert row is not None
    conn.close()


def test_save_deck_returns_id(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    deck_id = save_deck(conn, "Test Deck", "MAGE", "Standard", "AAECAf0EAA==")
    assert isinstance(deck_id, int)
    assert deck_id > 0
    conn.close()


def test_get_all_decks_returns_summaries(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    save_deck(conn, "Deck A", "MAGE", "Standard", "AAECAf0EAA==")
    save_deck(conn, "Deck B", "PALADIN", "Wild", "AAECAZ8FAA==")
    decks = get_all_decks(conn)
    assert len(decks) == 2
    assert decks[0].name == "Deck B"  # newest first (D-09)
    assert decks[1].name == "Deck A"
    assert decks[0].hero_class == "PALADIN"
    assert decks[0].format == "Wild"
    conn.close()


def test_get_all_decks_empty(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    decks = get_all_decks(conn)
    assert decks == []
    conn.close()


def test_delete_deck_removes_row(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    deck_id = save_deck(conn, "Doomed Deck", "WARRIOR", "Standard", "AAECAQcA")
    delete_deck(conn, deck_id)
    decks = get_all_decks(conn)
    assert len(decks) == 0
    conn.close()


def test_deck_summary_has_created_at(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    save_deck(conn, "Timestamped", "ROGUE", "Standard", "AAECAaIHAA==")
    decks = get_all_decks(conn)
    assert decks[0].created_at is not None
    assert len(decks[0].created_at) > 0
    conn.close()


# --- Slice #9: Replay schema v2 ---


def _init_v1_only(conn):
    """Build a v1 database without running the v2 migration."""
    conn.executescript(_SCHEMA_V1_LEGACY)
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (1,))
    conn.commit()


def test_fresh_db_is_version_three(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    assert get_schema_version(conn) == 3
    conn.close()


def test_replays_table_created(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "replays" in tables
    conn.close()


def test_replays_table_columns(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(replays)")}
    expected = {
        "id",
        "file_path",
        "checksum",
        "source",
        "friendly_class",
        "opponent_class",
        "result",
        "turns",
        "game_type",
        "format_type",
        "deck_name",
        "deck_id",
        "played_at",
        "duration_seconds",
        "imported_at",
        "in_stats",
    }
    assert cols == expected
    conn.close()


def _insert_replay(conn, checksum):
    conn.execute(
        """INSERT INTO replays
        (file_path, checksum, source, friendly_class, opponent_class,
         result, turns, played_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            "/replays/game.hsreplay",
            checksum,
            "live_auto",
            "MAGE",
            "WARRIOR",
            "WON",
            10,
        ),
    )
    conn.commit()


def test_replays_checksum_unique(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    _insert_replay(conn, "abc123")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_replay(conn, "abc123")
    conn.close()


def test_v1_to_v3_migration_preserves_decks_and_drops_games(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    _init_v1_only(conn)
    assert get_schema_version(conn) == 1

    deck_id = save_deck(conn, "Legacy Deck", "MAGE", "Standard", "AAECAf0EAA==")
    conn.execute(
        """INSERT INTO games
        (deck_name, hero_class, opponent_class, result, turns, duration_seconds, played_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        ("Legacy Deck", "MAGE", "WARRIOR", "WIN", 10, 300),
    )
    conn.commit()

    init_db(conn)

    assert get_schema_version(conn) == 3
    decks = get_all_decks(conn)
    assert len(decks) == 1
    assert decks[0].name == "Legacy Deck"
    assert decks[0].deck_id == deck_id
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "games" not in tables
    # replays table now exists and is usable
    _insert_replay(conn, "post-migration")
    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 1
    conn.close()


def test_init_db_idempotent_at_v3(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    init_db(conn)
    init_db(conn)
    assert get_schema_version(conn) == 3
    conn.close()


def test_v2_to_v3_migration_backfills_in_stats_by_source_and_drops_games(tmp_path):
    from stonereader.db import _SCHEMA_V2

    conn = get_connection(str(tmp_path / "test.db"))
    _init_v1_only(conn)
    conn.executescript(_SCHEMA_V2)
    conn.execute("UPDATE schema_version SET version = 2")
    for checksum, source in (("live", "live_auto"), ("imported", "manual_import")):
        conn.execute(
            """INSERT INTO replays
            (file_path, checksum, source, friendly_class, opponent_class,
             result, turns, played_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"{checksum}.hsreplay",
                checksum,
                source,
                "MAGE",
                "WARRIOR",
                "WON",
                10,
                "2026-08-16T09:30:00",
            ),
        )
    conn.commit()

    init_db(conn)

    rows = conn.execute(
        "SELECT checksum, in_stats FROM replays ORDER BY checksum"
    ).fetchall()
    assert [(row["checksum"], row["in_stats"]) for row in rows] == [
        ("imported", 0),
        ("live", 1),
    ]
    assert get_schema_version(conn) == 3
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='games'"
    ).fetchone() is None
    conn.close()


def test_v2_migration_backfills_unique_deck_and_isolates_corrupt_replay(
    tmp_path, monkeypatch, caplog
):
    from stonereader.db import _SCHEMA_V2
    from stonereader.models.card import CardDatabase
    from stonereader.services import _deck_detect, _replay_loader

    conn = get_connection(str(tmp_path / "test.db"))
    _init_v1_only(conn)
    conn.executescript(_SCHEMA_V2)
    conn.execute("UPDATE schema_version SET version = 2")
    deck_id = save_deck(conn, "Legacy Deck", "MAGE", "Standard", "deck-code")
    for checksum in ("good", "corrupt"):
        conn.execute(
            """INSERT INTO replays
            (file_path, checksum, source, friendly_class, opponent_class,
             result, turns, played_at)
            VALUES (?, ?, 'live_auto', 'MAGE', 'WARRIOR', 'WON', 8, ?)""",
            (f"{checksum}.hsreplay", checksum, "2026-08-16T09:30:00"),
        )
    conn.commit()

    monkeypatch.setattr(CardDatabase, "load", classmethod(lambda cls: object()))

    def load(path, card_db):
        if path.name == "corrupt.hsreplay":
            raise _replay_loader.ReplayLoadError("corrupt")
        return SimpleNamespace(states=(object(),))

    monkeypatch.setattr(_replay_loader, "load_replay", load)
    monkeypatch.setattr(
        _deck_detect,
        "detect_deck",
        lambda state, decks, card_db: (deck_id, "Legacy Deck"),
    )

    with caplog.at_level("INFO"):
        init_db(conn)

    rows = conn.execute(
        "SELECT checksum, deck_id, deck_name FROM replays ORDER BY checksum"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("corrupt", None, None),
        ("good", deck_id, "Legacy Deck"),
    ]
    assert "replay deck backfill: attributed 1 / skipped 1" in caplog.text
    assert get_schema_version(conn) == 3
    conn.close()


def test_replay_constants():
    assert REPLAY_SOURCES == ("live_auto", "manual_import")
    assert REPLAY_RESULTS == ("WON", "LOST", "TIED", "UNKNOWN")
