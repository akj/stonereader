"""Saved Decks Surface."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from stonereader.db import delete_deck
from stonereader.services._stats import Record, compute_records
from stonereader.surfaces._deck_data import (
    CurrentDeck,
    DeckData,
    DeckRow,
    DeckSubject,
    GamePool,
    OfferSubjectSink,
    copy_deck_code,
    spoken_record,
)
from stonereader.surfaces._spoken import class_name, count
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, MenuOption, SurfaceSpec, WidgetType


_FULL_DECK = 30


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
    """Build the record menu: All decks, saved decks, Other games, import."""
    engine: VerticalMenuEngine | None = None
    armed: ArmedAction | None = None

    def decks() -> dict[str, DeckRow]:
        return {f"deck.{row.summary.deck_id}": row for row in data.all()}

    def open_page(subject: DeckSubject) -> None:
        current_deck.set(subject)
        nav.drill_down("Deck")

    def options() -> list[MenuOption]:
        # Recomputed on every access (ADR-0012): no cached aggregates.
        records = compute_records(conn)
        rows = [
            MenuOption(
                "all",
                lambda: f"All decks, {spoken_record(records.all_decks)}",
                lambda: open_page(GamePool.ALL_DECKS),
            ),
            *(
                MenuOption(
                    option_id,
                    lambda row=row: _deck_title(
                        row, records.deck(row.summary.deck_id)
                    ),
                    lambda row=row: open_page(row.summary),
                )
                for option_id, row in decks().items()
            ),
        ]
        if records.other_games.games:
            rows.append(
                MenuOption(
                    "other",
                    lambda: f"Other games, {spoken_record(records.other_games)}",
                    lambda: open_page(GamePool.OTHER_GAMES),
                )
            )
        rows.append(
            MenuOption(
                "import",
                lambda: "Import deck…",
                lambda: nav.drill_down("Import Deck"),
            )
        )
        return rows

    def focused() -> DeckRow | None:
        if engine is None:
            raise RuntimeError("Decks engine is not active")
        option_id = engine.current_option_id
        return None if option_id is None else decks().get(option_id)

    def activate_current() -> None:
        if engine is None:
            raise RuntimeError("Decks engine is not active")
        if not engine.activate_current():
            announcer.slot_noop(Slot.ENTER)

    def finish_delete(row: DeckRow) -> None:
        if armed is not None:
            armed.disarm()
        delete_deck(conn, row.summary.deck_id)
        announcer.confirmation(f"{row.summary.name} deleted")
        if engine is None:
            raise RuntimeError("Decks engine is not active")
        engine.on_landing(continues=True)

    def arm_delete() -> None:
        row = focused()
        if row is None:
            announcer.noop("Nothing to delete here")
            return
        if armed is None:
            raise RuntimeError("Decks armed action is not active")
        armed.press(
            str(row.summary.deck_id),
            f"Press Delete again to delete {row.summary.name}",
            lambda: finish_delete(row),
        )

    def delete_now() -> None:
        row = focused()
        if row is None:
            announcer.noop("Nothing to delete here")
            return
        finish_delete(row)

    def copy_code() -> None:
        row = focused()
        if row is None:
            announcer.noop("Nothing to copy here")
            return
        copy_deck_code(row.summary, announcer, copy_to_clipboard, sink)

    spec = SurfaceSpec(
        "Decks",
        WidgetType.VERTICAL_MENU,
        options=options,
        bindings=[
            Binding(
                Chord("c"),
                Command(
                    "decks.copy",
                    "C: copy this deck's code",
                    copy_code,
                ),
            ),
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
        ],
        slot_fills={
            Slot.ENTER: Command(
                "decks.open",
                "Enter: open the selected deck",
                activate_current,
            )
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Decks requires a vertical-menu engine")
    engine = surface.engine
    armed = ArmedAction(engine, announcer)
    return surface


def _deck_title(row: DeckRow, record: Record) -> str:
    """Say what tells a deck apart: "Odd Hunter, Wild, 29 cards, 3 wins, 1 loss".

    The class is omitted when the name already says it, Wild is said only for
    Wild decks, and the card count only when the deck is not full.
    """
    parts = [row.summary.name]
    spoken_class = class_name(row.summary.hero_class)
    if spoken_class.casefold() not in row.summary.name.casefold():
        parts.append(spoken_class)
    if row.summary.format.casefold() == "wild":
        parts.append("Wild")
    if row.card_count != _FULL_DECK:
        parts.append(count(row.card_count, "card"))
    parts.append(spoken_record(record))
    return ", ".join(parts)
