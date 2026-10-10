"""Deck Surface: one deck's record rows and actions (ADR-0017)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from stonereader.db import delete_deck
from stonereader.models.deck import DeckSummary
from stonereader.services._stats import LAST_GAMES, Record, compute_records
from stonereader.surfaces._deck_data import (
    CurrentDeck,
    CurrentGames,
    DeckData,
    GamePool,
    GamesFilter,
    GamesSelection,
    OfferSubjectSink,
    Versus,
    copy_deck_code,
    spoken_record,
    subject_name,
    subject_record,
)
from stonereader.spoken import class_name
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, MenuOption, SurfaceSpec, WidgetType


def build_deck_page(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    conn: sqlite3.Connection,
    data: DeckData,
    current_deck: CurrentDeck,
    current_games: CurrentGames,
    sink: OfferSubjectSink,
    copy_to_clipboard: Callable[[str], None],
) -> ActiveSurface:
    """Build the lazy singleton that shows the current subject's records."""
    engine: VerticalMenuEngine | None = None
    armed: ArmedAction | None = None

    def saved() -> DeckSummary | None:
        subject = current_deck.get()
        return None if isinstance(subject, GamePool) else subject

    def open_games(games: GamesFilter, record: Record) -> None:
        if not record.games:
            announcer.noop("No games yet")
            return
        current_games.set(GamesSelection(current_deck.get(), games))
        nav.drill_down("Games")

    def record_option(
        option_id: str,
        title: str,
        games: GamesFilter,
        record: Record,
    ) -> MenuOption:
        # Every record row opens exactly the games it counts.
        return MenuOption(
            option_id,
            lambda: title,
            lambda: open_games(games, record),
        )

    def options() -> list[MenuOption]:
        # Recomputed on every access (ADR-0012): no cached aggregates.
        record = subject_record(compute_records(conn), current_deck.get())
        summary = saved()
        rows: list[MenuOption] = []
        if summary is not None:
            cards = data.resolve(summary).total_cards()
            rows.append(
                MenuOption(
                    "cards",
                    lambda: f"Cards, {cards}",
                    lambda: nav.drill_down("Deck detail"),
                )
            )
        rows.append(record_option("games", _games_title(record), "all", record))
        if len(record.games) > LAST_GAMES:
            recent = record.recent()
            rows.append(
                record_option(
                    "last",
                    f"Last {LAST_GAMES} games, {spoken_record(recent)}",
                    "last",
                    recent,
                )
            )
        rows.extend(
            record_option(
                f"versus.{opponent_class}",
                f"Versus {class_name(opponent_class)}, {spoken_record(versus)}",
                Versus(opponent_class),
                versus,
            )
            for opponent_class, versus in record.by_opponent()
        )
        if summary is not None:
            rows.append(MenuOption("copy", lambda: "Copy deck code", copy_code))
            # Enter on Delete deck is handled by the Enter slot (see below).
            rows.append(MenuOption("delete", lambda: "Delete deck", None))
        return rows

    def finish_delete(summary: DeckSummary) -> None:
        if armed is not None:
            armed.disarm()
        delete_deck(conn, summary.deck_id)
        announcer.confirmation(f"{summary.name} deleted")
        nav.back(continues=True)

    def arm_delete(key: str) -> None:
        summary = saved()
        if summary is None:
            announcer.noop("Nothing to delete here")
            return
        if armed is None:
            raise RuntimeError("Deck armed action is not active")
        armed.press(
            f"{key}:{summary.deck_id}",
            f"Press {key} again to delete {summary.name}",
            lambda: finish_delete(summary),
        )

    def delete_now() -> None:
        summary = saved()
        if summary is None:
            announcer.noop("Nothing to delete here")
            return
        finish_delete(summary)

    def copy_code() -> None:
        summary = saved()
        if summary is None:
            announcer.noop("Nothing to copy here")
            return
        copy_deck_code(summary, announcer, copy_to_clipboard, sink)

    def activate_current() -> None:
        if engine is None:
            raise RuntimeError("Deck engine is not active")
        # Delete deck arms on Enter. Routing it past activate_current keeps the
        # menu's post-activation re-render from disarming it at once.
        if engine.current_option_id == "delete":
            arm_delete("Enter")
        elif not engine.activate_current():
            announcer.slot_noop(Slot.ENTER)

    spec = SurfaceSpec(
        "Deck",
        WidgetType.VERTICAL_MENU,
        context_label=lambda: subject_name(current_deck.get()),
        options=options,
        bindings=[
            Binding(
                Chord("delete"),
                Command(
                    "deck.delete",
                    "Delete: delete this deck, press twice",
                    lambda: arm_delete("Delete"),
                ),
            ),
            Binding(
                Chord("delete", shift=True),
                Command(
                    "deck.delete_now",
                    "Shift+Delete: delete this deck without asking",
                    delete_now,
                ),
            ),
            Binding(
                Chord("c"),
                Command("deck.copy", "C: copy this deck's code", copy_code),
            ),
        ],
        slot_fills={
            Slot.ENTER: Command(
                "deck.open",
                "Enter: open the selected option",
                activate_current,
            )
        },
        display_name=lambda: subject_name(current_deck.get()),
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Deck requires a vertical-menu engine")
    engine = surface.engine
    armed = ArmedAction(engine, announcer)

    def reopen() -> None:
        # A new subject is new content: start at its first option, unarmed.
        armed.disarm()
        engine.set_cursor(0)

    current_deck.subscribe(reopen)
    return surface


def _games_title(record: Record) -> str:
    if not record.games:
        return "Games, none yet"
    title = f"Games, {spoken_record(record)}"
    if record.win_rate_percent is not None:
        title += f", {record.win_rate_percent} percent"
    return title
