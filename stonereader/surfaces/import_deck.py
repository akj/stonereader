"""Two-option Import Deck form Surface."""

from __future__ import annotations

import sqlite3
from typing import Protocol

from stonereader.db import save_deck
from stonereader.models.card import CardDatabase
from stonereader.models.deck import Deck
from stonereader.surfaces._deck_data import unique_import_name
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType
from stonereader.ui.text_mode import TextSession


class TextModeSink(Protocol):
    def enter_text_mode(self, session: TextSession) -> None: ...

    def exit_text_mode(self) -> None: ...


class ImportDeckField:
    """App-owned field state shared with the clipboard Offer path."""

    def __init__(self, value: str = "") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value


def build_import_deck(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    conn: sqlite3.Connection,
    card_db: CardDatabase,
    sink: TextModeSink,
    field: ImportDeckField,
) -> ActiveSurface:
    """Build the Import Deck form without entering Text mode on landing."""
    engine: VerticalMenuEngine | None = None

    def reland() -> None:
        if engine is None:
            raise RuntimeError("Import Deck engine is not active")
        engine.on_landing()

    def commit(value: str) -> None:
        field.set(value)
        sink.exit_text_mode()
        reland()

    def abandon() -> None:
        sink.exit_text_mode()
        reland()

    def edit_code() -> None:
        sink.enter_text_mode(
            TextSession("Deck code", field.value, announcer, commit, abandon)
        )

    def import_code() -> None:
        code = field.value.strip()
        try:
            deck = Deck.from_deckstring(code, card_db, allow_unknown=True)
        except (TypeError, ValueError):
            announcer.noop("Deck code not recognized")
            return
        name = unique_import_name(conn, deck.hero_class)
        save_deck(conn, name, deck.hero_class, deck.format, code)
        announcer.confirmation(f"{name} imported")
        nav.back(queued=True)

    # The field title stays constant: its contents remain reachable in Text mode.
    options = [
        MenuOption("deck_code", lambda: "Deck code, edit text", edit_code),
        MenuOption("import", lambda: "Import", import_code),
    ]

    def activate_current() -> None:
        if engine is None:
            raise RuntimeError("Import Deck engine is not active")
        if not engine.activate_current():
            announcer.noop("Nothing to do here")

    spec = SurfaceSpec(
        "Import Deck",
        WidgetType.VERTICAL_MENU,
        options=lambda: options,
        slot_fills={
            Slot.ENTER: Command(
                "import_deck.activate",
                "Enter: edit this field, or run this action",
                activate_current,
            )
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Import Deck requires a vertical-menu engine")
    engine = surface.engine
    return surface
