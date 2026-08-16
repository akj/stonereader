"""Saved Decks Surface."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from stonereader.db import delete_deck
from stonereader.surfaces._deck_data import CurrentDeck, DeckData, DeckRow, spoken_enum
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, SurfaceSpec, WidgetType, ZoneSpec


class OfferSubjectSink(Protocol):
    def mark_offer_subject_seen(self, subject: str) -> None: ...


@dataclass(frozen=True)
class ActionRow:
    action_id: str
    label: str


DeckItem: TypeAlias = DeckRow | ActionRow

_IMPORT = ActionRow("import", "Import deck…")
_STATISTICS = ActionRow("statistics", "Statistics…")


def build_decks(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    conn: sqlite3.Connection,
    data: DeckData,
    current_deck: CurrentDeck,
    sink: OfferSubjectSink,
    copy_to_clipboard: Callable[[str], None],
) -> ActiveSurface:
    """Build the DB-backed saved-deck list and its action rows."""
    engine: HorizontalListEngine | None = None
    armed: ArmedAction | None = None

    def items() -> list[DeckItem]:
        return [*data.all(), _IMPORT, _STATISTICS]

    def title(item: DeckItem) -> str:
        return item.summary.name if isinstance(item, DeckRow) else item.label

    def details(item: DeckItem) -> list[str]:
        if isinstance(item, ActionRow):
            return []
        played = (
            f"Last played {item.last_played}"
            if item.last_played is not None
            else "Never played"
        )
        return [
            f"{spoken_enum(item.summary.hero_class)}, {item.summary.format}",
            f"{item.card_count} cards",
            played,
        ]

    def selected() -> DeckItem:
        if engine is None:
            raise RuntimeError("Decks engine is not active")
        item = engine.current_item()
        if not isinstance(item, (DeckRow, ActionRow)):
            raise RuntimeError("Decks always has action rows")
        return item

    def open_selected() -> None:
        item = selected()
        if isinstance(item, DeckRow):
            current_deck.set(item.summary)
            nav.drill_down("Deck detail")
        elif item.action_id == "import":
            nav.drill_down("Import Deck")
        else:
            announcer.noop("Statistics: not yet migrated")

    def finish_delete(item: DeckRow) -> None:
        if armed is not None:
            armed.disarm()
        delete_deck(conn, item.summary.deck_id)
        announcer.confirmation(f"{item.summary.name} deleted")
        if engine is None:
            raise RuntimeError("Decks engine is not active")
        engine.on_landing(queued=True)

    def arm_delete() -> None:
        item = selected()
        if isinstance(item, ActionRow):
            announcer.noop("Nothing to delete here")
            return
        if armed is None:
            raise RuntimeError("Decks armed action is not active")
        armed.press(
            str(item.summary.deck_id),
            f"Press Delete again to delete {item.summary.name}",
            lambda: finish_delete(item),
        )

    def delete_now() -> None:
        item = selected()
        if isinstance(item, ActionRow):
            announcer.noop("Nothing to delete here")
            return
        finish_delete(item)

    def copy_code() -> None:
        item = selected()
        if isinstance(item, ActionRow):
            announcer.noop("Nothing to copy here")
            return
        copy_to_clipboard(item.summary.deckstring)
        announcer.confirmation("Deck code copied")
        sink.mark_offer_subject_seen(item.summary.deckstring)

    spec = SurfaceSpec(
        "Decks",
        WidgetType.HORIZONTAL_LIST,
        zones=[ZoneSpec("decks", "Decks", items, title, details)],
        bindings=[
            Binding(
                Chord("delete"),
                Command(
                    "decks.delete",
                    "Delete: delete this deck, press twice",
                    arm_delete,
                ),
            ),
            Binding(
                Chord("delete", shift=True),
                Command(
                    "decks.delete_now",
                    "Shift+Delete: delete this deck without asking",
                    delete_now,
                ),
            ),
            Binding(
                Chord("c"),
                Command(
                    "decks.copy",
                    "C: copy this deck's code",
                    copy_code,
                ),
            ),
        ],
        slot_fills={
            Slot.ENTER: Command(
                "decks.open",
                "Enter: open the selected deck",
                open_selected,
            )
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, HorizontalListEngine):
        raise TypeError("Decks requires a horizontal-list engine")
    engine = surface.engine
    armed = ArmedAction(engine, announcer)
    return surface
