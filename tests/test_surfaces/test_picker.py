from __future__ import annotations

from stonereader.surfaces.picker import PickerHolder, PickerRequest, build_picker
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import NavigationController
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType

from tests.test_ui.conftest import FakeSpeech


def harness():
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    holder = PickerHolder()
    selected = {"value": "b"}
    nav.register(
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
            announcer,
            [],
            nav,
        ),
    )
    nav.register("Picker", lambda: build_picker(announcer, [], nav, holder))
    nav.jump("Settings")
    return nav, sink, speech, holder, selected


def test_cursor_starts_on_current_and_display_name_is_request_label() -> None:
    nav, _sink, _speech, holder, selected = harness()
    holder.set(PickerRequest("Choice", [("A", "a"), ("B", "b")], "b", lambda raw: selected.update(value=raw)))
    nav.drill_down("Picker")
    surface = nav._surfaces["Picker"]

    assert surface.engine.options_snapshot() == (["A", "B"], 1)
    assert surface.spec.display_name is not None
    assert surface.spec.display_name() == "Choice"


def test_picker_can_be_built_before_a_request_for_command_reference() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda _surface: None,
    )
    holder = PickerHolder()

    surface = build_picker(announcer, [], nav, holder)

    assert surface.spec.name == "Picker"


def test_select_pops_and_reannounces_parent_with_updated_value() -> None:
    nav, sink, speech, holder, selected = harness()
    holder.set(PickerRequest("Choice", [("A", "a"), ("B", "b")], "b", lambda raw: selected.update(value=raw)))
    nav.drill_down("Picker")
    sink.handle_chord(Chord("up"))
    sink.handle_chord(Chord("enter"))

    assert selected["value"] == "a"
    assert nav.stack == ("Home", "Settings")
    assert speech.calls[-1] == ("Settings, Choice, a", True)


def test_back_changes_nothing() -> None:
    nav, sink, _speech, holder, selected = harness()
    holder.set(PickerRequest("Choice", [("A", "a"), ("B", "b")], "b", lambda raw: selected.update(value=raw)))
    nav.drill_down("Picker")
    sink.handle_chord(Chord("up"))
    sink.handle_chord(Chord("escape"))

    assert selected["value"] == "b"
    assert nav.stack == ("Home", "Settings")
