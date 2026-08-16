from __future__ import annotations

from dataclasses import dataclass

import pytest

from stonereader.models.card import Card, CardDatabase
from stonereader.surfaces.cards import build_cards
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.surface import SurfaceSpec, WidgetType

from tests.test_ui.conftest import FakeSpeech


@pytest.fixture(scope="module")
def real_card_db() -> CardDatabase:
    return CardDatabase.load()


@dataclass
class Harness:
    surface: ActiveSurface
    sink: _SinkCore
    speech: FakeSpeech
    nav: NavigationController

    @property
    def engine(self) -> HorizontalListEngine:
        assert isinstance(self.surface.engine, HorizontalListEngine)
        return self.surface.engine

    def press(self, chord: Chord) -> bool:
        return self.sink.handle_chord(chord)

    def type(self, text: str) -> None:
        for character in text:
            self.press(Chord("space") if character == " " else Chord(character))


def card(
    dbf_id: int,
    name: str,
    *,
    cost: int = 1,
    card_class: str = "NEUTRAL",
    card_type: str = "SPELL",
    attack: int | None = None,
    health: int | None = None,
    text: str = "",
    rarity: str = "COMMON",
    card_set: str = "TEST",
    durability: int | None = None,
) -> Card:
    return Card(
        id=f"TEST_{dbf_id}",
        dbf_id=dbf_id,
        name=name,
        cost=cost,
        attack=attack,
        health=health,
        text=text,
        rarity=rarity,
        card_class=card_class,
        card_type=card_type,
        card_set=card_set,
        durability=durability,
    )


def database(*cards: Card) -> CardDatabase:
    card_db = CardDatabase()
    card_db.collectible_cards.extend(cards)
    return card_db


def make_harness(card_db: CardDatabase) -> Harness:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    surface = build_cards(announcer, [], nav, card_db, sink)
    sink.set_active(surface.registry)
    return Harness(surface, sink, speech, nav)


def current_names(harness: Harness) -> list[str]:
    return harness.engine.items_snapshot()[0]


def cycle_to_mage(harness: Harness) -> None:
    for _ in range(5):
        harness.press(Chord("tab"))


def commit_search(harness: Harness, query: str) -> None:
    harness.press(Chord("f", ctrl=True))
    harness.type(query)
    harness.press(Chord("enter"))


def test_real_database_is_loaded_once_and_initial_results_are_name_sorted(
    real_card_db: CardDatabase,
) -> None:
    harness = make_harness(real_card_db)
    values = list(harness.surface.spec.zones[0].items())

    assert values
    assert [value.name for value in values] == sorted(value.name for value in values)
    assert all(value.collectible for value in values)


def test_context_label_composes_all_spec_rows_verbatim() -> None:
    harness = make_harness(
        database(
            card(1, "Fire Three", cost=3, card_class="MAGE", text="fire"),
            card(2, "Other", cost=3, card_class="MAGE"),
        )
    )
    label = harness.surface.spec.context_label
    assert label is not None

    assert label() == "All cards"
    cycle_to_mage(harness)
    assert label() == "Mage cards"
    harness.press(Chord("3"))
    assert label() == "Mage cards, 3 mana"
    commit_search(harness, "fire")
    assert label() == "Mage cards, 3 mana, matching fire"
    harness.press(Chord("3"))
    assert label() == "Mage cards, matching fire"
    for _ in range(5):
        harness.press(Chord("tab", shift=True))
    assert label() == "All cards matching fire"


