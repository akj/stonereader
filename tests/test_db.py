import sqlite3

from stonereader.db import get_connection, init_db, get_schema_version


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


def test_schema_version_starts_at_one(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    assert get_schema_version(conn) == 1
    conn.close()


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    init_db(conn)  # second call should not raise or duplicate
    assert get_schema_version(conn) == 1
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
