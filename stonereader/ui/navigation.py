"""Route-invariant Surface stack ownership (ADR-0006, ADR-0010)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from stonereader.ui.announcer import Announcer
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.surface import SurfaceSpec


class SurfaceEngine(Protocol):
    """The engine behavior navigation needs at the landing seam."""

    def on_landing(self, continues: bool = False) -> None: ...


@dataclass
class ActiveSurface:
    """The declaration, engine, and registry activated as one Surface."""

    spec: SurfaceSpec
    engine: SurfaceEngine
    registry: CommandRegistry


class NavigationController:
    """Own Screen jumps, Drill-downs, back, and every landing effect."""

    def __init__(
        self,
        set_title: Callable[[str], None],
        set_heading: Callable[[str], None],
        announcer: Announcer,
        stop_audio: Callable[[], None],
        activate: Callable[[ActiveSurface], None],
        home: str = "Home",
    ) -> None:
        self._set_title = set_title
        self._set_heading = set_heading
        self._announcer = announcer
        self._stop_audio = stop_audio
        self._activate = activate
        self._home = home
        self._stack = [home]
        self._factories: dict[str, Callable[[], ActiveSurface]] = {}
        self._surfaces: dict[str, ActiveSurface] = {}

    @property
    def stack(self) -> tuple[str, ...]:
        return tuple(self._stack)

    @property
    def current_name(self) -> str:
        """Return the registered name of the currently landed Surface."""
        return self._stack[-1]

    def register(self, name: str, factory: Callable[[], ActiveSurface]) -> None:
        if not name:
            raise ValueError("Registered Surface name must not be empty")
        if name in self._factories:
            raise ValueError(f"Surface is already registered: {name}")
        self._factories[name] = factory

    def peek(self, name: str) -> ActiveSurface:
        """Get or create a registered Surface without landing on it."""
        return self._get_surface(name)

    def all_surfaces(self) -> tuple[tuple[str, ActiveSurface], ...]:
        """Get or create every registered Surface without landing on one."""
        return tuple(
            (name, self._get_surface(name)) for name in tuple(self._factories)
        )

    def jump(
        self,
        name: str,
        then: Callable[[ActiveSurface], None] | None = None,
    ) -> None:
        """Screen jump to a target, resetting the stack through Home."""
        surface = self._get_surface(name)
        self._stack = [self._home] if name == self._home else [self._home, name]
        self._land(surface)
        if then is not None:
            # ADR-0006: compound hotkeys equal landing and then pressing a zone key.
            then(surface)

    def drill_down(self, name: str) -> None:
        """Push a new Surface and land on it."""
        if name in self._stack:
            raise ValueError(f"Surface is already on the stack: {name}")
        surface = self._get_surface(name)
        self._stack.append(name)
        self._land(surface)

    def jump_path(self, names: list[str]) -> None:
        """Reset to an exact Home-rooted path and land on its final Surface."""
        if not names or names[0] != self._home:
            raise ValueError(f"Navigation path must start with {self._home}")
        if len(set(names)) != len(names):
            raise ValueError("Navigation path cannot contain duplicate Surfaces")
        # Home is the controller's structural root and need not be instantiated
        # merely to reset a path; every reachable non-root Surface must exist.
        unknown = [name for name in names[1:] if name not in self._factories]
        if unknown:
            raise KeyError(f"Unknown Surface: {unknown[0]}")
        surface = self._get_surface(names[-1])
        self._stack = list(names)
        self._land(surface)

    def back(self, continues: bool = False) -> None:
        """Pop one Drill-down, or announce the root no-op.

        `continues` marks the revealed Surface's landing utterance as a Lane-1
        continuation: it follows a confirmation already spoken instead of
        cutting it (ADR-0007).
        """
        if len(self._stack) == 1:
            self._announcer.already_home(self._home)
            return
        self._stack.pop()
        self._land(self._get_surface(self._stack[-1]), continues=continues)

    def install_back(self, registry: CommandRegistry) -> None:
        """Centrally install Escape and Backspace on an activated registry."""
        registry.register_back(self.back)

    def _get_surface(self, name: str) -> ActiveSurface:
        if name in self._surfaces:
            return self._surfaces[name]
        try:
            factory = self._factories[name]
        except KeyError as error:
            raise KeyError(f"Unknown Surface: {name}") from error
        surface = factory()
        self._surfaces[name] = surface
        return surface

    def _display_name(self, name: str) -> str:
        spec = self._get_surface(name).spec
        return spec.display_name() if spec.display_name is not None else name

    def _land(self, surface: ActiveSurface, *, continues: bool = False) -> None:
        # A single landing path makes route invariance structural (ADR-0010).
        self._stop_audio()
        # ADR-0017: the heading leaves out the Home root every deeper path shares.
        path = [self._display_name(name) for name in self._stack[1:] or self._stack]
        self._set_title(f"{path[-1]} — StoneReader")
        self._set_heading(" › ".join(_crumbs(path)))
        self._activate(surface)
        surface.engine.on_landing(continues=continues)


def _crumbs(path: list[str]) -> list[str]:
    """Drop the parent's name a heading crumb repeats: "Odd Hunter cards" is "Cards"."""
    crumbs = path[:1]
    for parent, name in zip(path, path[1:]):
        rest = ""
        for joiner in (" ", ", "):
            if name.startswith(parent + joiner):
                rest = name[len(parent + joiner) :]
        crumbs.append(rest[:1].upper() + rest[1:] if rest else name)
    return crumbs
