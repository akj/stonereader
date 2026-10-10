from __future__ import annotations

from dataclasses import dataclass

import pytest

from stonereader.models.game_state import GameState, Hero
from stonereader.models.replay import ReplayState
from stonereader.surfaces._help_content import (
    screen_bindings,
    widget_type_sentence,
)
from stonereader.surfaces.help import HelpOrigin, build_help, open_help
from stonereader.surfaces.help_all import COMMAND_SURFACE_NAMES, build_help_all
from stonereader.surfaces.help_reference import (
    CommandReferenceHolder,
    build_help_reference,
)
from stonereader.surfaces.help_universal import build_help_universal
from stonereader.surfaces.home import build_home
from stonereader.surfaces.live_game import CurrentGame
from stonereader.surfaces.replay_viewer import CurrentReplay, build_replay_viewer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import (
    Binding,
    MenuOption,
    SurfaceSpec,
    WidgetType,
    ZoneSpec,
)

from .conftest import Harness, make_harness as make_base_harness


CARDS_SENTENCE = (
    "Horizontal list: Left and Right move between items, "
    "Up and Down read details."
)
REPLAY_VIEWER_BINDINGS = [
    "Horizontal list: Left and Right move between items, "
    "Up and Down read details.",
    "Enter: go to the event where this card was played or drawn",
    "Page Up: go to the previous turn",
    "Page Down: go to the next turn",
    "F5: go to the previous event",
    "F6: go to the next event",
    "B: your minions",
    "G: opponent minions",
    "C: your hand",
    "Shift+C: opponent hand",
    "S: your secrets",
    "Shift+S: opponent secrets",
    "V: your hero",
    "F: opponent hero",
    "W: your weapon",
    "Shift+W: opponent weapon",
    "D: jump to Remaining Deck",
    "P: cards you played",
    "Shift+P: cards your opponent played",
    "N: cards you drew",
    "Shift+N: cards your opponent drew",
    "Y: the game's events",
    "A: how much mana you have",
    "Shift+A: how much mana your opponent has",
    "Shift+D: how many cards are in your opponent's deck",
    "R: your hero power",
    "Shift+R: your opponent's hero power",
    "1 to 9: jump to that position in the list",
    "0: jump to the tenth item",
]


@dataclass
class HelpContext:
    origin: HelpOrigin
    reference: CommandReferenceHolder
    deleted: list[str]
    live_builds: list[str]


def make_harness() -> Harness[HelpContext]:
    deleted: list[str] = []
    live_builds: list[str] = []
    origin = HelpOrigin()
    reference = CommandReferenceHolder()
    harness = make_base_harness(
        HelpContext(origin, reference, deleted, live_builds)
    )

    def invoke_help() -> None:
        open_help(
            harness.announcer,
            harness.nav,
            origin,
            harness.active_surface,
        )

    quit_command = Command(
        "app.quit", "Ctrl+Q or Alt+F4: quit StoneReader", lambda: None
    )
    universal = [
        (
            Chord("f1"),
            Command("app.help", "F1: help for this screen", invoke_help),
        ),
        (Chord("q", ctrl=True), quit_command),
        (Chord("f4", alt=True), quit_command),
    ]

    def home_factory() -> ActiveSurface:
        targets = {
            name: lambda name=name: harness.nav.jump(name)
            for name in ("Live Game", "Decks", "Cards", "Replays", "Settings")
        }
        return build_home(
            harness.announcer, universal, harness.nav, targets, CurrentGame()
        )

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
                        lambda: harness.events.append("handler:d"),
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
                    lambda: harness.events.append("handler:search"),
                ),
            },
            slot_reverse_fills={Slot.GROUP_JUMP: group},
            slot_noops={Slot.LISTEN: "Game audio is not available"},
        )
        surface = build_active_surface(
            spec, harness.announcer, universal, harness.nav
        )
        assert isinstance(surface.engine, HorizontalListEngine)
        engine = surface.engine
        armed = ArmedAction(engine, harness.announcer)
        return surface

    def settings_factory() -> ActiveSurface:
        return build_active_surface(
            SurfaceSpec(
                "Settings",
                WidgetType.VERTICAL_MENU,
                options=lambda: [MenuOption("setting", lambda: "A setting", None)],
            ),
            harness.announcer,
            universal,
            harness.nav,
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
            harness.announcer,
            universal,
            harness.nav,
        )

    def replay_viewer_factory() -> ActiveSurface:
        hero = Hero("hero", "Jaina", 30, 0, "", "MAGE")
        replay = CurrentReplay()
        replay.set(ReplayState((GameState(1, 1, (), (), (), (), hero, hero),), 1))
        return build_replay_viewer(
            harness.announcer,
            universal,
            harness.nav,
            replay,
            replay_autoplay=lambda: False,
        )

    harness.nav.register("Home", home_factory)
    harness.nav.register("Cards", cards_factory)
    harness.nav.register("Settings", settings_factory)
    harness.nav.register("Live Game", live_game_factory)
    harness.nav.register("Replay Viewer", replay_viewer_factory)
    harness.nav.register(
        "Help menu",
        lambda: build_help(
            harness.announcer,
            universal,
            harness.nav,
            origin,
            harness.sink,
        ),
    )
    harness.nav.register(
        "Universal keys",
        lambda: build_help_universal(
            harness.announcer, universal, harness.nav
        ),
    )
    harness.nav.register(
        "All commands",
        lambda: build_help_all(
            harness.announcer, universal, harness.nav, reference
        ),
    )
    harness.nav.register(
        "Command reference",
        lambda: build_help_reference(
            harness.announcer, universal, harness.nav, reference
        ),
    )
    harness.nav.jump("Cards")
    return harness


