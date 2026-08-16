from __future__ import annotations

import pytest

from stonereader.ui.chords import Chord
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, SurfaceSpec, WidgetType, ZoneSpec


def zone(
    zone_id: str = "cards",
    *,
    jump_chord: Chord | None = None,
    help_phrase: str = "",
) -> ZoneSpec:
    return ZoneSpec(
        zone_id,
        "Cards",
        lambda: [],
        str,
        lambda _item: [],
        jump_chord,
        help_phrase,
    )


def test_name_must_be_nonempty() -> None:
    with pytest.raises(ValueError):
        SurfaceSpec("", WidgetType.VERTICAL_MENU, options=lambda: [])


def test_vertical_menu_requires_options() -> None:
    with pytest.raises(ValueError):
        SurfaceSpec("Menu", WidgetType.VERTICAL_MENU)


def test_vertical_menu_refuses_zones() -> None:
    with pytest.raises(ValueError):
        SurfaceSpec("Menu", WidgetType.VERTICAL_MENU, options=lambda: [], zones=[zone()])


def test_horizontal_list_requires_zone() -> None:
    with pytest.raises(ValueError):
        SurfaceSpec("Cards", WidgetType.HORIZONTAL_LIST)


def test_horizontal_list_refuses_options() -> None:
    with pytest.raises(ValueError):
        SurfaceSpec(
            "Cards", WidgetType.HORIZONTAL_LIST, options=lambda: [], zones=[zone()]
        )


def test_zone_ids_must_be_unique() -> None:
    with pytest.raises(ValueError):
        SurfaceSpec("Cards", WidgetType.HORIZONTAL_LIST, zones=[zone(), zone()])


def test_surface_binding_chords_must_be_unique() -> None:
    first = Command("first", "First", lambda: None)
    second = Command("second", "Second", lambda: None)
    with pytest.raises(ValueError):
        SurfaceSpec(
            "Menu",
            WidgetType.VERTICAL_MENU,
            options=lambda: [],
            bindings=[Binding(Chord("a"), first), Binding(Chord("a"), second)],
        )


def test_slot_cannot_be_fill_and_noop() -> None:
    command = Command("search", "Search", lambda: None)
    with pytest.raises(ValueError):
        SurfaceSpec(
            "Menu",
            WidgetType.VERTICAL_MENU,
            options=lambda: [],
            slot_fills={Slot.SEARCH: command},
            slot_noops={Slot.SEARCH: "No search"},
        )


def test_zone_jump_requires_help_phrase() -> None:
    with pytest.raises(ValueError):
        SurfaceSpec(
            "Cards",
            WidgetType.HORIZONTAL_LIST,
            zones=[zone(jump_chord=Chord("c"))],
        )
