from __future__ import annotations

import pytest

from stonereader.models.card import Card, CardDatabase
from stonereader.services._audio_index import CardClip
from stonereader.surfaces._help_content import screen_bindings
from stonereader.surfaces.cards import CardsState, build_card_browser, build_cards
from stonereader.surfaces.sounds_menu import SoundsMenuHolder
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface
from stonereader.ui.surface import SurfaceSpec, WidgetType

from .conftest import Harness, make_harness as make_base_harness, placeholder_surface


@pytest.fixture(scope="module")
def real_card_db() -> CardDatabase:
    return CardDatabase.load()


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


class FakeAudioIndex:
    def __init__(
        self,
        status: str,
        reason: str,
        clips: list[CardClip] | None = None,
    ) -> None:
        self.status = status
        self.reason = reason
        self._clips = clips or []

    def clips_for_card(self, card_id: str) -> list[CardClip]:
        del card_id
        return list(self._clips)


def make_harness(
    card_db: CardDatabase,
    audio_index: FakeAudioIndex | None = None,
    sounds: SoundsMenuHolder | None = None,
) -> Harness[None]:
    harness = make_base_harness(None)
    if audio_index is not None and sounds is not None:
        harness.nav.register(
            "Sounds menu",
            lambda: placeholder_surface("Sounds menu"),
        )
    harness.set_surface(
        build_card_browser(
            harness.announcer,
            [],
            harness.nav,
            card_db,
            harness.sink,
            CardsState(),
            audio_index=audio_index,
            sounds=sounds,
        )
    )
    return harness


def test_listen_handles_empty_warming_no_clips_and_pushes_ready_card() -> None:
    sounds = SoundsMenuHolder()
    empty = make_harness(
        database(),
        FakeAudioIndex("ready", "", [CardClip("Play", "key")]),
        sounds,
    )
    empty.press(Chord("l"))
    assert empty.speech.calls[-1] == ("No card focused", True)

    warming = make_harness(
        database(card(1, "Fireball")),
        FakeAudioIndex("indexing", "Game audio is not ready yet"),
        SoundsMenuHolder(),
    )
    warming.press(Chord("l"))
    assert warming.nav.stack == ("Home",)
    assert warming.speech.calls[-1] == ("Game audio is not ready yet", True)

    silent = make_harness(
        database(card(1, "Fireball")),
        FakeAudioIndex("ready", ""),
        SoundsMenuHolder(),
    )
    silent.press(Chord("l"))
    assert silent.nav.stack == ("Home",)
    assert silent.speech.calls[-1] == ("Fireball: no sounds", True)

    ready_sounds = SoundsMenuHolder()
    ready = make_harness(
        database(card(1, "Fireball")),
        FakeAudioIndex("ready", "", [CardClip("Play", "key")]),
        ready_sounds,
    )
    ready.press(Chord("l"))
    assert ready.nav.stack == ("Home", "Sounds menu")
    assert ready_sounds.get().card_name == "Fireball"


def current_names(harness: Harness[None]) -> list[str]:
    return harness.horizontal.items_snapshot()[0]


def cycle_to_mage(harness: Harness[None]) -> None:
    for _ in range(5):
        harness.press(Chord("tab"))


def commit_search(harness: Harness[None], query: str) -> None:
    harness.press(Chord("f", ctrl=True))
    harness.type(query)
    harness.press(Chord("enter"))


def test_real_database_is_loaded_once_and_initial_results_are_mana_then_name_sorted(
    real_card_db: CardDatabase,
) -> None:
    harness = make_harness(real_card_db)
    values = list(harness.subject_surface.spec.zones[0].items())

    assert values
    keys = [(value.cost, value.name.casefold(), value.dbf_id) for value in values]
    assert keys == sorted(keys)
    assert all(value.collectible for value in values)


