"""Assemble declarations, engines, and registries into active Surfaces."""

from __future__ import annotations

from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import (
    Command,
    CommandRegistry,
    Layer,
    Slot,
)
from stonereader.ui.surface import SurfaceSpec, WidgetType


def build_active_surface(
    spec: SurfaceSpec,
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
) -> ActiveSurface:
    """Build the engine and complete layered registry for one Surface."""
    if spec.widget_type is WidgetType.VERTICAL_MENU:
        engine: VerticalMenuEngine | HorizontalListEngine = VerticalMenuEngine(
            spec, announcer
        )
    else:
        engine = HorizontalListEngine(spec, announcer)

    registry = CommandRegistry(universal_bindings)
    nav.install_back(registry)

    for chord, command in engine.widget_type_bindings():
        registry.register(Layer.WIDGET_TYPE, chord, command)
    if isinstance(engine, HorizontalListEngine):
        for chord, command in engine.zone_bindings():
            registry.register(Layer.SURFACE, chord, command)
    for binding in spec.bindings:
        registry.register(Layer.SURFACE, binding.chord, binding.command)
    for slot, command in spec.slot_fills.items():
        registry.fill_slot(slot, command, spec.slot_reverse_fills.get(slot))
    for slot, phrase in spec.slot_noops.items():
        registry.fill_slot_noop(slot, phrase)

    if (
        isinstance(engine, VerticalMenuEngine)
        and Slot.ENTER not in spec.slot_fills
        and Slot.ENTER not in spec.slot_noops
    ):

        def activate_current() -> None:
            if not engine.activate_current():
                announcer.slot_noop(Slot.ENTER)

        registry.fill_slot(
            Slot.ENTER,
            Command(
                "menu.activate",
                "Enter: act on the current option",
                activate_current,
            ),
        )

    return ActiveSurface(spec, engine, registry)
