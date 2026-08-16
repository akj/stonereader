"""Declarative UI foundation and its enforced seams (ADR-0010)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord, chord_from_key
from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import (
    Command,
    CommandRegistry,
    DispatchResult,
    Layer,
    RegistrationError,
    Slot,
)
from stonereader.ui.surface import (
    Binding,
    MenuOption,
    SurfaceSpec,
    WidgetType,
    ZoneSpec,
)
from stonereader.ui.text_mode import TextSession

if TYPE_CHECKING:
    from stonereader.ui.sink import InputSink

__all__ = [
    "ActiveSurface",
    "Announcer",
    "Binding",
    "Chord",
    "Command",
    "CommandRegistry",
    "DispatchResult",
    "HorizontalListEngine",
    "InputSink",
    "Layer",
    "MenuOption",
    "NavigationController",
    "RegistrationError",
    "Slot",
    "SurfaceSpec",
    "TextSession",
    "VerticalMenuEngine",
    "WidgetType",
    "ZoneSpec",
    "chord_from_key",
    "build_active_surface",
]


def __getattr__(name: str) -> Any:
    """Keep headless foundation imports from eagerly importing wx."""
    if name == "InputSink":
        from stonereader.ui.sink import InputSink

        return InputSink
    raise AttributeError(name)