def test_context_label_composes_all_spec_rows_verbatim() -> None:
    harness = make_harness(
        database(
            card(1, "Fire Three", cost=3, card_class="MAGE", text="fire"),
            card(2, "Other", cost=3, card_class="MAGE"),
        )
    )
    label = harness.subject_surface.spec.context_label
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
    assert current_names(harness) == ["Mage Fire Three", "Mage Fire Four"]
    assert harness.subject_surface.spec.context_label is not None
    assert harness.subject_surface.spec.context_label() == "Mage cards, matching fire"

    harness.press(Chord("f", ctrl=True))
    for _ in "fire":
        harness.press(Chord("backspace"))
    harness.press(Chord("enter"))
    assert current_names(harness) == [
        "Mage Fire Three",
        "Mage Water Three",
        "Mage Fire Four",
    ]
    assert harness.subject_surface.spec.context_label() == "Mage cards"


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
    assert current_names(harness) == ["Zero", "Eight", "Nine", "Twelve"]

    harness.press(Chord("9"))
    assert current_names(harness) == ["Nine", "Twelve"]
    assert harness.subject_surface.spec.context_label is not None
    assert harness.subject_surface.spec.context_label() == "All cards, 9 plus mana"
    harness.press(Chord("9"))
    assert current_names(harness) == ["Zero", "Eight", "Nine", "Twelve"]


def test_tab_cycles_both_directions_with_wraparound() -> None:
    harness = make_harness(database(card(1, "Only")))
    label = harness.subject_surface.spec.context_label
    assert label is not None

    harness.press(Chord("tab"))
    assert label() == "Death Knight cards"
    harness.press(Chord("tab", shift=True))
    assert label() == "All cards"
    harness.press(Chord("tab", shift=True))
    assert label() == "Neutral cards"
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
    assert harness.subject_surface.spec.context_label is not None
    assert harness.subject_surface.spec.context_label() == "All cards matching fire"

    harness.press(Chord("f", ctrl=True))
    harness.type("x")
    harness.press(Chord("escape"))
    assert harness.subject_surface.spec.context_label() == "All cards matching fire"
    assert current_names(harness) == ["Fireball"]

    harness.press(Chord("f", ctrl=True))
    for _ in "fire":
        harness.press(Chord("backspace"))
    harness.press(Chord("enter"))
    assert harness.subject_surface.spec.context_label() == "All cards"
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
    assert harness.horizontal.items_snapshot()[1] == 10
    harness.press(Chord("pagedown"))
    harness.press(Chord("pagedown"))
    assert harness.horizontal.items_snapshot()[1] == 24
    harness.press(Chord("pageup"))
    assert harness.horizontal.items_snapshot()[1] == 14
    harness.press(Chord("pageup"))
    harness.press(Chord("pageup"))
    assert harness.horizontal.items_snapshot()[1] == 0


