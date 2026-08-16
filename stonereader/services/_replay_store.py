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
from typing import TYPE_CHECKING

from stonereader import db
from stonereader.services._exceptions import ServicesError

if TYPE_CHECKING:
    from stonereader.models.card import CardDatabase

logger = logging.getLogger(__name__)


class ReplayImportError(ServicesError):
    """Raised when a replay source file cannot be read or imported.

    Wraps the underlying OS/decoding error so callers (presenter, app) never
    see a bare ``OSError``/``UnicodeDecodeError`` crash from import.
    """


@dataclass(frozen=True)
class ReplayMeta:
    """Immutable view of a single ``replays`` row."""

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
    in_stats: bool

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
            in_stats=bool(row["in_stats"]),
        )


@dataclass(frozen=True)
class ReplaySaveResult:
    """A stored replay plus whether this call created it."""

    meta: ReplayMeta
    created: bool


@dataclass(frozen=True)
class _ImportMetadata:
    friendly_class: str
    opponent_class: str
    result: str
    turns: int
    game_type: str
    format_type: str
    played_at: str


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

    def __init__(
        self,
        conn,
        replay_dir: Path,
        card_db: CardDatabase | None = None,
    ) -> None:
        self._conn = conn
        self._replay_dir = Path(replay_dir)
        self._card_db = card_db

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
        in_stats: bool = False,
        played_at: str,
        duration_seconds: int | None = None,
        raw_log: str | None = None,
    ) -> ReplaySaveResult:
        """Persist replay ``xml`` and report whether a record was created.

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
            return ReplaySaveResult(ReplayMeta.from_row(existing), created=False)

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
            in_stats=int(in_stats),
        )
        row = db.get_replay_by_checksum(self._conn, checksum)
        assert row is not None  # we just inserted it
        meta = ReplayMeta.from_row(row)
        assert meta.id == replay_id
        return ReplaySaveResult(meta, created=True)

    def import_file(
        self,
        src_path: Path,
        *,
        source: str = "manual_import",
        in_stats: bool = False,
        friendly_class: str | None = None,
        opponent_class: str | None = None,
        result: str | None = None,
        turns: int | None = None,
        game_type: str | None = None,
        format_type: str | None = None,
        deck_name: str | None = None,
        deck_id: int | None = None,
        played_at: str | None = None,
        duration_seconds: int | None = None,
    ) -> ReplaySaveResult:
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
        existing = db.get_replay_by_checksum(self._conn, _checksum(xml))
        if existing is not None:
            return ReplaySaveResult(ReplayMeta.from_row(existing), created=False)
        derived: _ImportMetadata | None = None
        if any(
            value is None
            for value in (
                friendly_class,
                opponent_class,
                result,
                turns,
                played_at,
            )
        ):
            try:
                derived = _derive_import_metadata(Path(src_path), self._card_db)
            except Exception as exc:
                raise ReplayImportError(
                    f"Cannot read replay metadata from {src_path!r}: {exc}"
                ) from exc
        if derived is not None:
            friendly_class = friendly_class or derived.friendly_class
            opponent_class = opponent_class or derived.opponent_class
            result = result or derived.result
            turns = derived.turns if turns is None else turns
            game_type = derived.game_type if game_type is None else game_type
            format_type = derived.format_type if format_type is None else format_type
            played_at = played_at or derived.played_at
        assert friendly_class is not None
        assert opponent_class is not None
        assert result is not None
        assert turns is not None
        assert played_at is not None
        return self.save_xml(
            xml,
            source=source,
            in_stats=in_stats,
            friendly_class=friendly_class,
            opponent_class=opponent_class,
            result=result,
            turns=turns,
            game_type=game_type or "",
            format_type=format_type or "",
            deck_name=deck_name,
            deck_id=deck_id,
            played_at=played_at,
            duration_seconds=duration_seconds,
        )

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

    def set_in_stats(self, replay_id: int, in_stats: bool) -> None:
        """Set one replay's stats-corpus membership."""
        db.set_replay_in_stats(self._conn, replay_id, in_stats)

    def prune(self, limit: int | None) -> None:
        """Delete oldest replays beyond ``limit``; ``None`` keeps everything."""
        if limit is None:
            return
        if limit < 0:
            raise ValueError("Replay retention limit must not be negative")
        for replay in reversed(self.all_replays()[limit:]):
            self.delete(replay.id)

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


def _derive_import_metadata(
    path: Path, card_db: CardDatabase | None = None
) -> _ImportMetadata:
    """Derive the minimal DB metadata exposed by the replay loader."""
    from stonereader.services._replay_loader import load_replay

    replay = load_replay(path, card_db)
    states = replay.states

    # Imported perspective is intentionally the replay's recorded Friendly side
    # (ADR-0012 documents the caveat; the in-stats toggle is the remedy).
    player_playstate = next(
        (
            state.player_playstate.upper()
            for state in reversed(states)
            if state.player_playstate.upper() in ("WON", "LOST", "TIED")
        ),
        "",
    )
    if not player_playstate:
        opponent_playstate = next(
            (
                state.opponent_playstate.upper()
                for state in reversed(states)
                if state.opponent_playstate.upper() in ("WON", "LOST")
            ),
            "",
        )
        player_playstate = {
            "WON": "LOST",
            "LOST": "WON",
        }.get(opponent_playstate, "UNKNOWN")

    def latest(getter) -> str:
        return next(
            (
                value
                for state in reversed(states)
                if (value := str(getter(state) or "").strip())
            ),
            "",
        )

    return _ImportMetadata(
        friendly_class=latest(lambda state: state.player_hero.hero_class),
        opponent_class=latest(lambda state: state.opponent_hero.hero_class),
        result=player_playstate,
        turns=max(state.turn for state in states),
        game_type=latest(lambda state: state.game_type),
        format_type=latest(lambda state: state.format_type),
        played_at=datetime.fromtimestamp(path.stat().st_mtime)
        .astimezone()
        .isoformat(),
    )