def option_titles(harness: Harness[HelpContext], name: str) -> list[str]:
    return harness.menu(name).options_snapshot()[0]


def move_to(harness: Harness[HelpContext], title: str) -> None:
    """Press Down on the current menu until ``title`` is the current option."""
    titles, cursor = harness.vertical.options_snapshot()
    steps = titles.index(title) - cursor
    assert steps > 0
    for _ in range(steps):
        harness.press(Chord("down"))
    assert harness.speech.calls[-1] == (title, True)


def test_content_builders_use_exact_generated_wording_order_and_deduplication() -> None:
    harness = make_harness()
    cards = harness.nav.peek("Cards")
    settings = harness.nav.peek("Settings")

    assert widget_type_sentence(cards.spec) == CARDS_SENTENCE
    assert widget_type_sentence(settings.spec) == (
        "Menu: Up and Down move between options, "
        "Enter acts on the current one."
    )
    entries = screen_bindings(cards)
    assert [entry.phrase for entry in entries] == [
        "Enter: open this card",
        "D: jump to Remaining Deck",
        "Delete: delete this card, press twice",
        "Shift+Delete: delete this card without asking",
        "Tab: jump to the next group",
        "Ctrl+F: search for a card",
    ]
    assert [entry.command is None for entry in entries] == [
        True,
        False,
        False,
        False,
        False,
        True,
    ]
    assert not any(entry.shared for entry in entries)


def test_help_entry_utterance_title_and_option_order() -> None:
    harness = make_harness()

    harness.press(Chord("f1"))

    assert harness.speech.calls[-1] == (f"Cards help, {CARDS_SENTENCE}", True)
    assert harness.titles[-1] == "Cards help — StoneReader"
    assert option_titles(harness, "Help menu") == [
        CARDS_SENTENCE,
        "Enter: open this card",
        "D: jump to Remaining Deck",
        "Delete: delete this card, press twice",
        "Shift+Delete: delete this card without asking",
        "Tab: jump to the next group",
        "Ctrl+F: search for a card",
        "Universal keys",
        "All commands",
    ]


def test_home_help_reads_enter_then_letters_in_option_order() -> None:
    harness = make_harness()
    harness.nav.jump("Home")

    harness.press(Chord("f1"))

    sentence = (
        "Menu: Up and Down move between options, "
        "Enter acts on the current one."
    )
    assert harness.speech.calls[-1] == (f"Home help, {sentence}", True)
    assert option_titles(harness, "Help menu") == [
        sentence,
        "Enter: open the selected screen",
        "L: go to Live Game",
        "D: go to Decks",
        "C: go to Cards",
        "R: go to Replays",
        "S: go to Settings",
        "Universal keys",
        "All commands",
    ]

    move_to(harness, "L: go to Live Game")
    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Live Game")


def test_replay_viewer_help_leads_with_turns_and_shares_one_digit_option() -> None:
    harness = make_harness()
    harness.nav.jump("Replay Viewer")

    harness.press(Chord("f1"))

    assert harness.speech.calls[-1] == (
        f"Replay Viewer help, {REPLAY_VIEWER_BINDINGS[0]}",
        True,
    )
    assert option_titles(harness, "Help menu") == [
        *REPLAY_VIEWER_BINDINGS,
        "Universal keys",
        "All commands",
    ]

    move_to(harness, "1 to 9: jump to that position in the list")
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Press one of these keys to use this", True)
    assert harness.nav.current_name == "Help menu"

    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Replay Viewer")


