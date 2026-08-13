import sqlite3

import pytest

from stonereader.db import (
    _SCHEMA_V1,
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
    assert "games" in tables
    assert "schema_version" in tables
    conn.close()


def test_schema_version_is_two(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    assert get_schema_version(conn) == 2
    conn.close()


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    init_db(conn)  # second call should not raise or duplicate
    assert get_schema_version(conn) == 2
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


def test_games_table_schema(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    conn.execute(
        """INSERT INTO games
        (deck_name, hero_class, opponent_class, result, turns, duration_seconds, played_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        ("Test Deck", "MAGE", "WARRIOR", "WIN", 10, 300),
    )
    row = conn.execute("SELECT * FROM games").fetchone()
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
    conn.executescript(_SCHEMA_V1)
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (1,))
    conn.commit()


def test_fresh_db_is_version_two(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    assert get_schema_version(conn) == 2
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


def test_v1_to_v2_migration_preserves_data(tmp_path):
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

    assert get_schema_version(conn) == 2
    decks = get_all_decks(conn)
    assert len(decks) == 1
    assert decks[0].name == "Legacy Deck"
    assert decks[0].deck_id == deck_id
    games = conn.execute("SELECT * FROM games").fetchall()
    assert len(games) == 1
    assert games[0]["deck_name"] == "Legacy Deck"
    # replays table now exists and is usable
    _insert_replay(conn, "post-migration")
    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 1
    conn.close()


def test_init_db_idempotent_at_v2(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    init_db(conn)
    init_db(conn)
    assert get_schema_version(conn) == 2
    conn.close()


def test_replay_constants():
    assert REPLAY_SOURCES == ("live_auto", "manual_import")
    assert REPLAY_RESULTS == ("WON", "LOST", "TIED", "UNKNOWN")
