from __future__ import annotations

from collections.abc import Callable

from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType, ZoneSpec

from .conftest import FakeSpeech


def run_binding(
    bindings: list[tuple[Chord, object]],
    chord: Chord,
) -> None:
    command = dict(bindings)[chord]
    handler = getattr(command, "handler")
    assert isinstance(handler, Callable)
    handler()


def menu_engine(
    options: list[MenuOption], speech: FakeSpeech
) -> VerticalMenuEngine:
    spec = SurfaceSpec("Home", WidgetType.VERTICAL_MENU, options=lambda: options)
    return VerticalMenuEngine(spec, Announcer(speech))


def test_vertical_entry_movement_boundary_home_end_and_reread() -> None:
    speech = FakeSpeech()
    engine = menu_engine(
        [
            MenuOption("live", lambda: "Live Game", None),
            MenuOption("cards", lambda: "Cards", None),
            MenuOption("settings", lambda: "Settings", None),
        ],
        speech,
    )
    bindings = engine.widget_type_bindings()

    engine.on_landing()
    run_binding(bindings, Chord("up"))
    run_binding(bindings, Chord("down"))
    run_binding(bindings, Chord("end"))
    run_binding(bindings, Chord("home"))
    run_binding(bindings, Chord("up", shift=True))

    assert [text for text, _interrupt in speech.calls] == [
        "Home, Live Game",
        "Live Game",
        "Cards",
        "Settings",
        "Live Game",
        "Home, Live Game",
    ]


def test_vertical_activate_current_and_change_notifications() -> None:
    speech = FakeSpeech()
    actions: list[str] = []
    changes: list[str] = []
    options = [
        MenuOption("field", lambda: "Field", None),
        MenuOption("action", lambda: "Action", lambda: actions.append("action")),
    ]
    engine = menu_engine(options, speech)
    engine.subscribe(lambda: changes.append("changed"))

    assert engine.activate_current() is False
    run_binding(engine.widget_type_bindings(), Chord("down"))
    assert engine.activate_current() is True

    assert actions == ["action"]
    assert changes == ["changed", "changed"]


def horizontal_engine(
    speech: FakeSpeech,
    *,
    first_items: list[str] | None = None,
    second_items: list[str] | None = None,
    context_label: Callable[[], str] | None = None,
) -> HorizontalListEngine:
    one = ["Fireball", "Frostbolt", "Arcane Intellect"] if first_items is None else first_items
    zones = [
        ZoneSpec(
            "one",
            "Your hand",
            lambda: one,
            str,
            lambda item: [f"{item} detail 1", f"{item} detail 2"],
            Chord("c"),
            "C: your hand",
        )
    ]
    if second_items is not None:
        zones.append(
            ZoneSpec(
                "two",
                "Opponent hand",
                lambda: second_items,
                str,
                lambda item: [f"{item} detail"],
                Chord("c", shift=True),
                "Shift+C: opponent hand",
            )
        )
    spec = SurfaceSpec(
        "Cards",
        WidgetType.HORIZONTAL_LIST,
        context_label=context_label,
        zones=zones,
    )
    return HorizontalListEngine(spec, Announcer(speech))


def test_horizontal_entry_movement_details_and_boundaries() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech)
    bindings = engine.widget_type_bindings()

    engine.on_landing()
    run_binding(bindings, Chord("left"))
    run_binding(bindings, Chord("right"))
    run_binding(bindings, Chord("down"))
    run_binding(bindings, Chord("down"))
    run_binding(bindings, Chord("down"))
    run_binding(bindings, Chord("up"))

    assert [text for text, _interrupt in speech.calls] == [
        "Cards, Fireball, 1 of 3",
        "Fireball",
        "Frostbolt",
        "Frostbolt detail 1",
        "Frostbolt detail 2",
        "Frostbolt detail 2",
        "Frostbolt detail 1",
    ]


