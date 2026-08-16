"""Contextual generated Help menu Surface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from stonereader.surfaces._help_content import screen_bindings, widget_type_sentence
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType
from stonereader.ui.text_mode import TextSession


HELP_SURFACE_NAMES = frozenset(
    {"Help menu", "Universal keys", "All commands", "Command reference"}
)


def open_help(
    announcer: Announcer,
    nav: NavigationController,
    origin: HelpOrigin,
    current: ActiveSurface,
) -> None:
    """Open contextual help, or announce the help-family recursion guard."""
    if nav.current_name in HELP_SURFACE_NAMES:
        announcer.noop("Already in help")
        return
    origin.set(current)
    nav.drill_down("Help menu")


class HelpTextSink(Protocol):
    """The Text-mode seam needed by help search."""

    def enter_text_mode(self, session: TextSession) -> None: ...

    def exit_text_mode(self) -> None: ...


class HelpOrigin:
    """Mutable origin seam for the one cached contextual Help Surface."""

    def __init__(self) -> None:
        self._surface: ActiveSurface | None = None
        self._subscribers: list[Callable[[], None]] = []

    def set(self, surface: ActiveSurface) -> None:
        changed = surface is not self._surface
        self._surface = surface
        if changed:
            for subscriber in tuple(self._subscribers):
                subscriber()

    def get(self) -> ActiveSurface:
        if self._surface is None:
            raise RuntimeError("Help origin has not been set")
        return self._surface

    def subscribe(self, on_change: Callable[[], None]) -> None:
        self._subscribers.append(on_change)


def build_help(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    origin: HelpOrigin,
    sink: HelpTextSink,
) -> ActiveSurface:
    """Build the searchable command-palette view of the current Surface."""
    engine: VerticalMenuEngine | None = None
    search = ""

    def origin_name() -> str:
        return origin.get().spec.name

    def execute(command: Command) -> None:
        nav.back()
        command.handler()

    def unfiltered_options() -> list[MenuOption]:
        surface = origin.get()
        options = [
            MenuOption(
                "widget_type",
                lambda surface=surface: widget_type_sentence(surface.spec),
                None,
            )
        ]
        options.extend(
            MenuOption(
                f"binding.{entry.command.id if entry.command else index}",
                lambda phrase=entry.phrase: phrase,
                (
                    None
                    if entry.command is None
                    else lambda command=entry.command: execute(command)
                ),
            )
            for index, entry in enumerate(screen_bindings(surface))
        )
        options.extend(
            [
                MenuOption(
                    "universal",
                    lambda: "Universal keys",
                    lambda: nav.drill_down("Universal keys"),
                ),
                MenuOption(
                    "all_commands",
                    lambda: "All commands",
                    lambda: nav.drill_down("All commands"),
                ),
            ]
        )
        return options

    def options() -> list[MenuOption]:
        if not search:
            return unfiltered_options()
        query = search.casefold()
        return [option for option in unfiltered_options() if query in option.title().casefold()]

    def reland() -> None:
        if engine is None:
            raise RuntimeError("Help engine is not active")
        engine.set_cursor(0)
        engine.refresh()
        engine.on_landing()

    def commit_search(value: str) -> None:
        nonlocal search
        search = value
        sink.exit_text_mode()
        reland()

    def abandon_search() -> None:
        sink.exit_text_mode()
        reland()

    def open_search() -> None:
        sink.enter_text_mode(
            TextSession("Search help", search, announcer, commit_search, abandon_search)
        )

    def origin_changed() -> None:
        nonlocal search
        # Help is origin-dependent, so a filter from another Surface would be
        # disorienting rather than useful persisted cursor state.
        search = ""
        if engine is not None:
            engine.set_cursor(0)
            engine.refresh()

    spec = SurfaceSpec(
        "Help menu",
        WidgetType.VERTICAL_MENU,
        context_label=lambda: f"{origin_name()} help",
        options=options,
        slot_fills={
            Slot.SEARCH: Command("help.search", "Ctrl+F: search help", open_search)
        },
        display_name=lambda: f"{origin_name()} help",
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Help requires a vertical-menu engine")
    engine = surface.engine
    origin.subscribe(origin_changed)
    return surface
