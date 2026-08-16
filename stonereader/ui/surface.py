"""Declarative Surface data interpreted by widget-type engines (ADR-0010)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from stonereader.ui.chords import Chord
from stonereader.ui.registry import Command, Slot


class WidgetType(Enum):
    """The exhaustive set of Surface navigation shapes."""

    VERTICAL_MENU = auto()
    HORIZONTAL_LIST = auto()


@dataclass(frozen=True)
class Binding:
    chord: Chord
    command: Command


@dataclass
class MenuOption:
    option_id: str
    title: Callable[[], str]
    on_enter: Callable[[], None] | None


@dataclass
class ZoneSpec:
    zone_id: str
    label: str
    items: Callable[[], Sequence[Any]]
    title: Callable[[Any], str]
    detail_lines: Callable[[Any], list[str]]
    jump_chord: Chord | None = None
    help_phrase: str = ""


@dataclass
class SurfaceSpec:
    name: str
    widget_type: WidgetType
    context_label: Callable[[], str] | None = None
    options: Callable[[], list[MenuOption]] | None = None
    zones: list[ZoneSpec] = field(default_factory=list)
    bindings: list[Binding] = field(default_factory=list)
    slot_fills: dict[Slot, Command] = field(default_factory=dict)
    slot_reverse_fills: dict[Slot, Command] = field(default_factory=dict)
    slot_noops: dict[Slot, str] = field(default_factory=dict)
    display_name: Callable[[], str] | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Surface name must not be empty")
        if self.widget_type is WidgetType.VERTICAL_MENU:
            if self.options is None:
                raise ValueError("A vertical menu requires an options provider")
            if self.zones:
                raise ValueError("A vertical menu cannot declare zones")
        elif self.widget_type is WidgetType.HORIZONTAL_LIST:
            if not self.zones:
                raise ValueError("A horizontal list requires at least one zone")
            if self.options is not None:
                raise ValueError("A horizontal list cannot declare options")

        zone_ids = [zone.zone_id for zone in self.zones]
        if len(set(zone_ids)) != len(zone_ids):
            raise ValueError("Zone ids must be unique")
        for zone in self.zones:
            if zone.jump_chord is not None and not zone.help_phrase:
                raise ValueError("A zone jump chord requires a help phrase")

        binding_chords = [binding.chord for binding in self.bindings]
        if len(set(binding_chords)) != len(binding_chords):
            raise ValueError("A chord may appear only once in Surface bindings")
        overlapping_slots = self.slot_fills.keys() & self.slot_noops.keys()
        if overlapping_slots:
            raise ValueError("A slot cannot be both filled and an announced no-op")
        orphaned_reverse_slots = self.slot_reverse_fills.keys() - self.slot_fills.keys()
        if orphaned_reverse_slots:
            raise ValueError("A reverse slot command requires a forward slot command")
