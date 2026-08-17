from __future__ import annotations

from dataclasses import replace

from stonereader.models.card import Card
from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard
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


def test_no_game_entry_all_queries_and_state_updates_are_lane_one_silent() -> None:
    harness = _harness()
    assert harness.speech.calls[-1] == ("Remaining Deck: empty", True)
    surface = harness.active_surface
    for zone in surface.spec.zones:
        assert list(zone.items()) == []

    for chord in (
        Chord("a"),
        Chord("a", shift=True),
        Chord("d", shift=True),
        Chord("r"),
        Chord("r", shift=True),
    ):
        harness.press(chord)
        assert harness.speech.calls[-1] == ("No game in progress", True)

    harness.speech.calls.clear()
    changes: list[None] = []
    harness.horizontal.subscribe(lambda: changes.append(None))
    harness.context.on_state(None, _rich_state())
    assert harness.speech.calls == []
    assert changes == [None]

    harness.context.on_state(
        _rich_state(), replace(_rich_state(), game_state="COMPLETE")
    )
    assert all(not zone.items() for zone in surface.spec.zones)


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


def test_event_step_keys_announce_no_events_in_a_live_game() -> None:
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


def test_compound_hotkey_lands_then_switches_to_the_requested_zone() -> None:
    harness = _harness(_rich_state())
    harness.horizontal.switch_zone("your_board")
    harness.speech.calls.clear()

    harness.nav.jump(
        "Live Game",
        then=lambda _active: harness.horizontal.switch_zone("remaining_deck"),
    )
    assert harness.speech.calls[-1] == (
        "Remaining Deck, Boar, 1 copy, 1 of 2",
        True,
    )
