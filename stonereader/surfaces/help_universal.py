"""Read-only Universal keys Help Surface."""

from __future__ import annotations

from stonereader.surfaces._help_content import universal_entries
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType


def build_help_universal(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
) -> ActiveSurface:
    """Build the registry-generated read-only list of app-wide keys."""
    surface: ActiveSurface | None = None

    def options() -> list[MenuOption]:
        if surface is None:
            raise RuntimeError("Universal help Surface is not active")
        return [
            MenuOption(
                f"universal.{index}",
                lambda phrase=phrase: phrase,
                None,
            )
            for index, phrase in enumerate(universal_entries(surface.registry))
        ]

    surface = build_active_surface(
        SurfaceSpec("Universal keys", WidgetType.VERTICAL_MENU, options=options),
        announcer,
        universal_bindings,
        nav,
    )
    return surface
