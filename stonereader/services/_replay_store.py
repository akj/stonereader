"""Replay store — persists .hsreplay files plus SQLite metadata (Slice #11).

Replay CONTENT lives in ``.hsreplay`` files on disk under a managed
``replay_dir``; lightweight metadata lives in the ``replays`` table (schema
v2). The store is the single seam between the two: it writes the file, inserts
the row, dedupes by content checksum, writes an optional ``.hdtreplay`` raw-log
sidecar, and tears all three down on delete.

Content is treated OPAQUELY here — the store neither parses nor validates
HSReplay XML. Whatever text it is handed is hashed (sha256 of the utf-8 bytes)
to form the dedupe key and written verbatim. This keeps the store reusable for
any string payload and lets the translation/validation concerns live elsewhere.

The connection and ``replay_dir`` are always injectable so tests can use a
``tmp_path``; :func:`default_replay_dir` mirrors ``db.get_connection``'s
``~/.stonereader`` location for production callers.
"""

from __future__ import annotations

import hashlib
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from stonereader import db
from stonereader.services._exceptions import ServicesError

logger = logging.getLogger(__name__)


class ReplayImportError(ServicesError):
    """Raised when a replay source file cannot be read or imported.

    Wraps the underlying OS/decoding error so callers (presenter, app) never
    see a bare ``OSError``/``UnicodeDecodeError`` crash from import.
    """


@dataclass(frozen=True)
class ReplayMeta:
    """Immutable view of a single ``replays`` row (all 15 columns)."""

    id: int
    file_path: str
    checksum: str
    source: str
    friendly_class: str
    opponent_class: str
    result: str
    turns: int
    game_type: str
    format_type: str
    deck_name: str | None
    deck_id: int | None
    played_at: str
    duration_seconds: int | None
    imported_at: str

    @classmethod
    def from_row(cls, row) -> "ReplayMeta":
        """Build a ReplayMeta from a sqlite3.Row (or any mapping-by-key)."""
        return cls(
            id=row["id"],
            file_path=row["file_path"],
            checksum=row["checksum"],
            source=row["source"],
            friendly_class=row["friendly_class"],
            opponent_class=row["opponent_class"],
            result=row["result"],
            turns=row["turns"],
            game_type=row["game_type"],
            format_type=row["format_type"],
            deck_name=row["deck_name"],
            deck_id=row["deck_id"],
            played_at=row["played_at"],
            duration_seconds=row["duration_seconds"],
            imported_at=row["imported_at"],
        )


def default_replay_dir() -> Path:
    """Production replay directory: ``~/.stonereader/replays``."""
    return Path.home() / ".stonereader" / "replays"


def _checksum(xml: str) -> str:
    """sha256 hex digest of the xml's utf-8 bytes (the dedupe key)."""
    return hashlib.sha256(xml.encode("utf-8")).hexdigest()


def _safe(value: str) -> str:
    """Reduce a value to a filesystem-safe token for use in a filename."""
    token = "".join(c if c.isalnum() else "_" for c in str(value))
    return token or "unknown"