def test_horizontal_item_movement_resets_detail_cursor() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech)
    bindings = engine.widget_type_bindings()
    run_binding(bindings, Chord("down"))
    run_binding(bindings, Chord("right"))
    run_binding(bindings, Chord("up"))
    assert speech.calls[-1][0] == "Frostbolt"


def test_horizontal_empty_entry_uses_context_label() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(
        speech,
        first_items=[],
        context_label=lambda: "Mage cards, matching fire",
    )
    engine.on_landing()
    assert speech.calls == [("Mage cards, matching fire: empty", True)]


def test_horizontal_orientation_reread_uses_current_line() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech)
    bindings = engine.widget_type_bindings()
    engine.on_landing()
    original = speech.calls[-1]
    run_binding(bindings, Chord("up", shift=True))
    assert speech.calls[-1] == original

    run_binding(bindings, Chord("down"))
    run_binding(bindings, Chord("up", shift=True))
    assert speech.calls[-1] == ("Cards, Fireball detail 1, 1 of 3", True)


def test_horizontal_read_remaining_uses_interrupt_then_queue() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech)
    bindings = engine.widget_type_bindings()
    run_binding(bindings, Chord("down"))
    speech.calls.clear()
    run_binding(bindings, Chord("down", shift=True))
    assert speech.calls == [
        ("Fireball detail 1", True),
        ("Fireball detail 2", False),
    ]


def test_zone_switch_persists_each_zone_cursor() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech, second_items=["Unknown 1", "Unknown 2"])
    bindings = engine.widget_type_bindings()
    run_binding(bindings, Chord("right"))
    engine.switch_zone("two")
    run_binding(bindings, Chord("right"))
    engine.switch_zone("one")
    assert engine.current_item() == "Frostbolt"
    engine.switch_zone("two")
    assert engine.current_item() == "Unknown 2"


def test_zone_switch_persists_each_zone_detail_cursor() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech, second_items=["Unknown"])
    bindings = engine.widget_type_bindings()
    run_binding(bindings, Chord("down"))
    engine.switch_zone("two")
    engine.switch_zone("one")
    speech.calls.clear()
    run_binding(bindings, Chord("up", shift=True))
    assert speech.calls == [("Your hand, Fireball detail 1, 1 of 3", True)]


def test_empty_zone_switch_is_announced_and_does_not_switch() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech, second_items=[])
    engine.switch_zone("two")
    assert engine.current_zone().zone_id == "one"
    assert speech.calls == [("No Opponent hand on this screen", True)]


def test_jump_page_clamping_and_change_notifications() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech)
    changes: list[str] = []
    engine.subscribe(lambda: changes.append("changed"))

    engine.jump_to_position(99)
    assert engine.current_item() == "Arcane Intellect"
    engine.page(-10)
    assert engine.current_item() == "Fireball"
    engine.page(1)
    assert engine.current_item() == "Frostbolt"
    assert changes == ["changed", "changed", "changed"]


def test_zone_bindings_carry_help_and_switch() -> None:
    speech = FakeSpeech()
    engine = horizontal_engine(speech, second_items=["Unknown"])
    zone_bindings = dict(engine.zone_bindings())
    assert zone_bindings[Chord("c", shift=True)].help_phrase == "Shift+C: opponent hand"
    zone_bindings[Chord("c", shift=True)].handler()
    assert engine.current_zone().zone_id == "two"


def test_horizontal_empty_zone_universal_keys_never_silent() -> None:
    # ADR-0004: Home/End, PageUp/PageDown, and bound digit jumps must not
    # die silently when the zone holds nothing.
    speech = FakeSpeech()
    engine = horizontal_engine(speech, first_items=[])
    bindings = engine.widget_type_bindings()

    run_binding(bindings, Chord("home"))
    run_binding(bindings, Chord("end"))
    engine.page(10)
    engine.jump_to_position(3)

    assert [text for text, _interrupt in speech.calls] == ["Cards: empty"] * 4
