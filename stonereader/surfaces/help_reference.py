"""Read-only per-Surface command-reference Surface."""

from __future__ import annotations

from collections.abc import Callable

from stonereader.surfaces._help_content import screen_bindings, widget_type_sentence
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType


class CommandReferenceHolder:
    """Mutable target seam for the one cached command-reference Surface."""

    def __init__(self) -> None:
        self._name: str | None = None
        self._subscribers: list[Callable[[], None]] = []

    def set(self, name: str) -> None:
        if not name:
            raise ValueError("A command-reference target requires a name")
        changed = name != self._name
        self._name = name
        if changed:
            for subscriber in tuple(self._subscribers):
                subscriber()

    def get(self) -> str:
        if self._name is None:
            raise RuntimeError("Command-reference target has not been set")
        return self._name

    def subscribe(self, on_change: Callable[[], None]) -> None:
        self._subscribers.append(on_change)


def build_help_reference(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    reference: CommandReferenceHolder,
) -> ActiveSurface:
    """Build the generated read-only reference for the selected Surface."""
    engine: VerticalMenuEngine | None = None

    def unavailable() -> None:
        announcer.noop(f"Only available on {reference.get()}")

    def options() -> list[MenuOption]:
        surface = nav.peek(reference.get())
        phrases = [
            widget_type_sentence(surface.spec),
            *(entry.phrase for entry in screen_bindings(surface)),
        ]
        return [
            MenuOption(
                f"reference.{index}",
                lambda phrase=phrase: phrase,
                unavailable,
            )
            for index, phrase in enumerate(phrases)
        ]

    def target_changed() -> None:
        if engine is not None:
            engine.set_cursor(0)
            engine.refresh()

    spec = SurfaceSpec(
        "Command reference",
        WidgetType.VERTICAL_MENU,
        context_label=lambda: f"{reference.get()} commands",
        options=options,
        display_name=lambda: f"{reference.get()} commands",
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Command reference requires a vertical-menu engine")
    engine = surface.engine
    reference.subscribe(target_changed)
    return surface