def test_all_commands_sections_share_one_option_per_phrase() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    move_to(harness, "All commands")
    harness.press(Chord("enter"))

    move_to(harness, "Replay Viewer")
    harness.press(Chord("enter"))

    assert option_titles(harness, "Command reference") == REPLAY_VIEWER_BINDINGS
    move_to(harness, "1 to 9: jump to that position in the list")
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Only available on Replay Viewer", True)


def test_f1_always_opens_fresh_on_the_widget_type_sentence() -> None:
    harness = make_harness()
    harness.nav.jump("Replay Viewer")
    harness.press(Chord("f1"))
    move_to(harness, "V: your hero")
    harness.press(Chord("escape"))

    harness.press(Chord("f1"))

    assert harness.speech.calls[-1] == (
        f"Replay Viewer help, {REPLAY_VIEWER_BINDINGS[0]}",
        True,
    )

    harness.press(Chord("f", ctrl=True))
    harness.type("hero")
    harness.press(Chord("enter"))
    harness.press(Chord("escape"))

    harness.press(Chord("f1"))

    assert harness.speech.calls[-1] == (
        f"Replay Viewer help, {REPLAY_VIEWER_BINDINGS[0]}",
        True,
    )
    assert len(option_titles(harness, "Help menu")) == len(REPLAY_VIEWER_BINDINGS) + 2


def test_back_from_nested_help_menus_finds_help_as_left() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    move_to(harness, "Universal keys")
    harness.press(Chord("enter"))

    harness.press(Chord("escape"))

    assert harness.speech.calls[-1] == ("Cards help, Universal keys", True)

    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    harness.press(Chord("escape"))

    assert harness.speech.calls[-1] == ("Cards help, All commands", True)


def test_enter_on_binding_pops_then_runs_after_origin_landing() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    move_to(harness, "D: jump to Remaining Deck")
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
    move_to(harness, "Delete: delete this card, press twice")

    harness.press(Chord("enter"))

    assert harness.context.deleted == []
    assert harness.speech.calls[-1] == (
        "Press Delete again to delete Card one",
        True,
    )


def test_non_executable_help_options_announce_default_noop() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))

    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Nothing to do here", True)

    move_to(harness, "Enter: open this card")
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Nothing to do here", True)
    assert harness.nav.current_name == "Help menu"


def test_universal_keys_are_exact_and_read_only() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    harness.nav.drill_down("Universal keys")

    assert option_titles(harness, "Universal keys") == [
        "Enter: act on the current item",
        "Escape or Backspace: go back",
        "Home and End: jump to the ends",
        "Page Up and Page Down: pages or turns where the screen has them",
        "Tab and Shift+Tab: jump between groups where the screen has them",
        "Ctrl+F: search where the screen has it",
        "F1: help for this screen",
        "L: listen to a card's sounds",
        "Ctrl: stop game audio",
        "Ctrl+Q or Alt+F4: quit StoneReader",
    ]
    assert harness.titles[-1] == "Universal keys — StoneReader"
    harness.press(Chord("enter"))
    assert harness.speech.calls[-1] == ("Nothing to do here", True)


def test_all_commands_reference_peeks_without_landing_and_is_read_only() -> None:
    harness = make_harness()
    harness.press(Chord("f1"))
    harness.nav.drill_down("All commands")

    assert option_titles(harness, "All commands") == [
        "Home",
        "Live Game",
        "Decks",
        "Deck",
        "Deck detail",
        "Games",
        "Import Deck",
        "Cards",
        "Card Browser",
        "Sounds menu",
        "Replays",
        "Replay Viewer",
        "Import Replays",
        "Settings",
        "Global hotkeys",
    ]
    assert list(COMMAND_SURFACE_NAMES) == option_titles(harness, "All commands")
    assert harness.context.live_builds == []
    harness.events.clear()
    harness.menu("All commands").set_cursor(1)
    harness.press(Chord("enter"))

    assert harness.context.live_builds == ["built"]
    assert harness.nav.current_name == "Command reference"
    assert harness.titles[-1] == "Live Game commands — StoneReader"
    assert all(event != "activate:Live Game" for event in harness.events)
    assert option_titles(harness, "Command reference") == [
        "Horizontal list: Left and Right move between items, "
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
        "Menu: Up and Down move between options, "
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
        harness.context.reference.set("Live Game")
    if help_name != "Help menu":
        harness.nav.drill_down(help_name)
    stack = harness.nav.stack

    harness.press(Chord("f1"))

    assert harness.nav.stack == stack
    assert harness.speech.calls[-1] == ("Already in help", True)
