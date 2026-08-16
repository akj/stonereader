"""Reusable solicited-choice Picker Surface (ADR-0011)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType


@dataclass(frozen=True)
class PickerRequest:
    label: str
    values: list[tuple[str, Any]]
    current_raw: Any
    on_select: Callable[[Any], None]


class PickerHolder:
    """Mutable request seam for the one cached Picker Surface."""

    def __init__(self) -> None:
        self._request: PickerRequest | None = None
        self._subscribers: list[Callable[[], None]] = []

    def set(self, request: PickerRequest) -> None:
        if not request.label or not request.values:
            raise ValueError("A Picker request requires a label and values")
        self._request = request
        for subscriber in tuple(self._subscribers):
            subscriber()

    def get(self) -> PickerRequest:
        if self._request is None:
            raise RuntimeError("Picker request has not been set")
        return self._request

    @property
    def is_set(self) -> bool:
        """Whether a caller has supplied a request for the cached Picker."""
        return self._request is not None

    def subscribe(self, on_change: Callable[[], None]) -> None:
        self._subscribers.append(on_change)


def build_picker(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    holder: PickerHolder,
) -> ActiveSurface:
    """Build the singleton whose contents come from ``holder``."""
    engine: VerticalMenuEngine | None = None

    def options() -> list[MenuOption]:
        request = holder.get()
        return [
            MenuOption(
                f"value_{index}",
                lambda spoken=spoken: spoken,
                lambda raw=raw: choose(raw),
            )
            for index, (spoken, raw) in enumerate(request.values)
        ]

    def choose(raw: Any) -> None:
        holder.get().on_select(raw)
        nav.back()

    def activate() -> None:
        if engine is None:
            raise RuntimeError("Picker engine is not active")
        if not engine.activate_current():
            announcer.noop("Nothing to do here")

    def align_cursor() -> None:
        if engine is None:
            return
        # Command reference may peek this lazy singleton before the User has
        # opened a setting. The later holder.set() notification performs the
        # ordinary alignment before Picker can be landed on.
        if not holder.is_set:
            return
        request = holder.get()
        index = next(
            (
                index
                for index, (_spoken, raw) in enumerate(request.values)
                if raw == request.current_raw
            ),
            0,
        )
        engine.set_cursor(index)
        engine.refresh()

    spec = SurfaceSpec(
        "Picker",
        WidgetType.VERTICAL_MENU,
        context_label=lambda: holder.get().label,
        options=options,
        slot_fills={
            Slot.ENTER: Command(
                "picker.choose",
                "Enter: choose this value",
                activate,
            )
        },
        display_name=lambda: holder.get().label,
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Picker requires a vertical-menu engine")
    engine = surface.engine
    holder.subscribe(align_cursor)
    align_cursor()
    return surface
