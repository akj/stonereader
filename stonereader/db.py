"""SQLite database for persisting decks and game history."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from stonereader.models.deck import DeckSummary

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    hero_class TEXT NOT NULL,
    format TEXT NOT NULL,
    deckstring TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_name TEXT NOT NULL,
    hero_class TEXT NOT NULL,
    opponent_class TEXT NOT NULL,
    result TEXT NOT NULL,
    turns INTEGER NOT NULL,
    duration_seconds INTEGER,
    played_at TIMESTAMP NOT NULL
);
"""

# Replay metadata (v2). Replay CONTENT lives in .hsreplay files, not the DB.
_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS replays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    checksum TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    friendly_class TEXT NOT NULL,
    opponent_class TEXT NOT NULL,
    result TEXT NOT NULL,
    turns INTEGER NOT NULL,
    game_type TEXT NOT NULL DEFAULT '',
    format_type TEXT NOT NULL DEFAULT '',
    deck_name TEXT,
    deck_id INTEGER,
    played_at TIMESTAMP NOT NULL,
    duration_seconds INTEGER,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

REPLAY_SOURCES = ("live_auto", "manual_import")
REPLAY_RESULTS = ("WON", "LOST", "TIED", "UNKNOWN")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection. Defaults to ~/.stonereader/stonereader.db."""
    if db_path is None:
        data_dir = Path.home() / ".stonereader"
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / "stonereader.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if not initialized."""
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def init_db(conn: sqlite3.Connection) -> None:
    """Create/migrate tables to the latest schema version. Idempotent.

    Migrates v1 -> v2 in place without dropping existing decks/games data.
    """
    version = get_schema_version(conn)
    if version >= 2:
        return
    if version == 0:
        conn.executescript(_SCHEMA_V1)
    conn.executescript(_SCHEMA_V2)
    # version is the PRIMARY KEY, so clear stale rows before recording the new one.
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (2,))
    conn.commit()


def save_deck(
    conn: sqlite3.Connection,
    name: str,
    hero_class: str,
    format_name: str,
    deckstring: str,
) -> int:
    """Insert a deck and return its id."""
    cursor = conn.execute(
        "INSERT INTO decks (name, hero_class, format, deckstring) VALUES (?, ?, ?, ?)",
        (name, hero_class, format_name, deckstring),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def get_all_decks(conn: sqlite3.Connection) -> list[DeckSummary]:
    """Return all decks ordered by newest first (D-09)."""
    rows = conn.execute(
        "SELECT id, name, hero_class, format, deckstring, created_at "
        "FROM decks ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [
        DeckSummary(
            deck_id=row["id"],
            name=row["name"],
            hero_class=row["hero_class"],
            format=row["format"],
            deckstring=row["deckstring"],
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def delete_deck(conn: sqlite3.Connection, deck_id: int) -> None:
    """Delete a deck by id."""
    conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    conn.commit()
