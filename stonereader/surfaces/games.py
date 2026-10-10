"""Games Surface: the games behind one Deck page record row (ADR-0017)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime

from stonereader.models.card import CardDatabase
from stonereader.services._replay_store import ReplayMeta, ReplayStore
from stonereader.services._stats import compute_records
from stonereader.surfaces._deck_data import CurrentGames
from stonereader.surfaces._replay_rows import ReplayDeletion, open_replay, replay_title
from stonereader.surfaces.replay_viewer import CurrentReplay
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType


def build_games(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    conn: sqlite3.Connection,
    store: ReplayStore,
    card_db: CardDatabase,
    current_games: CurrentGames,
    current_replay: CurrentReplay,
    *,
    now: Callable[[], datetime] = datetime.now,
) -> ActiveSurface:
    """Build the lazy singleton that lists the current selection's games."""
    engine: VerticalMenuEngine | None = None

    def games() -> dict[str, ReplayMeta]:
        # Recomputed on every access (ADR-0012): a deleted game leaves the list.
        record = current_games.get().record(compute_records(conn))
        return {f"replay.{meta.id}": meta for meta in record.games}

    def options() -> list[MenuOption]:
        moment = now()
        with_deck = not current_games.get().one_deck
        return [
            MenuOption(
                option_id,
                lambda meta=meta: replay_title(meta, moment, with_deck=with_deck),
                lambda meta=meta: open_replay(
                    meta, announcer, nav, card_db, current_replay
                ),
            )
            for option_id, meta in games().items()
        ]

    def focused() -> ReplayMeta | None:
        if engine is None:
            raise RuntimeError("Games engine is not active")
        option_id = engine.current_option_id
        return None if option_id is None else games().get(option_id)

    def activate_current() -> None:
        if engine is None:
            raise RuntimeError("Games engine is not active")
        if not engine.activate_current():
            announcer.slot_noop(Slot.ENTER)

    deletion = ReplayDeletion("games", announcer, store, focused)
    spec = SurfaceSpec(
        "Games",
        WidgetType.VERTICAL_MENU,
        context_label=lambda: current_games.get().label(),
        options=options,
        bindings=deletion.bindings(),
        slot_fills={
            Slot.ENTER: Command(
                "games.open",
                "Enter: open this replay",
                activate_current,
            )
        },
        display_name=lambda: current_games.get().label(),
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Games requires a vertical-menu engine")
    engine = surface.engine
    deletion.attach(engine)

    def reopen() -> None:
        # A new selection is new content: start at its newest game, unarmed.
        deletion.disarm()
        engine.set_cursor(0)

    current_games.subscribe(reopen)
    return surface
