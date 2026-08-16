from __future__ import annotations

from dataclasses import dataclass

import pytest

from stonereader.surfaces._help_content import (
    screen_bindings,
    universal_entries,
    widget_type_sentence,
)
from stonereader.surfaces.help import HelpOrigin, build_help, open_help
from stonereader.surfaces.help_all import COMMAND_SURFACE_NAMES, build_help_all
from stonereader.surfaces.help_reference import (
    CommandReferenceHolder,
    build_help_reference,
)
from stonereader.surfaces.help_universal import build_help_universal
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import (
    Binding,
    MenuOption,
    SurfaceSpec,
    WidgetType,
    ZoneSpec,
)


class RecordingSpeech:
    def __init__(self, events: list[str]) -> None:
        self.calls: list[tuple[str, bool]] = []
        self._events = events

    def speak(self, text: str, interrupt: bool = True) -> None:
        self.calls.append((text, interrupt))
        self._events.append(f"speech:{text}")


@dataclass
class Harness:
    nav: NavigationController
    sink: _SinkCore
    speech: RecordingSpeech
    events: list[str]
    titles: list[str]
    origin: HelpOrigin
    reference: CommandReferenceHolder
    current: dict[str, ActiveSurface]
    deleted: list[str]
    live_builds: list[str]

    def press(self, chord: Chord) -> bool:
        return self.sink.handle_chord(chord)

    def type(self, text: str) -> None:
        for character in text:
            self.press(Chord(character))

    def menu(self, name: str) -> VerticalMenuEngine:
        engine = self.nav.peek(name).engine
        assert isinstance(engine, VerticalMenuEngine)
        return engine


def make_harness() -> Harness:
    events: list[str] = []
    titles: list[str] = []
    deleted: list[str] = []
    live_builds: list[str] = []
    speech = RecordingSpeech(events)
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    current: dict[str, ActiveSurface] = {}

    def activate(surface: ActiveSurface) -> None:
        current["surface"] = surface
        sink.set_active(surface.registry)
        events.append(f"activate:{surface.spec.name}")

    nav = NavigationController(
        lambda title: titles.append(title),
        announcer,
        lambda: events.append("stop"),
        activate,
    )
    origin = HelpOrigin()
    reference = CommandReferenceHolder()

    def invoke_help() -> None:
        open_help(announcer, nav, origin, current["surface"])

    universal = [
        (
            Chord("f1"),
            Command("app.help", "F1: help for this screen", invoke_help),
        )
    ]

    def cards_factory() -> ActiveSurface:
        engine: HorizontalListEngine | None = None
        armed: ArmedAction | None = None

        def arm_delete() -> None:
            if armed is None:
                raise RuntimeError("Cards delete action is not active")
            armed.press(
                "card",
                "Press Delete again to delete Card one",
                lambda: deleted.append("card"),
            )

        group = Command("cards.group", "Tab: jump to the next group", lambda: None)
        spec = SurfaceSpec(
            "Cards",
            WidgetType.HORIZONTAL_LIST,
            zones=[ZoneSpec("cards", "Cards", lambda: ["Card one"], str, lambda _item: [])],
            bindings=[
                Binding(
                    Chord("d"),
                    Command(
                        "cards.destination",
                        "D: jump to Remaining Deck",
                        lambda: events.append("handler:d"),
                    ),
                ),
                Binding(
                    Chord("delete"),
                    Command(
                        "cards.delete",
                        "Delete: delete this card, press twice",
                        arm_delete,
                    ),
                ),
                Binding(
                    Chord("delete", shift=True),
                    Command(
                        "cards.delete_now",
                        "Shift+Delete: delete this card without asking",
                        lambda: deleted.append("card"),
                    ),
                ),
            ],
            slot_fills={
                Slot.ENTER: Command("cards.open", "Enter: open this card", lambda: None),
                Slot.GROUP_JUMP: group,
                Slot.SEARCH: Command(
                    "cards.search",
                    "Ctrl+F: search for a card",
                    lambda: events.append("handler:search"),
                ),
            },
            slot_reverse_fills={Slot.GROUP_JUMP: group},
            slot_noops={Slot.LISTEN: "Game audio is not available"},
        )
        surface = build_active_surface(spec, announcer, universal, nav)
        assert isinstance(surface.engine, HorizontalListEngine)
        engine = surface.engine
        armed = ArmedAction(engine, announcer)
        return surface

    def settings_factory() -> ActiveSurface:
        return build_active_surface(
            SurfaceSpec(
                "Settings",
                WidgetType.VERTICAL_MENU,
                options=lambda: [MenuOption("setting", lambda: "A setting", None)],
            ),
            announcer,
            universal,
            nav,
        )

    def live_game_factory() -> ActiveSurface:
        live_builds.append("built")
        return build_active_surface(
            SurfaceSpec(
                "Live Game",
                WidgetType.HORIZONTAL_LIST,
                zones=[
                    ZoneSpec("hand", "Hand", lambda: ["Card"], str, lambda _item: [])
                ],
                bindings=[
                    Binding(
                        Chord("r"),
                        Command("game.remaining", "R: jump to Remaining Deck", lambda: None),
                    )
                ],
            ),
            announcer,
            universal,
            nav,
        )

    nav.register("Cards", cards_factory)
    nav.register("Settings", settings_factory)
    nav.register("Live Game", live_game_factory)
    nav.register(
        "Help menu",
        lambda: build_help(announcer, universal, nav, origin, sink),
    )
    nav.register(
        "Universal keys",
        lambda: build_help_universal(announcer, universal, nav),
    )
    nav.register(
        "All commands",
        lambda: build_help_all(announcer, universal, nav, reference),
    )
    nav.register(
        "Command reference",
        lambda: build_help_reference(announcer, universal, nav, reference),
    )
    nav.jump("Cards")
    return Harness(
        nav,
        sink,
        speech,
        events,
        titles,
        origin,
        reference,
        current,
        deleted,
        live_builds,
    )


