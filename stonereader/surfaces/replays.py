"""Stored Replays Surface."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from stonereader.models.card import CardDatabase
from stonereader.services._replay_store import ReplayMeta, ReplayStore
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces._replay_rows import ReplayDeletion, open_replay, replay_title
from stonereader.surfaces.replay_viewer import CurrentReplay
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, MenuOption, SurfaceSpec, WidgetType


def build_replays(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    store: ReplayStore,
    card_db: CardDatabase,
    current_replay: CurrentReplay,
    data: DeckData,
    current_deck: CurrentDeck,
    *,
    now: Callable[[], datetime] = datetime.now,
) -> ActiveSurface:
    """Build the newest-first replay menu ending in Import replays…."""
    engine: VerticalMenuEngine | None = None

    def replays() -> dict[str, ReplayMeta]:
        return {f"replay.{meta.id}": meta for meta in store.all_replays()}

    def options() -> list[MenuOption]:
        moment = now()
        return [
            *(
                MenuOption(
                    option_id,
                    lambda meta=meta: replay_title(meta, moment),
                    lambda meta=meta: open_replay(
                        meta, announcer, nav, card_db, current_replay
                    ),
                )
                for option_id, meta in replays().items()
            ),
            MenuOption(
                "import",
                lambda: "Import replays…",
                lambda: nav.drill_down("Import Replays"),
            ),
        ]

    def focused() -> ReplayMeta | None:
        if engine is None:
            raise RuntimeError("Replays engine is not active")
        option_id = engine.current_option_id
        return None if option_id is None else replays().get(option_id)

    def activate_current() -> None:
        if engine is None:
            raise RuntimeError("Replays engine is not active")
        if not engine.activate_current():
            announcer.slot_noop(Slot.ENTER)

    def toggle_stats() -> None:
        meta = focused()
        if meta is None:
            announcer.noop("Nothing to count here")
            return
        included = not meta.in_stats
        store.set_in_stats(meta.id, included)
        announcer.confirmation(
            "Included in stats" if included else "Excluded from stats"
        )

    def open_deck() -> None:
        meta = focused()
        if meta is None:
            announcer.noop("Nothing to open here")
            return
        summary = data.saved(meta.deck_id)
        if summary is None:
            announcer.noop("No saved deck for this game")
            return
        current_deck.set(summary)
        nav.drill_down("Deck")

    deletion = ReplayDeletion("replays", announcer, store, focused)
    spec = SurfaceSpec(
        "Replays",
        WidgetType.VERTICAL_MENU,
        options=options,
        bindings=[
            Binding(
                Chord("space"),
                Command(
                    "replays.toggle_stats",
                    "Space: count this game in your stats",
                    toggle_stats,
                ),
            ),
            *deletion.bindings(),
            Binding(
                Chord("d"),
                Command(
                    "replays.open_deck",
                    "D: open this game's deck",
                    open_deck,
                ),
            ),
        ],
        slot_fills={
            Slot.ENTER: Command(
                "replays.open",
                "Enter: open this replay",
                activate_current,
            )
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Replays requires a vertical-menu engine")
    engine = surface.engine
    deletion.attach(engine)
    return surface
