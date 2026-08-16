from __future__ import annotations

from dataclasses import dataclass

from stonereader.surfaces.picker import PickerHolder, PickerRequest, build_picker
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType

from .conftest import Harness, make_harness


@dataclass
class PickerContext:
    holder: PickerHolder
    selected: dict[str, str]


def picker_harness() -> Harness[PickerContext]:
    holder = PickerHolder()
    selected = {"value": "b"}
    harness = make_harness(PickerContext(holder, selected))
    harness.nav.register(
        "Settings",
        lambda: build_active_surface(
            SurfaceSpec(
                "Settings",
                WidgetType.VERTICAL_MENU,
                options=lambda: [
                    MenuOption(
                        "choice",
                        lambda: f"Choice, {selected['value']}",
                        None,
                    )
                ],
            ),
            harness.announcer,
            [],
            harness.nav,
        ),
    )
    harness.nav.register(
        "Picker",
        lambda: build_picker(harness.announcer, [], harness.nav, holder),
    )
    harness.nav.jump("Settings")
    return harness


def test_cursor_starts_on_current_and_display_name_is_request_label() -> None:
    harness = picker_harness()
    harness.context.holder.set(PickerRequest("Choice", [("A", "a"), ("B", "b")], "b", lambda raw: harness.context.selected.update(value=raw)))
    harness.nav.drill_down("Picker")
    surface = harness.nav.peek("Picker")

    assert harness.menu("Picker").options_snapshot() == (["A", "B"], 1)
    assert surface.spec.display_name is not None
    assert surface.spec.display_name() == "Choice"


def test_picker_can_be_built_before_a_request_for_command_reference() -> None:
    holder = PickerHolder()
    harness = make_harness(holder)

    surface = build_picker(harness.announcer, [], harness.nav, holder)

    assert surface.spec.name == "Picker"


def test_select_pops_and_reannounces_parent_with_updated_value() -> None:
    harness = picker_harness()
    harness.context.holder.set(PickerRequest("Choice", [("A", "a"), ("B", "b")], "b", lambda raw: harness.context.selected.update(value=raw)))
    harness.nav.drill_down("Picker")
    harness.press(Chord("up"))
    harness.press(Chord("enter"))

    assert harness.context.selected["value"] == "a"
    assert harness.nav.stack == ("Home", "Settings")
    assert harness.speech.calls[-1] == ("Settings, Choice, a", True)


def test_back_changes_nothing() -> None:
    harness = picker_harness()
    harness.context.holder.set(PickerRequest("Choice", [("A", "a"), ("B", "b")], "b", lambda raw: harness.context.selected.update(value=raw)))
    harness.nav.drill_down("Picker")
    harness.press(Chord("up"))
    harness.press(Chord("escape"))

    assert harness.context.selected["value"] == "b"
    assert harness.nav.stack == ("Home", "Settings")
