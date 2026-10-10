from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from stonereader.app import _switch_live_zone
from stonereader.models.card import Card, CardDatabase
from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard
from stonereader.services._narrator import Narrator
from stonereader.services._tracker import GameTracker
from stonereader.surfaces.live_game import CurrentGame, build_live_game
from stonereader.ui.chords import Chord

from .conftest import Harness, make_harness, placeholder_surface


def _card(
    card_id: str,
    name: str,
    *,
    cost: int = 1,
    attack: int | None = 1,
    health: int | None = 1,
    card_type: str = "MINION",
    text: str = "",
) -> Card:
    return Card(
        card_id,
        len(card_id),
        name,
        cost,
        attack,
        health,
        text,
        "COMMON",
        "NEUTRAL",
        card_type,
    )


def _entity(
    entity_id: int,
    card: Card,
    *,
    controller: int = 1,
    zone: str = "PLAY",
    name: str | None = None,
    drawn_turn: int = -1,
    lineage: str = "",
) -> GameEntity:
    return GameEntity(
        entity_id,
        card.id,
        card,
        card.name if name is None else name,
        card.cost,
        card.attack or 0,
        card.health or 0,
        card.card_type,
        zone,
        1,
        controller,
        drawn_turn=drawn_turn,
        creation_lineage=lineage,
    )


def _played(entity_id: int, card: Card, turn: int, controller: int) -> PlayedCard:
    return PlayedCard(entity_id, card.id, card, card.name, turn, controller)


def _empty_state() -> GameState:
    return GameState(
        turn=3,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=Hero("p", "Jaina", 27, 2, "Fireblast", "MAGE"),
        opponent_hero=Hero("o", "Garrosh", 30, 5, "Armor Up!", "WARRIOR"),
    )


def _rich_state() -> GameState:
    boar = _card("BOAR", "Boar", attack=1, health=3, text="Charge.")
    yeti = _card("YETI", "Yeti", cost=4, attack=4, health=5)
    fireball = _card(
        "FIREBALL",
        "Fireball",
        cost=4,
        attack=None,
        health=None,
        card_type="SPELL",
        text="Deal 6 damage.",
    )
    secret = _card(
        "SECRET",
        "Counterspell",
        cost=3,
        attack=None,
        health=None,
        card_type="SPELL",
    )
    axe = _card("AXE", "Fiery Axe", cost=3, attack=3, health=2, card_type="WEAPON")
    return replace(
        _empty_state(),
        player_board=(_entity(1, boar),),
        opponent_board=(_entity(2, yeti, controller=2),),
        player_hand=(_entity(3, fireball, zone="HAND"),),
        opponent_hand=(None, None),
        player_secrets=(_entity(6, secret, zone="SECRET"),),
        opponent_secrets=(_entity(7, secret, controller=2, zone="SECRET", name=""),),
        player_weapon=_entity(8, axe),
        opponent_weapon=_entity(9, axe, controller=2),
        player_deck=(
            _entity(10, fireball, zone="DECK"),
            _entity(11, fireball, zone="DECK"),
            _entity(12, boar, zone="DECK"),
        ),
        player_played=(_played(13, boar, 1, 1),),
        opponent_played=(_played(14, yeti, 2, 2),),
        player_drawn=(_played(15, fireball, 1, 1),),
        opponent_drawn=(_played(16, yeti, 2, 2),),
        player_mana=4,
        player_max_mana=7,
        opponent_mana=2,
        opponent_max_mana=6,
        player_deck_count=3,
        opponent_deck_count=22,
    )


def _harness(state: GameState | None = None) -> Harness[CurrentGame]:
    current = CurrentGame()
    if state is not None:
        current.on_state(None, state)
    harness = make_harness(current)
    harness.nav.register("Home", lambda: placeholder_surface("Home"))
    harness.nav.register(
        "Live Game",
        lambda: build_live_game(harness.announcer, [], harness.nav, current),
    )
    harness.nav.jump("Live Game")
    return harness


