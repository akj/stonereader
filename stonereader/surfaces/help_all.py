"""All-commands Surface index."""

from __future__ import annotations

from stonereader.surfaces.help_reference import CommandReferenceHolder
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType


# Home options first, with each Surface's drill-down children immediately after
# their parent. Help-family Surfaces are the reference UI, not reference targets.
COMMAND_SURFACE_NAMES = (
    "Live Game",
    "Decks",
    "Deck detail",
    "Import Deck",
    "Statistics",
    "Cards",
    "Replays",
    "Replay Viewer",
    "Import Replays",
    "Settings",
    "Picker",
    "Global hotkeys",
)


def build_help_all(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    reference: CommandReferenceHolder,
) -> ActiveSurface:
    """Build the flat, Home-ordered index of application Surfaces."""

    def open_reference(name: str) -> None:
        reference.set(name)
        nav.drill_down("Command reference")

    def options() -> list[MenuOption]:
        return [
            MenuOption(
                f"surface.{name.casefold().replace(' ', '_')}",
                lambda name=name: name,
                lambda name=name: open_reference(name),
            )
            for name in COMMAND_SURFACE_NAMES
        ]

    return build_active_surface(
        SurfaceSpec("All commands", WidgetType.VERTICAL_MENU, options=options),
        announcer,
        universal_bindings,
        nav,
    )
