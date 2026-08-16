from __future__ import annotations

import pytest

from stonereader.ui.announcer import Announcer
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.surface import SurfaceSpec, WidgetType

from .conftest import FakeSpeech


class FakeEngine:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events
        self.cursor = 0

    def on_landing(self, queued: bool = False) -> None:
        self.events.append(f"landing:{self.name}:{self.cursor}")


def active(name: str, events: list[str]) -> ActiveSurface:
    spec = SurfaceSpec(name, WidgetType.VERTICAL_MENU, options=lambda: [])
    return ActiveSurface(spec, FakeEngine(name, events), CommandRegistry())


def controller(
    events: list[str], speech: FakeSpeech
) -> NavigationController:
    return NavigationController(
        lambda title: events.append(f"title:{title}"),
        Announcer(speech),
        lambda: events.append("stop"),
        lambda surface: events.append(f"activate:{surface.spec.name}"),
    )


def register_factories(
    navigation: NavigationController,
    events: list[str],
    counts: dict[str, int] | None = None,
) -> None:
    for name in ["Home", "Cards", "Detail"]:
        def factory(surface_name: str = name) -> ActiveSurface:
            if counts is not None:
                counts[surface_name] = counts.get(surface_name, 0) + 1
            return active(surface_name, events)

        navigation.register(name, factory)


def test_jump_drill_and_back_stack_semantics() -> None:
    events: list[str] = []
    navigation = controller(events, FakeSpeech())
    register_factories(navigation, events)

    navigation.jump("Cards")
    assert navigation.stack == ("Home", "Cards")
    navigation.drill_down("Detail")
    assert navigation.stack == ("Home", "Cards", "Detail")
    navigation.back()
    assert navigation.stack == ("Home", "Cards")
    navigation.jump("Home")
    assert navigation.stack == ("Home",)


def test_every_landing_route_uses_same_ordered_effects() -> None:
    events: list[str] = []
    navigation = controller(events, FakeSpeech())
    register_factories(navigation, events)

    navigation.jump("Cards")
    navigation.drill_down("Detail")
    navigation.back()

    assert events == [
        "stop",
        "title:Cards — StoneReader",
        "activate:Cards",
        "landing:Cards:0",
        "stop",
        "title:Detail — StoneReader",
        "activate:Detail",
        "landing:Detail:0",
        "stop",
        "title:Cards — StoneReader",
        "activate:Cards",
        "landing:Cards:0",
    ]


def test_back_at_root_is_exact_announced_noop() -> None:
    speech = FakeSpeech()
    navigation = controller([], speech)
    navigation.back()
    assert speech.calls == [("Home — already at the top", True)]


def test_surfaces_are_lazy_singletons_and_found_as_left() -> None:
    events: list[str] = []
    counts: dict[str, int] = {}
    navigation = controller(events, FakeSpeech())
    register_factories(navigation, events, counts)
    navigation.jump("Cards")
    cards = navigation._surfaces["Cards"]
    assert isinstance(cards.engine, FakeEngine)
    cards.engine.cursor = 4
    navigation.jump("Home")
    navigation.jump("Cards")
    assert counts["Cards"] == 1
    assert events[-1] == "landing:Cards:4"


def test_jump_then_runs_after_plain_landing() -> None:
    events: list[str] = []
    navigation = controller(events, FakeSpeech())
    register_factories(navigation, events)
    navigation.jump("Cards", then=lambda _surface: events.append("then"))
    assert events[-2:] == ["landing:Cards:0", "then"]


def test_drill_to_existing_stack_name_raises() -> None:
    navigation = controller([], FakeSpeech())
    register_factories(navigation, [])
    navigation.jump("Cards")
    with pytest.raises(ValueError):
        navigation.drill_down("Home")


def test_factory_is_not_called_until_first_visit() -> None:
    navigation = controller([], FakeSpeech())
    calls: list[str] = []

    def factory() -> ActiveSurface:
        calls.append("made")
        return active("Cards", [])

    navigation.register("Cards", factory)
    assert calls == []
    navigation.jump("Cards")
    assert calls == ["made"]
