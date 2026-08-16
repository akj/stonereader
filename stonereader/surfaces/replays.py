"""Stored Replays Surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeAlias

from stonereader.models.card import CardDatabase
from stonereader.services._replay_loader import ReplayLoadError, load_replay
from stonereader.services._replay_store import ReplayMeta, ReplayStore
from stonereader.surfaces._deck_data import spoken_enum
from stonereader.surfaces.replay_viewer import CurrentReplay
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, SurfaceSpec, WidgetType, ZoneSpec


@dataclass(frozen=True)
class ActionRow:
    action_id: str
    label: str


ReplayItem: TypeAlias = ReplayMeta | ActionRow

_IMPORT = ActionRow("import", "Import replays…")
_RESULTS = {
    "WON": "Won",
    "LOST": "Lost",
    "TIED": "Tied",
    # The spec pins no separate UNKNOWN string; title case is the ruling.
    "UNKNOWN": "Unknown",
}
_CLASS_NAMES = {
    "DEATHKNIGHT": "Death Knight",
    "DEMONHUNTER": "Demon Hunter",
}


def build_replays(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    store: ReplayStore,
    card_db: CardDatabase,
    current_replay: CurrentReplay,
) -> ActiveSurface:
    """Build the newest-first replay list and its import action row."""
    engine: HorizontalListEngine | None = None
    armed: ArmedAction | None = None

    def items() -> list[ReplayItem]:
        return [*store.all_replays(), _IMPORT]

    def title(item: ReplayItem) -> str:
        if isinstance(item, ActionRow):
            return item.label
        result = _RESULTS.get(item.result.upper(), "Unknown")
        class_key = (item.opponent_class or "UNKNOWN").upper()
        opponent = _CLASS_NAMES.get(class_key, spoken_enum(class_key))
        return f"{result} versus {opponent}, {item.turns} turns"

    def details(item: ReplayItem) -> list[str]:
        if isinstance(item, ActionRow):
            return []
        deck = f"Played {item.deck_name}" if item.deck_name else "Deck not detected"
        game_type = spoken_enum(item.game_type or "UNKNOWN")
        format_type = spoken_enum(item.format_type or "UNKNOWN")
        return [
            _spoken_played_at(item.played_at),
            deck,
            f"{game_type}, {format_type}",
            "Counted in stats" if item.in_stats else "Not counted",
            "Live recorded" if item.source == "live_auto" else "Imported",
        ]

    def selected() -> ReplayItem:
        if engine is None:
            raise RuntimeError("Replays engine is not active")
        item = engine.current_item()
        if not isinstance(item, (ReplayMeta, ActionRow)):
            raise RuntimeError("Replays always has an action row")
        return item

    def open_selected() -> None:
        item = selected()
        if isinstance(item, ActionRow):
            nav.drill_down("Import Replays")
        else:
            try:
                replay = load_replay(Path(item.file_path), card_db)
            except ReplayLoadError:
                announcer.noop("Could not open replay; the file may be invalid")
                return
            current_replay.set(replay)
            nav.drill_down("Replay Viewer")

    def toggle_stats() -> None:
        item = selected()
        if isinstance(item, ActionRow):
            announcer.noop("Nothing to count here")
            return
        included = not item.in_stats
        store.set_in_stats(item.id, included)
        announcer.confirmation(
            "Included in stats" if included else "Excluded from stats"
        )

    def finish_delete(item: ReplayMeta) -> None:
        if armed is not None:
            armed.disarm()
        store.delete(item.id)
        # Replay titles are intentionally too long for a confirmation object.
        announcer.confirmation("Replay deleted")
        if engine is None:
            raise RuntimeError("Replays engine is not active")
        engine.on_landing(queued=True)

    def arm_delete() -> None:
        item = selected()
        if isinstance(item, ActionRow):
            announcer.noop("Nothing to delete here")
            return
        if armed is None:
            raise RuntimeError("Replays armed action is not active")
        armed.press(
            str(item.id),
            "Press Delete again to delete this replay",
            lambda: finish_delete(item),
        )

    def delete_now() -> None:
        item = selected()
        if isinstance(item, ActionRow):
            announcer.noop("Nothing to delete here")
            return
        finish_delete(item)

    spec = SurfaceSpec(
        "Replays",
        WidgetType.HORIZONTAL_LIST,
        zones=[ZoneSpec("replays", "Replays", items, title, details)],
        bindings=[
            Binding(
                Chord("space"),
                Command(
                    "replays.toggle_stats",
                    "Space: count this game in your stats",
                    toggle_stats,
                ),
            ),
            Binding(
                Chord("delete"),
                Command(
                    "replays.delete",
                    "Delete: delete this replay, press twice",
                    arm_delete,
                ),
            ),
            Binding(
                Chord("delete", shift=True),
                Command(
                    "replays.delete_now",
                    "Shift+Delete: delete this replay without asking",
                    delete_now,
                ),
            ),
        ],
        slot_fills={
            Slot.ENTER: Command(
                "replays.open",
                "Enter: open this replay",
                open_selected,
            )
        },
        slot_noops={Slot.SEARCH: "No search on this screen"},
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, HorizontalListEngine):
        raise TypeError("Replays requires a horizontal-list engine")
    engine = surface.engine
    armed = ArmedAction(engine, announcer)
    return surface


def _spoken_played_at(value: str) -> str:
    """Render a replay timestamp as ISO date then plain 24-hour time."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        date, _, time = value.partition("T" if "T" in value else " ")
        return f"{date}, {time[:5]}" if time else date
    return parsed.strftime("%Y-%m-%d, %H:%M")
