from __future__ import annotations

from dataclasses import replace

from stonereader.models.card import Card
from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard
from stonereader.surfaces.live_game import CurrentGame, build_live_game
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.surface import SurfaceSpec, WidgetType

from tests.test_ui.conftest import FakeSpeech


class _LandingEngine:
    def on_landing(self, queued: bool = False) -> None:
        pass


def _placeholder(name: str) -> ActiveSurface:
    return ActiveSurface(
        SurfaceSpec(name, WidgetType.VERTICAL_MENU, options=lambda: []),
        _LandingEngine(),
        CommandRegistry(),
    )


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
        opponent_hand=(
            None,
            _entity(4, fireball, controller=2, zone="HAND", name="", drawn_turn=-1),
            _entity(
                5,
                yeti,
                controller=2,
                zone="HAND",
                drawn_turn=0,
                lineage="Wand",
            ),
        ),
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


def _harness(state: GameState | None = None):
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    current = CurrentGame()
    if state is not None:
        current.on_state(None, state)
    nav.register("Home", lambda: _placeholder("Home"))
    nav.register(
        "Live Game",
        lambda: build_live_game(announcer, [], nav, current),
    )
    nav.jump("Live Game")
    surface = nav._surfaces["Live Game"]
    assert isinstance(surface.engine, HorizontalListEngine)
    return surface, sink, speech, nav, current


def test_all_fifteen_zone_providers_and_shared_formats() -> None:
    surface, _sink, _speech, _nav, _current = _harness(_rich_state())
    assert [zone.zone_id for zone in surface.spec.zones] == [
        "remaining_deck",
        "your_board",
        "opponent_board",
        "your_hand",
        "opponent_hand",
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
        "opponent_hand": ["Card 1, unknown", "Card 2, unknown", "Card 3, Yeti"],
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


def test_opponent_hand_slots_keep_positions_and_draw_provenance() -> None:
    surface, sink, _speech, _nav, _current = _harness(_rich_state())
    sink.handle_chord(Chord("c", shift=True))
    assert surface.engine.items_snapshot() == (
        ["Card 1, unknown", "Card 2, unknown", "Card 3, Yeti"],
        0,
        ["Drawn turn unknown"],
    )
    surface.engine.jump_to_position(2)
    assert surface.engine.items_snapshot()[2] == ["Drawn turn unknown"]
    surface.engine.jump_to_position(3)
    assert surface.engine.items_snapshot()[2] == [
        "Drawn in the mulligan",
        "Created by Wand",
    ]


def test_no_game_entry_all_queries_and_state_updates_are_lane_one_silent() -> None:
    surface, sink, speech, _nav, current = _harness()
    assert speech.calls[-1] == ("Remaining Deck: empty", True)
    for zone in surface.spec.zones:
        assert list(zone.items()) == []

    for chord in (
        Chord("a"),
        Chord("a", shift=True),
        Chord("d", shift=True),
        Chord("r"),
        Chord("r", shift=True),
    ):
        sink.handle_chord(chord)
        assert speech.calls[-1] == ("No game in progress", True)

    speech.calls.clear()
    changes: list[None] = []
    surface.engine.subscribe(lambda: changes.append(None))
    current.on_state(None, _rich_state())
    assert speech.calls == []
    assert changes == [None]

    current.on_state(_rich_state(), replace(_rich_state(), game_state="COMPLETE"))
    assert all(not zone.items() for zone in surface.spec.zones)


def test_queries_digits_y_slots_and_unbound_keys_match_live_contract() -> None:
    surface, sink, speech, _nav, _current = _harness(_rich_state())
    for chord, expected in (
        (Chord("a"), "Your mana, 4 of 7"),
        (Chord("a", shift=True), "Opponent mana, 2 of 6"),
        (Chord("d", shift=True), "Opponent deck, 22 cards"),
        (Chord("r"), "Your hero power, Fireblast"),
        (Chord("r", shift=True), "Opponent hero power, Armor Up!"),
    ):
        sink.handle_chord(chord)
        assert speech.calls[-1] == (expected, True)
        assert surface.engine.current_zone().zone_id == "remaining_deck"

    sink.handle_chord(Chord("2"))
    assert speech.calls[-1] == ("Fireball, 2 copies", True)
    for chord, expected in (
        (Chord("y"), "No events in a live game"),
        (Chord("pageup"), "No turns to step in a live game"),
        (Chord("pagedown"), "No turns to step in a live game"),
        (Chord("l"), "No game audio during a live game"),
        (Chord("enter"), "Nothing to do here"),
        (Chord("tab"), "No groups on this screen"),
        (Chord("f", ctrl=True), "No search on this screen"),
    ):
        sink.handle_chord(chord)
        assert speech.calls[-1] == (expected, True)

    before = list(speech.calls)
    assert sink.handle_chord(Chord("delete")) is False
    assert sink.handle_chord(Chord("space")) is False
    assert speech.calls == before


def test_compound_hotkeys_land_then_switch_to_the_requested_zone() -> None:
    surface, _sink, speech, nav, _current = _harness(_rich_state())
    surface.engine.switch_zone("your_board")
    speech.calls.clear()

    nav.jump(
        "Live Game",
        then=lambda active: active.engine.switch_zone("remaining_deck"),  # type: ignore[attr-defined]
    )
    assert speech.calls[-1] == (
        "Remaining Deck, Boar, 1 copy, 1 of 2",
        True,
    )

    nav.jump(
        "Live Game",
        then=lambda active: active.engine.switch_zone("opponent_hand"),  # type: ignore[attr-defined]
    )
    assert speech.calls[-1] == (
        "Opponent hand, Card 1, unknown, 1 of 3",
        True,
    )