def test_all_fourteen_zone_providers_and_shared_formats() -> None:
    harness = _harness(_rich_state())
    surface = harness.active_surface
    assert [zone.zone_id for zone in surface.spec.zones] == [
        "remaining_deck",
        "your_board",
        "opponent_board",
        "your_hand",
        "your_secrets",
        "opponent_secrets",
        "your_hero",
        "opponent_hero",
        "your_weapon",
        "opponent_weapon",
        "your_played",
        "opponent_played",
        "your_drawn",
        "opponent_drawn",
    ]

    expected_titles = {
        "remaining_deck": ["Boar, 1 copy", "Fireball, 2 copies"],
        "your_board": ["Boar"],
        "opponent_board": ["Yeti"],
        "your_hand": ["Fireball"],
        "your_secrets": ["Counterspell"],
        "opponent_secrets": ["Unknown card"],
        "your_hero": ["Jaina, 27 health, 2 armor"],
        "opponent_hero": ["Garrosh, 30 health, 5 armor"],
        "your_weapon": ["Fiery Axe"],
        "opponent_weapon": ["Fiery Axe"],
        "your_played": ["Boar, turn 1"],
        "opponent_played": ["Yeti, turn 2"],
        "your_drawn": ["Fireball, turn 1"],
        "opponent_drawn": ["Yeti, turn 2"],
    }
    for zone in surface.spec.zones:
        assert [zone.title(item) for item in zone.items()] == expected_titles[zone.zone_id]

    remaining = surface.spec.zones[0]
    assert remaining.detail_lines(remaining.items()[0]) == [
        "33 percent to draw",
        "1 mana",
        "Minion",
        "1 attack, 3 health",
        "Charge.",
    ]
    assert remaining.detail_lines(remaining.items()[1]) == [
        "67 percent to draw",
        "4 mana",
        "Spell",
        "Deal 6 damage.",
    ]


def test_no_game_landing_says_live_game_is_waiting() -> None:
    harness = _harness()
    assert harness.speech.calls[-1] == ("Live Game, waiting for a game", True)
    surface = harness.active_surface
    for zone in surface.spec.zones:
        assert list(zone.items()) == []

    harness.press(Chord("up", shift=True))
    assert harness.speech.calls[-1] == ("Live Game, waiting for a game", True)


def test_no_game_every_zone_query_and_navigation_key_says_waiting() -> None:
    harness = _harness()
    letters = [Chord(key) for key in "bgcsvfwdpn"] + [
        Chord(key, shift=True) for key in "cswpn"
    ]
    queries = [
        Chord("a"),
        Chord("a", shift=True),
        Chord("d", shift=True),
        Chord("r"),
        Chord("r", shift=True),
    ]
    navigation = [
        Chord(key)
        for key in (
            "left", "right", "up", "down", "home", "end",
            *"1234567890",
            "pageup", "pagedown", "y", "f5", "f6", "enter",
        )
    ] + [Chord("down", shift=True)]

    for chord in (*letters, *queries, *navigation):
        harness.speech.calls.clear()
        assert harness.press(chord) is True
        assert harness.speech.calls == [("Waiting for a game", True)], chord
    assert harness.horizontal.current_zone().zone_id == "remaining_deck"

    harness.press(Chord("l"))
    assert harness.speech.calls[-1] == ("No game audio during a live game", True)
    harness.press(Chord("escape"))
    assert harness.nav.stack == ("Home",)


def test_a_starting_game_brings_back_the_zone_landing() -> None:
    harness = _harness()
    harness.speech.calls.clear()
    changes: list[None] = []
    harness.horizontal.subscribe(lambda: changes.append(None))
    harness.context.on_state(None, _rich_state())
    assert harness.speech.calls == []
    assert changes == [None]

    harness.press(Chord("up", shift=True))
    harness.press(Chord("b"))
    assert harness.speech.calls == [
        ("Remaining Deck, Boar, 1 copy, 1 of 2", True),
        ("Your board, Boar, 1 of 1", True),
    ]

    surface = harness.active_surface
    harness.speech.calls.clear()
    harness.context.on_state(
        _rich_state(), replace(_rich_state(), game_state="COMPLETE")
    )
    assert harness.speech.calls == []
    assert all(not zone.items() for zone in surface.spec.zones)
    harness.press(Chord("right"))
    assert harness.speech.calls == [("Waiting for a game", True)]


def test_empty_zone_during_a_game_is_a_place_without_a_turn_prefix() -> None:
    harness = _harness(_empty_state())
    assert harness.speech.calls[-1] == ("Remaining Deck: empty", True)

    harness.press(Chord("b"))
    harness.press(Chord("right"))
    harness.press(Chord("3"))
    assert harness.horizontal.current_zone().zone_id == "your_board"
    assert harness.speech.calls[-3:] == [("Your board: empty", True)] * 3
    harness.press(Chord("v"))
    assert harness.speech.calls[-1] == (
        "Your hero, Jaina, 27 health, 2 armor, 1 of 1",
        True,
    )


