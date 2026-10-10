"""Home Surface declaration and target-independent actions."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from stonereader.models.game_state import GameState
from stonereader.surfaces._replay_turns import turn_number
from stonereader.spoken import class_name
from stonereader.surfaces.live_game import CurrentGame
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
    current_game: CurrentGame,
) -> ActiveSurface:
    """Build Home without coupling its options to navigation targets."""
    engine: VerticalMenuEngine | None = None

    def open_selected() -> None:
        if engine is None:
            raise RuntimeError("Home engine is not active")
        engine.activate_current()

    def title(name: str) -> str:
        if name == "Live Game":
            return _live_game_title(current_game.get())
        return name

    options = [
        MenuOption(
            option_id=name.lower().replace(" ", "_"),
            title=lambda name=name: title(name),
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
        help_first=[Chord("l")],
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
    current_game.subscribe(engine.refresh)
    return surface


def _live_game_title(state: GameState | None) -> str:
    """Say what Live Game holds right now (ADR-0017)."""
    if state is None:
        return "Live Game, waiting for a game"
    opponent = class_name(state.opponent_hero.hero_class)
    return f"Live Game, turn {turn_number(state)} versus {opponent}"