class ReplayStore:
    """Stores replay XML on disk and its metadata in SQLite, deduped by checksum."""

    def __init__(self, conn, replay_dir: Path) -> None:
        self._conn = conn
        self._replay_dir = Path(replay_dir)

    def save_xml(
        self,
        xml: str,
        *,
        source: str,
        friendly_class: str,
        opponent_class: str,
        result: str,
        turns: int,
        game_type: str = "",
        format_type: str = "",
        deck_name: str | None = None,
        deck_id: int | None = None,
        played_at: str,
        duration_seconds: int | None = None,
        raw_log: str | None = None,
    ) -> ReplayMeta:
        """Persist replay ``xml`` and its metadata, returning the stored record.

        Dedupes by sha256 checksum of the xml: if a replay with the same
        content already exists, returns the EXISTING record without writing a
        new file or inserting a new row. Otherwise writes the ``.hsreplay``
        file and inserts the metadata row. When ``raw_log`` is provided, also
        writes the source Power.log lines in Hearthstone Deck Tracker's
        one-entry ``.hdtreplay`` ZIP format. A sidecar failure is logged but
        cannot invalidate the already-written XML replay.
        """
        checksum = _checksum(xml)
        existing = db.get_replay_by_checksum(self._conn, checksum)
        if existing is not None:
            return ReplayMeta.from_row(existing)

        file_path = self._write_file(
            xml,
            checksum=checksum,
            friendly_class=friendly_class,
            opponent_class=opponent_class,
            played_at=played_at,
        )
        if raw_log is not None:
            self._write_raw_log_sidecar(file_path, raw_log)
        replay_id = db.insert_replay(
            self._conn,
            file_path=str(file_path),
            checksum=checksum,
            source=source,
            friendly_class=friendly_class,
            opponent_class=opponent_class,
            result=result,
            turns=turns,
            game_type=game_type,
            format_type=format_type,
            deck_name=deck_name,
            deck_id=deck_id,
            played_at=played_at,
            duration_seconds=duration_seconds,
        )
        row = db.get_replay_by_checksum(self._conn, checksum)
        assert row is not None  # we just inserted it
        meta = ReplayMeta.from_row(row)
        assert meta.id == replay_id
        return meta

    def import_file(self, src_path: Path, **meta) -> ReplayMeta:
        """Import an external replay file into managed storage.

        Reads the source file's text, then runs the same dedupe + store path
        as :meth:`save_xml` (the caller supplies the metadata). A source that
        is missing or cannot be read/decoded raises :class:`ReplayImportError`
        rather than crashing.
        """
        try:
            xml = Path(src_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ReplayImportError(
                f"Cannot read replay source {src_path!r}: {exc}"
            ) from exc
        return self.save_xml(xml, **meta)

    def all_replays(self) -> list[ReplayMeta]:
        """Return all stored replays, newest first."""
        return [ReplayMeta.from_row(row) for row in db.get_all_replays(self._conn)]

    def delete(self, replay_id: int) -> None:
        """Remove a replay's metadata row AND its on-disk file.

        Tolerates an already-missing file (the row is still removed).
        """
        existing = next(
            (r for r in db.get_all_replays(self._conn) if r["id"] == replay_id),
            None,
        )
        db.delete_replay(self._conn, replay_id)
        if existing is not None:
            file_path = Path(existing["file_path"])
            file_path.unlink(missing_ok=True)
            file_path.with_suffix(".hdtreplay").unlink(missing_ok=True)

    @staticmethod
    def _write_raw_log_sidecar(file_path: Path, raw_log: str) -> None:
        """Best-effort write of HDT's uploadable raw-log replay container.

        ``.hdtreplay`` is not a second serialization of the game. It is a ZIP
        containing the source-of-truth Power.log excerpt under HDT's exact
        ``output_log.txt`` entry name, so a replay can be regenerated after a
        future serializer fix. Failure here must not cost the primary XML save.
        """
        sidecar_path = file_path.with_suffix(".hdtreplay")
        try:
            with zipfile.ZipFile(
                sidecar_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr("output_log.txt", raw_log)
        except Exception:
            logger.exception(
                "could not write raw-log replay sidecar %s; keeping XML replay",
                sidecar_path,
            )

    def _write_file(
        self,
        xml: str,
        *,
        checksum: str,
        friendly_class: str,
        opponent_class: str,
        played_at: str,
    ) -> Path:
        """Write the .hsreplay file under replay_dir/<date>/ and return its path."""
        date_dir, stamp = _date_and_stamp(played_at)
        target_dir = self._replay_dir / date_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        name = (
            f"{stamp}_{_safe(friendly_class)}_vs_{_safe(opponent_class)}"
            f"_{checksum[:12]}.hsreplay"
        )
        path = target_dir / name
        path.write_text(xml, encoding="utf-8")
        return path


def _date_and_stamp(played_at: str) -> tuple[str, str]:
    """Derive (YYYY-MM-DD dir, timestamp filename token) from played_at.

    Parses an ISO-8601-ish ``played_at`` string. Falls back to a sanitized
    form of the raw value when it cannot be parsed, so a malformed timestamp
    never blocks storage.
    """
    parsed = _parse_dt(played_at)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d"), parsed.strftime("%Y%m%d_%H%M%S")
    token = _safe(played_at)
    return token[:10] or "unknown", token


def _parse_dt(played_at: str) -> datetime | None:
    """Best-effort parse of played_at into a datetime, or None."""
    text = str(played_at).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