def test_queries_digits_y_slots_and_unbound_keys_match_live_contract() -> None:
    harness = _harness(_rich_state())
    for chord, expected in (
        (Chord("a"), "Your mana, 4 of 7"),
        (Chord("a", shift=True), "Opponent mana, 2 of 6"),
        (Chord("d", shift=True), "Opponent deck, 22 cards"),
        (Chord("r"), "Your hero power, Fireblast"),
        (Chord("r", shift=True), "Opponent hero power, Armor Up!"),
    ):
        harness.press(chord)
        assert harness.speech.calls[-1] == (expected, True)
        assert harness.horizontal.current_zone().zone_id == "remaining_deck"

    harness.press(Chord("2"))
    assert harness.speech.calls[-1] == ("Fireball, 2 copies", True)
    for chord, expected in (
        (Chord("y"), "No events in a live game"),
        (Chord("c", shift=True), "The game announces the opponent's hand"),
        (Chord("pageup"), "No turns to step in a live game"),
        (Chord("pagedown"), "No turns to step in a live game"),
        (Chord("l"), "No game audio during a live game"),
        (Chord("enter"), "Nothing to do here"),
        (Chord("tab"), "No groups on this screen"),
        (Chord("f", ctrl=True), "No search on this screen"),
    ):
        harness.press(chord)
        assert harness.speech.calls[-1] == (expected, True)

    before = list(harness.speech.calls)
    assert harness.press(Chord("delete")) is False
    assert harness.press(Chord("space")) is False
    assert harness.speech.calls == before


def test_no_op_keys_carry_help_phrases() -> None:
    harness = _harness(_rich_state())
    help_by_chord = {
        str(chord): command.help_phrase
        for chord, command in harness.active_surface.registry.surface_bindings()
    }

    for chord in (Chord("f5"), Chord("f6")):
        harness.press(chord)
        assert harness.speech.calls[-1] == ("No events in a live game", True)

    assert help_by_chord["f5"] == "F5: no events in a live game"
    assert help_by_chord["f6"] == "F6: no events in a live game"
    assert help_by_chord["enter"] == "Enter: nothing to do here"
    assert help_by_chord["pageup"] == (
        "Page Up and Page Down: no turns to step in a live game"
    )


def test_compound_hotkey_lands_then_switches_to_the_requested_zone() -> None:
    harness = _harness(_rich_state())
    harness.horizontal.switch_zone("your_board")
    harness.speech.calls.clear()

    harness.nav.jump(
        "Live Game",
        then=lambda surface: _switch_live_zone(
            surface, harness.context, "remaining_deck"
        ),
    )
    assert harness.speech.calls[-1] == (
        "Remaining Deck, Boar, 1 copy, 1 of 2",
        True,
    )


def test_compound_hotkey_with_no_game_keeps_the_waiting_landing() -> None:
    harness = _harness()
    harness.speech.calls.clear()

    harness.nav.jump(
        "Live Game",
        then=lambda surface: _switch_live_zone(
            surface, harness.context, "remaining_deck"
        ),
    )
    assert harness.speech.calls == [("Live Game, waiting for a game", True)]


class _Narrations:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def narrate(self, text: str) -> None:
        self.spoken.append(text)


def test_a_live_log_narrates_the_opponents_spell_and_lists_it_as_played() -> None:
    """Power.log lines through the tracker, wired as the app wires it.

    The opponent casts a hidden Fireball (it arrives as a reveal straight into
    PLAY), then plays Acidic Swamp Ooze: Key moments narrates both plays, and
    Opponent played lists both.
    """
    heroes = (
        replace(_card("HERO_08", "Jaina", card_type="HERO"), card_class="MAGE"),
        replace(_card("HERO_01", "Garrosh", card_type="HERO"), card_class="WARRIOR"),
    )
    cards = (
        _card("CS2_106", "Fiery War Axe", card_type="WEAPON"),
        _card("EX1_277", "Arcane Missiles", card_type="SPELL"),
        _card("CS2_029", "Fireball", card_type="SPELL"),
        _card("EX1_066", "Acidic Swamp Ooze"),
    )
    card_db = CardDatabase(cards_by_id={card.id: card for card in (*heroes, *cards)})
    tracker = GameTracker(card_db=card_db)
    current = CurrentGame()
    narrations = _Narrations()
    narrator = Narrator(narrations, lambda: "key_moments", card_db)  # type: ignore[arg-type]
    tracker.subscribe(current.on_state)
    tracker.subscribe(narrator.on_state)

    log = Path(__file__).parent.parent / "fixtures" / "log" / "spells_and_weapons.log"
    tracker._on_lines(log.read_text(encoding="utf-8").splitlines())

    assert narrations.spoken == [
        "Opponent played Fireball",
        "Opponent played Acidic Swamp Ooze",
    ]
    harness = _harness(current.get())
    harness.press(Chord("p", shift=True))
    assert harness.speech.calls[-1] == (
        "Opponent played, Fireball, turn 2, 1 of 2",
        True,
    )
    assert harness.horizontal.items_snapshot()[0] == [
        "Fireball, turn 2",
        "Acidic Swamp Ooze, turn 2",
    ]
