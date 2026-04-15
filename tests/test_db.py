from stonereader.db import get_connection, init_db, get_schema_version, save_deck, get_all_decks, delete_deck


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
