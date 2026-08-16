from __future__ import annotations

import pytest

from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine
from stonereader.ui.navigation import NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, MenuOption, SurfaceSpec, WidgetType, ZoneSpec

from tests.support import FakeSpeech


def navigation(announcer: Announcer) -> NavigationController:
    return NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda _surface: None,
    )


def horizontal_spec(*, bindings: list[Binding] | None = None) -> SurfaceSpec:
    return SurfaceSpec(
        "Cards",
        WidgetType.HORIZONTAL_LIST,
        zones=[
            ZoneSpec("first", "First", lambda: ["One", "Two"], str, lambda _item: []),
            ZoneSpec(
                "second",
                "Second",
                lambda: ["Other"],
                str,
                lambda _item: [],
                Chord("x"),
                "X: second zone",
            ),
        ],
        bindings=[] if bindings is None else bindings,
    )


@pytest.mark.parametrize(
    ("spec", "engine_type"),
    [
        (
            SurfaceSpec("Menu", WidgetType.VERTICAL_MENU, options=lambda: []),
            VerticalMenuEngine,
        ),
        (horizontal_spec(), HorizontalListEngine),
    ],
)
def test_selects_engine_for_widget_type(
    spec: SurfaceSpec,
    engine_type: type[VerticalMenuEngine] | type[HorizontalListEngine],
) -> None:
    announcer = Announcer(FakeSpeech())
    surface = build_active_surface(spec, announcer, [], navigation(announcer))
    assert isinstance(surface.engine, engine_type)


def test_installs_back() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    surface = build_active_surface(
        SurfaceSpec("Menu", WidgetType.VERTICAL_MENU, options=lambda: []),
        announcer,
        [],
        navigation(announcer),
    )

    assert surface.registry.dispatch(Chord("escape")).handled is True
    assert surface.registry.dispatch(Chord("backspace")).handled is True
    assert speech.calls == [
        ("Home — already at the top", True),
        ("Home — already at the top", True),
    ]


def test_registers_universal_widget_surface_and_zone_bindings() -> None:
    calls: list[str] = []
    speech = FakeSpeech()
    announcer = Announcer(speech)
    universal = [
        (
            Chord("f1"),
            Command("app.help", "F1: help", lambda: calls.append("help")),
        )
    ]
    spec = horizontal_spec(
        bindings=[
            Binding(
                Chord("z"),
                Command("surface.action", "Z: act", lambda: calls.append("surface")),
            )
        ]
    )
    surface = build_active_surface(spec, announcer, universal, navigation(announcer))

    assert surface.registry.dispatch(Chord("f1")).handled is True
    assert surface.registry.dispatch(Chord("right")).handled is True
    assert surface.registry.dispatch(Chord("x")).handled is True
    assert surface.registry.dispatch(Chord("z")).handled is True
    assert calls == ["help", "surface"]
    assert [chord for chord, _command in surface.registry.surface_bindings()] == [
        Chord("x"),
        Chord("z"),
    ]


def test_applies_slot_fills_and_announced_noops() -> None:
    calls: list[str] = []
    announcer = Announcer(FakeSpeech())
    spec = SurfaceSpec(
        "Menu",
        WidgetType.VERTICAL_MENU,
        options=lambda: [],
        slot_fills={
            Slot.ENTER: Command(
                "menu.custom",
                "Enter: custom",
                lambda: calls.append("enter"),
            )
        },
        slot_noops={Slot.SEARCH: "Search is unavailable"},
    )
    surface = build_active_surface(spec, announcer, [], navigation(announcer))

    assert surface.registry.dispatch(Chord("enter")).handled is True
    assert surface.registry.dispatch(Chord("f", ctrl=True)).announce == (
        "Search is unavailable"
    )
    assert calls == ["enter"]


def test_default_vertical_enter_runs_current_option() -> None:
    calls: list[str] = []
    speech = FakeSpeech()
    announcer = Announcer(speech)
    spec = SurfaceSpec(
        "Menu",
        WidgetType.VERTICAL_MENU,
        options=lambda: [MenuOption("act", lambda: "Act", lambda: calls.append("act"))],
    )
    surface = build_active_surface(spec, announcer, [], navigation(announcer))

    result = surface.registry.dispatch(Chord("enter"))
    assert result.handled is True
    assert result.announce is None
    assert calls == ["act"]
    assert speech.calls == []


def test_default_vertical_enter_announces_default_when_option_has_no_action() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    spec = SurfaceSpec(
        "Menu",
        WidgetType.VERTICAL_MENU,
        options=lambda: [MenuOption("read_only", lambda: "Read only", None)],
    )
    surface = build_active_surface(spec, announcer, [], navigation(announcer))

    result = surface.registry.dispatch(Chord("enter"))
    assert result.handled is True
    assert result.announce is None
    assert speech.calls == [("Nothing to do here", True)]
