"""Replay rows shared by the Replays and Games Surfaces (ADR-0017)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from stonereader.models.card import CardDatabase
from stonereader.services._replay_loader import ReplayLoadError, load_replay
from stonereader.services._replay_store import ReplayMeta, ReplayStore
from stonereader.spoken import class_name, count
from stonereader.surfaces.replay_viewer import CurrentReplay
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import NavigationController
from stonereader.ui.registry import Command
from stonereader.ui.surface import Binding


_OUTCOMES = {"WON": "Won against", "LOST": "Lost to", "TIED": "Tied with"}
# Said only when unusual: Ranked and Standard are the usual case, and unknown
# or empty values are omitted rather than spoken as "Unknown".
_USUAL_GAME_TYPES = {"", "UNKNOWN", "RANKED"}
_USUAL_FORMATS = {"", "UNKNOWN", "STANDARD"}
_GAME_TYPE_NAMES = {
    "VS_AI": "Practice",
    "VS_FRIEND": "Friendly",
    "TAVERNBRAWL": "Tavern Brawl",
}
_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def replay_title(meta: ReplayMeta, now: datetime, *, with_deck: bool = True) -> str:
    """Return a game's Title line, most telling part first.

    "Won against Mage in 8 turns, today 3:36 PM, Odd Hunter, Casual, Wild,
    imported, not counted" — every part after the first only when it applies.
    """
    outcome = _OUTCOMES.get(meta.result.upper(), "Result unknown against")
    parts = [
        f"{outcome} {class_name(meta.opponent_class)} "
        f"in {count(meta.turns, 'turn')}"
    ]
    when = spoken_when(meta.played_at, now)
    if when is not None:
        parts.append(when)
    if with_deck and meta.deck_name:
        parts.append(meta.deck_name)
    game_type = (meta.game_type or "").upper()
    if game_type not in _USUAL_GAME_TYPES:
        parts.append(_GAME_TYPE_NAMES.get(game_type, _title(game_type)))
    format_type = (meta.format_type or "").upper()
    if format_type not in _USUAL_FORMATS:
        parts.append(_title(format_type))
    if meta.source != "live_auto":
        parts.append("imported")
    if not meta.in_stats:
        parts.append("not counted")
    return ", ".join(parts)


def spoken_when(played_at: str, now: datetime) -> str | None:
    """Say when a game was played, relative to ``now``, in local time.

    A timestamp with an offset is converted to the User's local time; one
    without is already local. ``now`` is the local wall clock.
    """
    try:
        played = datetime.fromisoformat(played_at)
    except ValueError:
        return None
    if played.tzinfo is not None:
        played = played.astimezone()
    days = (now.date() - played.date()).days
    if days == 0:
        return f"today {_clock(played)}"
    if days == 1:
        return f"yesterday {_clock(played)}"
    if 1 < days < 7:
        return _WEEKDAYS[played.weekday()]
    date = f"{_MONTHS[played.month - 1]} {played.day}"
    return date if played.year == now.year else f"{date}, {played.year}"


def open_replay(
    meta: ReplayMeta,
    announcer: Announcer,
    nav: NavigationController,
    card_db: CardDatabase,
    current_replay: CurrentReplay,
) -> None:
    """Load a stored game and drill into the Replay Viewer on it."""
    try:
        replay = load_replay(Path(meta.file_path), card_db)
    except ReplayLoadError:
        announcer.noop("Could not open replay; the file may be invalid")
        return
    current_replay.set(replay)
    nav.drill_down("Replay Viewer")


class ReplayDeletion:
    """Delete (press twice) and Shift+Delete for a menu of replay rows."""

    def __init__(
        self,
        prefix: str,
        announcer: Announcer,
        store: ReplayStore,
        focused: Callable[[], ReplayMeta | None],
    ) -> None:
        self._prefix = prefix
        self._announcer = announcer
        self._store = store
        self._focused = focused
        self._engine: VerticalMenuEngine | None = None
        self._armed: ArmedAction | None = None

    def attach(self, engine: VerticalMenuEngine) -> None:
        self._engine = engine
        self._armed = ArmedAction(engine, self._announcer)

    def disarm(self) -> None:
        if self._armed is not None:
            self._armed.disarm()

    def bindings(self) -> list[Binding]:
        return [
            Binding(
                Chord("delete"),
                Command(
                    f"{self._prefix}.delete",
                    "Delete: delete this replay, press twice",
                    self._arm,
                ),
            ),
            Binding(
                Chord("delete", shift=True),
                Command(
                    f"{self._prefix}.delete_now",
                    "Shift+Delete: delete this replay without asking",
                    self._delete_now,
                ),
            ),
        ]

    def _arm(self) -> None:
        meta = self._focused()
        if meta is None:
            self._announcer.noop("Nothing to delete here")
            return
        if self._armed is None:
            raise RuntimeError("Replay deletion is not attached")
        self._armed.press(
            str(meta.id),
            "Press Delete again to delete this replay",
            lambda: self._finish(meta),
        )

    def _delete_now(self) -> None:
        meta = self._focused()
        if meta is None:
            self._announcer.noop("Nothing to delete here")
            return
        self._finish(meta)

    def _finish(self, meta: ReplayMeta) -> None:
        if self._armed is None or self._engine is None:
            raise RuntimeError("Replay deletion is not attached")
        self._armed.disarm()
        self._store.delete(meta.id)
        # Replay titles are intentionally too long for a confirmation object.
        self._announcer.confirmation("Replay deleted")
        self._engine.on_landing(continues=True)


def _clock(moment: datetime) -> str:
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


def _title(value: str) -> str:
    return value.replace("_", " ").title()