def test_filters_and_search_and_clearing_one_leaves_the_others() -> None:
    harness = make_harness(
        database(
            card(1, "Mage Fire Three", cost=3, card_class="MAGE", text="fire"),
            card(2, "Mage Water Three", cost=3, card_class="MAGE", text="water"),
            card(3, "Neutral Fire Three", cost=3, text="fire"),
            card(4, "Mage Fire Four", cost=4, card_class="MAGE", text="fire"),
        )
    )
    cycle_to_mage(harness)
    harness.press(Chord("3"))
    commit_search(harness, "fire")
    assert current_names(harness) == ["Mage Fire Three"]

    harness.press(Chord("3"))
    assert current_names(harness) == ["Mage Fire Four", "Mage Fire Three"]
    assert harness.surface.spec.context_label is not None
    assert harness.surface.spec.context_label() == "Mage cards, matching fire"

    harness.press(Chord("f", ctrl=True))
    for _ in "fire":
        harness.press(Chord("backspace"))
    harness.press(Chord("enter"))
    assert current_names(harness) == [
        "Mage Fire Four",
        "Mage Fire Three",
        "Mage Water Three",
    ]
    assert harness.surface.spec.context_label() == "Mage cards"


def test_digits_toggle_exact_zero_and_nine_plus_filters() -> None:
    harness = make_harness(
        database(
            card(1, "Zero", cost=0),
            card(2, "Eight", cost=8),
            card(3, "Nine", cost=9),
            card(4, "Twelve", cost=12),
        )
    )

    harness.press(Chord("0"))
    assert current_names(harness) == ["Zero"]
    harness.press(Chord("0"))
    assert current_names(harness) == ["Eight", "Nine", "Twelve", "Zero"]

    harness.press(Chord("9"))
    assert current_names(harness) == ["Nine", "Twelve"]
    assert harness.surface.spec.context_label is not None
    assert harness.surface.spec.context_label() == "All cards, 9 plus mana"
    harness.press(Chord("9"))
    assert current_names(harness) == ["Eight", "Nine", "Twelve", "Zero"]


def test_tab_cycles_both_directions_with_wraparound() -> None:
    harness = make_harness(database(card(1, "Only")))
    label = harness.surface.spec.context_label
    assert label is not None

    harness.press(Chord("tab"))
    assert label() == "Demon Hunter cards"
    harness.press(Chord("tab", shift=True))
    assert label() == "All cards"
    harness.press(Chord("tab", shift=True))
    assert label() == "Warrior cards"
    harness.press(Chord("tab"))
    assert label() == "All cards"


def test_search_commit_abandon_and_empty_commit_clear() -> None:
    harness = make_harness(
        database(
            card(1, "Fireball", text="damage"),
            card(2, "Frostbolt", text="freeze"),
        )
    )

    commit_search(harness, "fire")
    assert harness.sink.text_mode_active is False
    assert current_names(harness) == ["Fireball"]
    assert harness.surface.spec.context_label is not None
    assert harness.surface.spec.context_label() == "All cards matching fire"

    harness.press(Chord("f", ctrl=True))
    harness.type("x")
    harness.press(Chord("escape"))
    assert harness.surface.spec.context_label() == "All cards matching fire"
    assert current_names(harness) == ["Fireball"]

    harness.press(Chord("f", ctrl=True))
    for _ in "fire":
        harness.press(Chord("backspace"))
    harness.press(Chord("enter"))
    assert harness.surface.spec.context_label() == "All cards"
    assert current_names(harness) == ["Fireball", "Frostbolt"]


def test_filter_and_search_changes_speak_full_context_entry() -> None:
    harness = make_harness(
        database(
            card(1, "Fire Three", cost=3, card_class="MAGE", text="fire"),
            card(2, "Other Three", cost=3, card_class="MAGE"),
        )
    )

    cycle_to_mage(harness)
    assert harness.speech.calls[-1] == ("Mage cards, Fire Three, 1 of 2", True)
    harness.press(Chord("3"))
    assert harness.speech.calls[-1] == (
        "Mage cards, 3 mana, Fire Three, 1 of 2",
        True,
    )
    commit_search(harness, "fire")
    assert harness.speech.calls[-1] == (
        "Mage cards, 3 mana, matching fire, Fire Three, 1 of 1",
        True,
    )


