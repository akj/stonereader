"""SQLite database for persisting decks and game history."""

from __future__ import annotations

import sqlite3
import logging
import threading
import time
from pathlib import Path

from stonereader.models.deck import DeckSummary

logger = logging.getLogger(__name__)

# Historical schema used only to exercise upgrades; fresh databases never run it.
_SCHEMA_V1_LEGACY = """
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

# v4 adds no columns; it marks replay metadata as re-derived from the stored
# files (see _rederive_replay_metadata).
_SCHEMA_V4_FRESH = """
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
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    in_stats INTEGER NOT NULL DEFAULT 0
);
"""

REPLAY_SOURCES = ("live_auto", "manual_import")
REPLAY_RESULTS = ("WON", "LOST", "TIED", "UNKNOWN")

_backfill_lock = threading.Lock()
_backfill_workers: dict[str, threading.Thread] = {}
_BACKFILL_STARTUP_GRACE_SECONDS = 0.05


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

    Fresh databases receive the current schema. Upgrades preserve decks and
    replays, add stats membership, backfill replay deck attribution, remove
    the obsolete v1 ``games`` table, and re-derive replay metadata (v4). The
    backfills run in the background; v3 becomes v4 when that pass completes.
    """
    version = get_schema_version(conn)
    if version == 0:
        conn.executescript(_SCHEMA_V4_FRESH)
        _set_schema_version(conn, 4)
        conn.commit()
    elif version < 3:
        if version < 2:
            conn.executescript(_SCHEMA_V2)
        conn.execute(
            "ALTER TABLE replays ADD COLUMN in_stats INTEGER NOT NULL DEFAULT 0"
        )
        conn.execute(
            "UPDATE replays SET in_stats = "
            "CASE WHEN source = 'live_auto' THEN 1 ELSE 0 END"
        )
        conn.execute("DROP TABLE IF EXISTS games")
        _set_schema_version(conn, 3)
        conn.commit()

    if get_schema_version(conn) == 3 and not _has_replays(conn):
        _set_schema_version(conn, 4)
        conn.commit()

    if _replay_deck_backfill_needed(conn) or get_schema_version(conn) < 4:
        _start_replay_backfill(conn)


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Replace the singleton schema-version row."""
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def _has_replays(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM replays LIMIT 1").fetchone() is not None


def _replay_deck_backfill_needed(conn: sqlite3.Connection) -> bool:
    """Return whether any replay still needs deck attribution."""
    return (
        conn.execute(
            "SELECT 1 FROM replays WHERE deck_id IS NULL LIMIT 1"
        ).fetchone()
        is not None
    )


def _start_replay_backfill(conn: sqlite3.Connection) -> None:
    """Start the replay backfills on a connection-local worker."""
    row = next(
        (row for row in conn.execute("PRAGMA database_list") if row[1] == "main"),
        None,
    )
    db_path = str(row[2]) if row is not None and row[2] else None
    if db_path is None:
        logger.warning("replay backfill skipped for an in-memory database")
        return
    with _backfill_lock:
        worker = _backfill_workers.get(db_path)
        if worker is not None and worker.is_alive():
            return
        worker = threading.Thread(
            target=_run_replay_backfill,
            args=(db_path,),
            name="stonereader-replay-backfill",
            daemon=True,
        )
        _backfill_workers[db_path] = worker
        worker.start()
    worker.join(_BACKFILL_STARTUP_GRACE_SECONDS)


def _run_replay_backfill(db_path: str) -> None:
    """Run whichever replay backfills remain on a fresh SQLite connection."""
    try:
        conn = get_connection(db_path)
        try:
            if _replay_deck_backfill_needed(conn):
                _backfill_replay_decks(conn)
                conn.commit()
            if get_schema_version(conn) < 4:
                _rederive_replay_metadata(conn)
        finally:
            conn.close()
    except Exception:
        logger.exception("replay backfill failed")
    finally:
        current = threading.current_thread()
        with _backfill_lock:
            if _backfill_workers.get(db_path) is current:
                del _backfill_workers[db_path]


def _wait_for_replay_backfills(timeout: float | None = None) -> bool:
    """Wait for current backfills; primarily useful at test/smoke seams."""
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        with _backfill_lock:
            workers = tuple(_backfill_workers.values())
        if not workers:
            return True
        for worker in workers:
            remaining = (
                None if deadline is None else max(0.0, deadline - time.monotonic())
            )
            worker.join(remaining)
        if deadline is not None and time.monotonic() >= deadline:
            with _backfill_lock:
                return not any(
                    worker.is_alive() for worker in _backfill_workers.values()
                )


def _backfill_replay_decks(conn: sqlite3.Connection) -> None:
    """Attribute legacy replays from stored XML without blocking upgrades."""
    rows = conn.execute(
        "SELECT id, file_path FROM replays WHERE deck_id IS NULL"
    ).fetchall()
    updates: list[tuple[int, str, int]] = []
    decks = get_all_decks(conn)
    if rows and decks:
        try:
            from stonereader.models.card import CardDatabase
            from stonereader.services._deck_detect import detect_deck
            from stonereader.services._replay_loader import load_replay

            card_db = CardDatabase.load()
        except Exception:
            logger.exception("replay deck backfill setup failed; skipping attribution")
        else:
            for row in rows:
                try:
                    replay = load_replay(Path(row["file_path"]), card_db)
                    match = next(
                        (
                            detected
                            for state in replay.states
                            if (detected := detect_deck(state, decks, card_db))
                            is not None
                        ),
                        None,
                    )
                    if match is None:
                        continue
                    deck_id, deck_name = match
                    updates.append((deck_id, deck_name, row["id"]))
                except Exception:
                    logger.exception(
                        "replay deck backfill skipped replay %s", row["id"]
                    )
    attributed = 0
    if updates:
        cursor = conn.executemany(
            "UPDATE replays SET deck_id = ?, deck_name = ? "
            "WHERE id = ? AND deck_id IS NULL",
            updates,
        )
        attributed = max(cursor.rowcount, 0)
    skipped = len(rows) - attributed
    logger.info("replay deck backfill: attributed %d / skipped %d", attributed, skipped)


def _rederive_replay_metadata(conn: sqlite3.Connection) -> None:
    """v3 -> v4: re-derive turns, game type and format from each stored file.

    Rows written before the loader fix took a player's own turn counter for the
    game turn and never learned the game type or format. They are re-derived
    with the same function import uses for a new row. Result and classes are
    left alone: the engine always resolved them against the friendly player, so
    they were never mirrored. A file that fails to load keeps its row as is.
    Every update and the version bump commit together, so a pass that dies
    midway leaves v3 and the next startup repeats it.
    """
    from stonereader.services._replay_store import derive_replay_metadata

    rows = conn.execute(
        "SELECT id, file_path, turns, game_type, format_type FROM replays"
    ).fetchall()
    updates: list[tuple[int, str, str, int]] = []
    for row in rows:
        try:
            derived = derive_replay_metadata(Path(row["file_path"]))
        except Exception:
            logger.exception("replay metadata repair skipped replay %s", row["id"])
            continue
        # A file can omit what the row already knows (the recorder falls back
        # to plain XML when enrichment fails), so only known values replace.
        updates.append(
            (
                derived.turns or row["turns"],
                _known(derived.game_type, row["game_type"]),
                _known(derived.format_type, row["format_type"]),
                row["id"],
            )
        )
    conn.executemany(
        "UPDATE replays SET turns = ?, game_type = ?, format_type = ? WHERE id = ?",
        updates,
    )
    _set_schema_version(conn, 4)
    conn.commit()
    logger.info(
        "replay metadata repair: re-derived %d / skipped %d",
        len(updates),
        len(rows) - len(updates),
    )


def _known(derived: str, stored: str | None) -> str:
    """Prefer a derived enum name, falling back when the file did not say."""
    return derived if derived and derived.upper() != "UNKNOWN" else (stored or "")


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
    "in_stats",
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
    if values["in_stats"] is None:
        values["in_stats"] = 0
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


def set_replay_in_stats(
    conn: sqlite3.Connection, replay_id: int, in_stats: bool
) -> None:
    """Set one replay's stats-corpus membership."""
    conn.execute(
        "UPDATE replays SET in_stats = ? WHERE id = ?",
        (int(in_stats), replay_id),
    )
    conn.commit()
