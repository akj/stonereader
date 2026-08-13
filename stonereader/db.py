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


# --- Replay metadata CRUD (v2) ---

_REPLAY_COLUMNS = (
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
)


def insert_replay(conn: sqlite3.Connection, **fields: object) -> int:
    """Insert a replay metadata row and return its id.

    Accepts the writable replay columns as keyword arguments (``id`` and
    ``imported_at`` are assigned by SQLite). ``game_type`` and ``format_type``
    default to '' to match the schema; ``deck_name``, ``deck_id`` and
    ``duration_seconds`` default to NULL.
    """
    values = {col: fields.get(col) for col in _REPLAY_COLUMNS}
    if values["game_type"] is None:
        values["game_type"] = ""
    if values["format_type"] is None:
        values["format_type"] = ""
    placeholders = ", ".join("?" for _ in _REPLAY_COLUMNS)
    columns = ", ".join(_REPLAY_COLUMNS)
    cursor = conn.execute(
        f"INSERT INTO replays ({columns}) VALUES ({placeholders})",
        tuple(values[col] for col in _REPLAY_COLUMNS),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def get_all_replays(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all replay rows, newest first (played_at DESC, id DESC)."""
    return conn.execute(
        "SELECT * FROM replays ORDER BY played_at DESC, id DESC"
    ).fetchall()


def get_replay_by_checksum(
    conn: sqlite3.Connection, checksum: str
) -> sqlite3.Row | None:
    """Return the replay row with the given checksum, or None."""
    return conn.execute(
        "SELECT * FROM replays WHERE checksum = ?", (checksum,)
    ).fetchone()


def delete_replay(conn: sqlite3.Connection, replay_id: int) -> None:
    """Delete a replay metadata row by id."""
    conn.execute("DELETE FROM replays WHERE id = ?", (replay_id,))
    conn.commit()