def test_paging_moves_ten_and_clamps_at_both_ends() -> None:
    harness = make_harness(
        database(*(card(index, f"Card {index:02d}") for index in range(25)))
    )

    harness.press(Chord("pagedown"))
    assert harness.engine.items_snapshot()[1] == 10
    harness.press(Chord("pagedown"))
    harness.press(Chord("pagedown"))
    assert harness.engine.items_snapshot()[1] == 24
    harness.press(Chord("pageup"))
    assert harness.engine.items_snapshot()[1] == 14
    harness.press(Chord("pageup"))
    harness.press(Chord("pageup"))
    assert harness.engine.items_snapshot()[1] == 0


def test_detail_lines_cover_minion_weapon_spell_and_empty_text() -> None:
    harness = make_harness(
        database(
            card(
                1,
                "A Minion",
                cost=2,
                card_class="MAGE",
                card_type="MINION",
                attack=3,
                health=4,
                text="Taunt.",
                rarity="RARE",
                card_set="CORE",
            ),
            card(
                2,
                "B Weapon",
                cost=3,
                card_class="WARRIOR",
                card_type="WEAPON",
                attack=4,
                health=2,
                text="Swing.",
                rarity="EPIC",
                card_set="EXPERT1",
                durability=99,
            ),
            card(
                3,
                "C Spell",
                cost=1,
                card_class="MAGE",
                card_type="SPELL",
                attack=8,
                health=8,
                text="",
            ),
        )
    )

    assert harness.engine.items_snapshot()[2] == [
        "2 mana",
        "Minion",
        "3 attack, 4 health",
        "Taunt.",
        "Mage",
        "Rare",
        "CORE",
    ]
    harness.press(Chord("right"))
    assert harness.engine.items_snapshot()[2] == [
        "3 mana",
        "Weapon",
        "4 attack, 2 durability",
        "Swing.",
        "Warrior",
        "Epic",
        "EXPERT1",
    ]
    harness.press(Chord("right"))
    assert harness.engine.items_snapshot()[2] == [
        "1 mana",
        "Spell",
        "Mage",
        "Common",
        "TEST",
    ]


def test_enter_and_listen_are_announced_noops_delete_and_space_are_silent() -> None:
    harness = make_harness(database(card(1, "Only")))

    assert harness.press(Chord("enter")) is True
    assert harness.press(Chord("l")) is True
    before_silent = list(harness.speech.calls)
    assert harness.press(Chord("delete")) is False
    assert harness.press(Chord("space")) is False

    assert harness.speech.calls[:2] == [
        ("Nothing to do here", True),
        ("Game audio is not available", True),
    ]
    assert harness.speech.calls == before_silent


def test_filter_state_survives_leave_and_return() -> None:
    card_db = database(
        card(1, "Fire Three", cost=3, card_class="MAGE", text="fire"),
        card(2, "Other", cost=4),
    )
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    builds = 0
    cards_surface: ActiveSurface | None = None

    def cards_factory() -> ActiveSurface:
        nonlocal builds, cards_surface
        builds += 1
        cards_surface = build_cards(announcer, [], nav, card_db, sink)
        return cards_surface

    def home_factory() -> ActiveSurface:
        return build_active_surface(
            SurfaceSpec("Home", WidgetType.VERTICAL_MENU, options=lambda: []),
            announcer,
            [],
            nav,
        )

    nav.register("Home", home_factory)
    nav.register("Cards", cards_factory)
    nav.jump("Cards")
    assert cards_surface is not None
    harness = Harness(cards_surface, sink, speech, nav)
    cycle_to_mage(harness)
    sink.handle_chord(Chord("3"))
    commit_search(harness, "fire")

    nav.jump("Home")
    nav.jump("Cards")

    assert cards_surface.spec.context_label is not None
    assert cards_surface.spec.context_label() == (
        "Mage cards, 3 mana, matching fire"
    )
    assert builds == 1
    assert speech.calls[-1] == (
        "Mage cards, 3 mana, matching fire, Fire Three, 1 of 1",
        True,
    )
