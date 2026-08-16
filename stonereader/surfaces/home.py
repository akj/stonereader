"""Home Surface declaration and target-independent actions."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, MenuOption, SurfaceSpec, WidgetType


_OPTIONS = (
    ("Live Game", "l"),
    ("Decks", "d"),
    ("Cards", "c"),
    ("Replays", "r"),
    ("Settings", "s"),
)


def build_home(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    targets: Mapping[str, Callable[[], None]],
) -> ActiveSurface:
    """Build Home without coupling its options to navigation targets."""
    engine: VerticalMenuEngine | None = None

    def open_selected() -> None:
        if engine is None:
            raise RuntimeError("Home engine is not active")
        engine.activate_current()

    options = [
        MenuOption(
            option_id=name.lower().replace(" ", "_"),
            title=lambda name=name: name,
            on_enter=targets[name],
        )
        for name, _letter in _OPTIONS
    ]
    bindings = [
        Binding(
            Chord(letter),
            Command(
                f"home.{name.lower().replace(' ', '_')}",
                f"{letter.upper()}: go to {name}",
                targets[name],
            ),
        )
        for name, letter in _OPTIONS
        if name != "Live Game"
    ]
    spec = SurfaceSpec(
        "Home",
        WidgetType.VERTICAL_MENU,
        options=lambda: options,
        bindings=bindings,
        slot_fills={
            Slot.ENTER: Command(
                "home.open",
                "Enter: open the selected screen",
                open_selected,
            ),
            Slot.LISTEN: Command(
                "home.live_game",
                "L: go to Live Game",
                targets["Live Game"],
            ),
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Home requires a vertical-menu engine")
    engine = surface.engine
    return surface