def test_help_documents_both_directions_for_class_and_page_chords() -> None:
    harness = make_harness(database(card(1, "Only")))
    phrases = [
        entry.phrase for entry in screen_bindings(harness.subject_surface)
    ]

    assert phrases[-5:] == [
        "Tab: jump to the next class",
        "Shift+Tab: jump to the previous class",
        "Ctrl+F: search for a card",
        "Page Up: jump ten cards back",
        "Page Down: jump ten cards forward",
    ]


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

    harness.press(Chord("right"))
    assert harness.horizontal.items_snapshot()[2] == [
        "2 mana",
        "Minion",
        "3 attack, 4 health",
        "Taunt.",
        "Mage",
        "Rare",
        "CORE",
    ]
    harness.press(Chord("right"))
    assert harness.horizontal.items_snapshot()[2] == [
        "3 mana",
        "Weapon",
        "4 attack, 2 durability",
        "Swing.",
        "Warrior",
        "Epic",
        "EXPERT1",
    ]
    harness.press(Chord("home"))
    assert harness.horizontal.items_snapshot()[2] == [
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
    harness = make_base_harness(None)
    builds = 0
    cards_surface: ActiveSurface | None = None

    def cards_factory() -> ActiveSurface:
        nonlocal builds, cards_surface
        builds += 1
        cards_surface = build_card_browser(
            harness.announcer,
            [],
            harness.nav,
            card_db,
            harness.sink,
            CardsState(),
        )
        return cards_surface

    def home_factory() -> ActiveSurface:
        return build_active_surface(
            SurfaceSpec("Home", WidgetType.VERTICAL_MENU, options=lambda: []),
            harness.announcer,
            [],
            harness.nav,
        )

    harness.nav.register("Home", home_factory)
    harness.nav.register("Card Browser", cards_factory)
    harness.nav.jump("Card Browser")
    assert cards_surface is not None
    cycle_to_mage(harness)
    harness.press(Chord("3"))
    commit_search(harness, "fire")

    harness.nav.jump("Home")
    harness.nav.jump("Card Browser")

    assert cards_surface.spec.context_label is not None
    assert cards_surface.spec.context_label() == (
        "Mage cards, 3 mana, matching fire"
    )
    assert builds == 1
    assert harness.speech.calls[-1] == (
        "Mage cards, 3 mana, matching fire, Fire Three, 1 of 1",
        True,
    )


def test_class_menu_drills_down_to_sorted_cards_and_back_keeps_menu_position() -> None:
    card_db = database(
        card(1, "Zebra", cost=0, card_class="MAGE"),
        card(2, "Beta", cost=2, card_class="MAGE"),
        card(3, "alpha", cost=2, card_class="MAGE"),
        card(4, "Neutral card", cost=1),
    )
    harness = make_base_harness(None)
    state = CardsState()
    harness.nav.register("Home", lambda: build_active_surface(
        SurfaceSpec("Home", WidgetType.VERTICAL_MENU, options=lambda: []),
        harness.announcer, [], harness.nav,
    ))
    harness.nav.register("Cards", lambda: build_cards(
        harness.announcer, [], harness.nav, state,
    ))
    harness.nav.register("Card Browser", lambda: build_card_browser(
        harness.announcer, [], harness.nav, card_db, harness.sink, state,
    ))
    harness.nav.jump("Cards")
    titles, _ = harness.vertical.options_snapshot()
    assert titles == [
        "Death Knight", "Demon Hunter", "Druid", "Hunter", "Mage", "Paladin",
        "Priest", "Rogue", "Shaman", "Warlock", "Warrior", "Neutral", "All cards",
    ]
    for _ in range(4):
        harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Cards", "Card Browser")
    assert current_names(harness) == ["Zebra", "alpha", "Beta"]
    assert harness.speech.calls[-1] == ("Mage cards, Zebra, 1 of 3", True)
    harness.press(Chord("2"))
    harness.press(Chord("right"))
    harness.press(Chord("escape"))
    assert harness.nav.stack == ("Home", "Cards")
    assert harness.vertical.options_snapshot()[1] == 4
    assert harness.speech.calls[-1] == ("Cards, Mage", True)
    harness.press(Chord("enter"))
    assert current_names(harness) == ["alpha", "Beta"]
    assert harness.horizontal.items_snapshot()[1] == 0
    harness.press(Chord("2"))
    harness.press(Chord("backspace"))
    for _ in range(7):
        harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert current_names(harness) == ["Neutral card"]
    assert harness.speech.calls[-1] == ("Neutral cards, Neutral card, 1 of 1", True)
    harness.nav.jump("Cards")
    assert harness.nav.stack == ("Home", "Cards")
    harness.press(Chord("escape"))
    assert harness.nav.stack == ("Home",)


def test_filter_changes_reset_card_and_detail_cursors_and_notify_renderer() -> None:
    harness = make_harness(database(*(
        card(index, f"Mage {index}", cost=2, card_class="MAGE")
        for index in range(5)
    )))
    renders: list[int] = []
    harness.horizontal.subscribe(
        lambda: renders.append(harness.horizontal.items_snapshot()[1])
    )
    for change in (lambda: cycle_to_mage(harness),
                   lambda: harness.press(Chord("2")),
                   lambda: commit_search(harness, "Mage")):
        harness.press(Chord("end"))
        harness.press(Chord("down"))
        change()
        assert harness.horizontal.items_snapshot()[1] == 0
        assert renders[-1] == 0
        start = len(harness.speech.calls)
        harness.press(Chord("down", shift=True))
        assert harness.speech.calls[start][0] == "Mage 0"


def test_abandoning_search_keeps_the_current_card() -> None:
    harness = make_harness(database(card(1, "First"), card(2, "Second")))
    harness.press(Chord("end"))
    harness.press(Chord("f", ctrl=True))
    harness.type("missing")
    harness.press(Chord("escape"))
    assert harness.horizontal.items_snapshot()[1] == 1
