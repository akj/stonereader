"""Deck Statistics Surface."""

from __future__ import annotations

import sqlite3

from stonereader.services._stats import StatsRow, compute_stats
from stonereader.surfaces._deck_data import spoken_enum
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import SurfaceSpec, WidgetType, ZoneSpec


_CLASS_NAMES = {
    "DEATHKNIGHT": "Death Knight",
    "DEMONHUNTER": "Demon Hunter",
}


def build_statistics(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    conn: sqlite3.Connection,
) -> ActiveSurface:
    """Build the always-current, DB-backed deck statistics list."""

    def items() -> list[StatsRow]:
        # Deliberately recompute on every provider access: local replay lists
        # are small, and ADR-0012 forbids cached or persisted aggregates.
        return compute_stats(conn)

    def title(row: StatsRow) -> str:
        if row.total_games == 0:
            return f"{row.name}, no games yet"
        value = f"{row.name}, {row.wins} wins, {row.losses} losses"
        if row.ties:
            value += f", {row.ties} ties"
        return value

    def details(row: StatsRow) -> list[str]:
        lines: list[str] = []
        if row.win_rate_percent is not None:
            lines.append(f"Win rate, {row.win_rate_percent} percent")
        if row.last20 is not None:
            wins, losses = row.last20
            lines.append(f"Last 20 games, {wins} wins, {losses} losses")
        lines.extend(
            f"Versus {_spoken_class(opponent_class)}, "
            f"{wins} wins, {losses} losses"
            for opponent_class, wins, losses in row.per_class
        )
        return lines

    spec = SurfaceSpec(
        "Statistics",
        WidgetType.HORIZONTAL_LIST,
        zones=[ZoneSpec("statistics", "Statistics", items, title, details)],
        slot_noops={Slot.ENTER: "Nothing to do here"},
    )
    return build_active_surface(spec, announcer, universal_bindings, nav)


def _spoken_class(value: str) -> str:
    key = value.upper() or "UNKNOWN"
    return _CLASS_NAMES.get(key, spoken_enum(key))