def option_titles(harness: Harness, name: str) -> list[str]:
    return harness.menu(name).options_snapshot()[0]


def test_content_builders_use_exact_generated_wording_order_and_deduplication() -> None:
    harness = make_harness()
    cards = harness.nav.peek("Cards")
    settings = harness.nav.peek("Settings")

    assert widget_type_sentence(cards.spec) == (
        "Cards is a horizontal list: Left and Right move between items, "
        "Up and Down read details."
    )
    assert widget_type_sentence(settings.spec) == (
        "Settings is a menu: Up and Down move between options, "
        "Enter acts on the current one."
    )
    entries = screen_bindings(cards)
    assert [entry.phrase for entry in entries] == [
        "D: jump to Remaining Deck",
        "Delete: delete this card, press twice",
        "Shift+Delete: delete this card without asking",
        "Enter: open this card",
        "Tab: jump to the next group",
        "Ctrl+F: search for a card",
    ]
    assert entries[3].command is None
    assert entries[5].command is None


def test_help_entry_utterance_title_and_option_order() -> None:
    harness = make_harness()

    harness.press(Chord("f1"))

    sentence = (
        "Cards is a horizontal list: Left and Right move between items, "
        "Up and Down read details."
    )
    assert harness.speech.calls[-1] == (f"Cards help, {sentence}", True)
    assert harness.titles[-1] == "Cards help — StoneReader"
    assert option_titles(harness, "Help menu") == [
        sentence,
        "D: jump to Remaining Deck",
        "Delete: delete this card, press twice",
        "Shift+Delete: delete this card without asking",
        "Enter: open this card",
        "Tab: jump to the next group",
        "Ctrl+F: search for a card",
        "Universal keys",
        "All commands",
    ]


def test_enter_on_binding_pops_then_runs_after_origin_landing() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    harness.menu("Help menu").set_cursor(1)
    harness.events.clear()

    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home", "Cards")
    assert harness.events[-2:] == [
        "speech:Cards, Card one, 1 of 1",
        "handler:d",
    ]


def test_delete_from_help_only_arms_the_origin_action() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    harness.menu("Help menu").set_cursor(2)

    harness.press(Chord("enter"))

    assert harness.deleted == []
    assert harness.speech.calls[-1] == (
        "Press Delete again to delete Card one",
        True,
    )


def test_non_executable_help_options_announce_default_noop() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))

    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Nothing to do here", True)

    help_engine = harness.menu("Help menu")
    enter_index = option_titles(harness, "Help menu").index("Enter: open this card")
    help_engine.set_cursor(enter_index)
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Nothing to do here", True)
    assert harness.nav.current_name == "Help menu"


def test_universal_keys_are_exact_and_read_only() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    harness.nav.drill_down("Universal keys")

    assert option_titles(harness, "Universal keys") == universal_entries()
    assert harness.titles[-1] == "Universal keys — StoneReader"
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Nothing to do here", True)


def test_all_commands_reference_peeks_without_landing_and_is_read_only() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    harness.nav.drill_down("All commands")

    assert option_titles(harness, "All commands") == list(COMMAND_SURFACE_NAMES)
    assert harness.live_builds == []
    harness.events.clear()
    harness.press(Chord("enter"))

    assert harness.live_builds == ["built"]
    assert harness.nav.current_name == "Command reference"
    assert harness.titles[-1] == "Live Game commands — StoneReader"
    assert all(event != "activate:Live Game" for event in harness.events)
    assert option_titles(harness, "Command reference") == [
        "Live Game is a horizontal list: Left and Right move between items, "
        "Up and Down read details.",
        "R: jump to Remaining Deck",
    ]
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Only available on Live Game", True)


def test_help_search_filters_case_insensitively_clears_and_resets_for_new_origin() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))

    harness.press(Chord("f", ctrl=True))
    harness.type("DELETE")
    harness.press(Chord("enter"))
    assert option_titles(harness, "Help menu") == [
        "Delete: delete this card, press twice",
        "Shift+Delete: delete this card without asking",
    ]

    harness.press(Chord("f", ctrl=True))
    for _ in "DELETE":
        harness.press(Chord("backspace"))
    harness.press(Chord("enter"))
    assert len(option_titles(harness, "Help menu")) == 9

    harness.press(Chord("f", ctrl=True))
    harness.type("delete")
    harness.press(Chord("enter"))
    harness.press(Chord("escape"))
    harness.nav.jump("Settings")
    harness.press(Chord("f1"))
    assert option_titles(harness, "Help menu") == [
        "Settings is a menu: Up and Down move between options, "
        "Enter acts on the current one.",
        "Enter: act on the current option",
        "Universal keys",
        "All commands",
    ]


@pytest.mark.parametrize(
    "help_name",
    ["Help menu", "Universal keys", "All commands", "Command reference"],
)
def test_f1_inside_every_help_surface_is_announced_noop(help_name: str) -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    if help_name == "Command reference":
        harness.reference.set("Live Game")
    if help_name != "Help menu":
        harness.nav.drill_down(help_name)
    stack = harness.nav.stack

    harness.press(Chord("f1"))

    assert harness.nav.stack == stack
    assert harness.speech.calls[-1] == ("Already in help", True)
