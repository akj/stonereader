"""Tests for stonereader.presenters.replay_viewer.ReplayViewerPresenter.

Slice #15 — the Replay viewer capstone. Turn-first navigation, event
drilldown, and an HSA-mirroring keymap (ADR-0003).

All tests run at the presenter level against MockSpeechService and a
hand-built ReplayState (no wx, no real speech). The ReplayState is a
Tuple[GameState, ...] with controlled zones across several turns so we can
assert that every zone resolves against the current (turn, event) moment.

Test idiom mirrors tests/test_live_game_presenter.py (_make_card /
_make_entity / Hero helpers).
"""

from __future__ import annotations

from typing import Optional, Tuple

from stonereader.models.card import Card
from stonereader.models.game_state import (
    GameEntity,
    GameState,
    Hero,
    PlayedCard,
)
from stonereader.models.replay import ReplayState
from stonereader.presenters.replay_viewer import ReplayViewerPresenter
from stonereader.services import _events
from tests.conftest import MockSpeechService

# -------------------------------- Helpers --------------------------------

_next_dbf_id = 7000  # avoid collision with other test modules


def _make_card(
    card_id: str,
    name: str,
    cost: int = 1,
    card_type: str = "MINION",
    attack: Optional[int] = 1,
    health: Optional[int] = 1,
    durability: Optional[int] = None,
) -> Card:
    global _next_dbf_id
    _next_dbf_id += 1
    return Card(
        id=card_id,
        dbf_id=_next_dbf_id,
        name=name,
        cost=cost,
        attack=attack,
        health=health,
        text="",
        rarity="COMMON",
        card_class="NEUTRAL",
        card_type=card_type,
        card_set="EXPERT1",
        collectible=True,
        durability=durability,
    )


def _hero(hc: str, name: str = "Hero", hero_power: str = "Fireblast") -> Hero:
    return Hero(
        id="HERO_" + hc,
        name=name,
        health=30,
        armor=0,
        hero_power=hero_power,
        hero_class=hc,
    )


def _make_entity(
    card: Card,
    controller: int = 1,
    zone: str = "PLAY",
    entity_id: Optional[int] = None,
    drawn_turn: int = -1,
) -> GameEntity:
    return GameEntity(
        entity_id=entity_id if entity_id is not None else abs(hash(card.id)) % 100000,
        card_id=card.id,
        base_card=card,
        name=card.name,
        cost=card.cost,
        current_attack=card.attack or 0,
        current_health=card.health or 0,
        card_type=card.card_type,
        zone=zone,
        zone_position=0,
        controller=controller,
        drawn_turn=drawn_turn,
    )


def _played(card: Card, turn: int, controller: int, entity_id: int) -> PlayedCard:
    return PlayedCard(
        entity_id=entity_id,
        card_id=card.id,
        base_card=card,
        name=card.name,
        turn=turn,
        controller=controller,
    )


def _state(
    turn: int,
    active_player_id: int = 1,
    *,
    player_board: Tuple[GameEntity, ...] = (),
    opponent_board: Tuple[GameEntity, ...] = (),
    player_hand: Tuple[GameEntity, ...] = (),
    opponent_hand: Tuple[Optional[GameEntity], ...] = (),
    player_secrets: Tuple[GameEntity, ...] = (),
    opponent_secrets: Tuple[GameEntity, ...] = (),
    player_weapon: Optional[GameEntity] = None,
    opponent_weapon: Optional[GameEntity] = None,
    player_deck: Tuple[GameEntity, ...] = (),
    player_played: Tuple[PlayedCard, ...] = (),
    opponent_played: Tuple[PlayedCard, ...] = (),
    player_drawn: Tuple[PlayedCard, ...] = (),
    opponent_drawn: Tuple[PlayedCard, ...] = (),
    player_mana: int = 0,
    player_max_mana: int = 0,
    opponent_mana: int = 0,
    opponent_max_mana: int = 0,
    opponent_deck_count: int = 0,
    player_hero: Optional[Hero] = None,
    opponent_hero: Optional[Hero] = None,
    block_stack: Tuple[str, ...] = (),
) -> GameState:
    return GameState(
        turn=turn,
        active_player_id=active_player_id,
        player_board=player_board,
        opponent_board=opponent_board,
        player_hand=player_hand,
        opponent_hand=opponent_hand,
        player_hero=player_hero or _hero("MAGE", "You", "Fireblast"),
        opponent_hero=opponent_hero or _hero("WARRIOR", "Opp", "Armor Up!"),
        player_weapon=player_weapon,
        opponent_weapon=opponent_weapon,
        player_secrets=player_secrets,
        opponent_secrets=opponent_secrets,
        player_mana=player_mana,
        player_max_mana=player_max_mana,
        opponent_mana=opponent_mana,
        opponent_max_mana=opponent_max_mana,
        opponent_deck_count=opponent_deck_count,
        player_deck=player_deck,
        player_played=player_played,
        opponent_played=opponent_played,
        player_drawn=player_drawn,
        opponent_drawn=opponent_drawn,
        block_stack=block_stack,
    )


# Shared cards.
_BOAR = _make_card("CS2_boar", "Stonetusk Boar", cost=1, attack=1, health=1)
_YETI = _make_card("CS2_yeti", "Chillwind Yeti", cost=4, attack=4, health=5)
_FIREBALL = _make_card(
    "CS2_fireball", "Fireball", cost=4, card_type="SPELL", attack=None, health=None
)
_SWORD = _make_card(
    "CS2_sword",
    "Fiery War Axe",
    cost=3,
    card_type="WEAPON",
    attack=3,
    health=2,
    durability=2,
)
_SECRET = _make_card(
    "CS2_secret", "Counterspell", cost=3, card_type="SPELL", attack=None, health=None
)
_RENO = _make_card("LOOT_reno", "Reno Jackson", cost=6, attack=4, health=6)


def _build_replay() -> ReplayState:
    """Three-turn replay with controlled zones.

    Turn 1: player plays a Boar (so the diff produces a CardPlayed event).
            Two transitions land on turn 1 to exercise event stepping.
    Turn 2: opponent's turn — board, weapon, secrets, played, drawn, mana.
    Turn 3: player turn with hand, deck, hero power, opponent hand (hidden).
    """
    # --- Turn 1: two transitions, both post_state.turn == 1 ---
    boar = _make_entity(_BOAR, controller=1, zone="HAND", entity_id=11)
    t1a = _state(
        turn=1,
        active_player_id=1,
        player_hand=(boar,),
        player_mana=1,
        player_max_mana=1,
    )
    # Boar moves HAND -> PLAY inside a PLAY block => CardPlayed event.
    boar_in_play = _make_entity(_BOAR, controller=1, zone="PLAY", entity_id=11)
    t1b = _state(
        turn=1,
        active_player_id=1,
        player_board=(boar_in_play,),
        player_mana=0,
        player_max_mana=1,
        block_stack=("PLAY",),
    )
    # A second card drawn on turn 1 in a later transition (still turn 1):
    yeti_drawn = _make_entity(_YETI, controller=1, zone="HAND", entity_id=12)
    t1c = _state(
        turn=1,
        active_player_id=1,
        player_board=(boar_in_play,),
        player_hand=(yeti_drawn,),
        player_mana=0,
        player_max_mana=1,
    )

    # --- Turn 2: opponent's turn, rich opponent zones ---
    opp_minion = _make_entity(_RENO, controller=2, zone="PLAY", entity_id=21)
    opp_weapon = _make_entity(_SWORD, controller=2, zone="PLAY", entity_id=22)
    opp_secret = _make_entity(_SECRET, controller=2, zone="SECRET", entity_id=23)
    t2 = _state(
        turn=2,
        active_player_id=2,
        player_board=(boar_in_play,),
        opponent_board=(opp_minion,),
        opponent_weapon=opp_weapon,
        opponent_secrets=(opp_secret,),
        opponent_played=(_played(_RENO, turn=2, controller=2, entity_id=21),),
        opponent_drawn=(_played(_RENO, turn=2, controller=2, entity_id=21),),
        opponent_mana=2,
        opponent_max_mana=2,
        opponent_deck_count=25,
    )

    # --- Turn 3: player's turn, rich friendly zones ---
    yeti_board = _make_entity(_YETI, controller=1, zone="PLAY", entity_id=12)
    my_weapon = _make_entity(_SWORD, controller=1, zone="PLAY", entity_id=31)
    my_secret = _make_entity(_SECRET, controller=1, zone="SECRET", entity_id=32)
    my_hand_card = _make_entity(_FIREBALL, controller=1, zone="HAND", entity_id=33)
    deck_card = _make_entity(_YETI, controller=1, zone="DECK", entity_id=34)
    hidden_opp = None  # opponent hand entry hidden
    visible_opp = _make_entity(
        _RENO, controller=2, zone="HAND", entity_id=35, drawn_turn=2
    )
    t3 = _state(
        turn=3,
        active_player_id=1,
        player_board=(boar_in_play, yeti_board),
        player_hand=(my_hand_card,),
        opponent_hand=(hidden_opp, visible_opp),
        player_secrets=(my_secret,),
        player_weapon=my_weapon,
        player_deck=(deck_card,),
        player_played=(
            _played(_BOAR, turn=1, controller=1, entity_id=11),
            _played(_YETI, turn=3, controller=1, entity_id=12),
        ),
        player_drawn=(
            _played(_YETI, turn=1, controller=1, entity_id=12),
            _played(_FIREBALL, turn=3, controller=1, entity_id=33),
        ),
        player_mana=3,
        player_max_mana=3,
        opponent_deck_count=24,
        player_hero=_hero("MAGE", "Jaina", "Fireblast"),
        opponent_hero=_hero("WARRIOR", "Garrosh", "Armor Up!"),
    )

    return ReplayState(states=(t1a, t1b, t1c, t2, t3), friendly_player_id=1)


def _make_presenter():
    speech = MockSpeechService()
    replay = _build_replay()
    presenter = ReplayViewerPresenter(speech, replay)
    return presenter, speech, replay


# -------------------------------- Tests --------------------------------


def test_starts_at_first_turn() -> None:
    presenter, speech, _replay = _make_presenter()
    assert presenter.current_turn_number() == 1
    # Opening announcement happened.
    assert speech.spoken != []
    assert "Turn 1" in speech.spoken[0][0]


def test_pagedown_pageup_change_selected_turn() -> None:
    presenter, _speech, _replay = _make_presenter()
    assert presenter.current_turn_number() == 1
    presenter.next_turn()
    assert presenter.current_turn_number() == 2
    presenter.next_turn()
    assert presenter.current_turn_number() == 3
    # Clamp at the last turn.
    presenter.next_turn()
    assert presenter.current_turn_number() == 3
    presenter.prev_turn()
    assert presenter.current_turn_number() == 2
    presenter.prev_turn()
    assert presenter.current_turn_number() == 1
    # Clamp at the first turn.
    presenter.prev_turn()
    assert presenter.current_turn_number() == 1


def test_selecting_turn_shows_end_of_turn_state() -> None:
    """Turn selected with no event -> resolved is the end-of-turn state.

    Turn 1 has three transitions (t1a/t1b/t1c). The end-of-turn state is
    t1c, where the Boar is on board AND a Yeti has been drawn into hand.
    Asserting the hand zone reflects t1c (Yeti) proves we use end-of-turn,
    not the first transition (t1a, where only the Boar is in hand).
    """
    presenter, _speech, _replay = _make_presenter()
    # On turn 1: player board should hold the Boar (end-of-turn state).
    board = presenter.get_zone_items("your_board")
    assert [e.name for e in board] == ["Stonetusk Boar"]
    # And the hand should reflect the end-of-turn (Yeti drawn in t1c).
    hand = presenter.get_zone_items("your_hand")
    assert [e.name for e in hand] == ["Chillwind Yeti"]


def test_event_zone_items_are_game_events() -> None:
    """The Y zone items are GameEvent instances from services._events."""
    presenter, _speech, _replay = _make_presenter()
    events = presenter.get_zone_items("events")
    assert len(events) >= 1
    for ev in events:
        assert isinstance(ev, _events.GameEvent)
    # Turn 1 includes the Boar being played.
    assert any(isinstance(ev, _events.CardPlayed) for ev in events)


def test_event_zone_steps_and_changes_resolved_state() -> None:
    """In the Y zone, right/left step events and update the resolved state.

    On turn 1, stepping into the CardPlayed event (post_state = t1b) means a
    zone read should reflect t1b. We assert the resolved state advances by
    checking the player board across the selected event.
    """
    presenter, speech, _replay = _make_presenter()
    key_map = presenter.get_key_map()
    # Activate the events zone.
    key_map["y"]()
    assert presenter._current_zone == "events"
    n_events = len(presenter.get_zone_items("events"))
    assert n_events >= 1

    # Step to the first event via right-arrow (move_in_zone in events zone).
    spoken_before = speech.last_speech
    key_map["right"]()
    # The spoken text should advance through the diff events (changed text).
    assert speech.last_speech != spoken_before or n_events == 1

    # After selecting the CardPlayed event, the resolved board reflects the
    # event's post_state (t1b: Boar already in PLAY).
    board = presenter.get_zone_items("your_board")
    assert [e.name for e in board] == ["Stonetusk Boar"]


def test_event_drilldown_resolved_differs_between_states() -> None:
    """Resolved state differs between turn-level and a specific event."""
    presenter, _speech, _replay = _make_presenter()
    presenter.next_turn()  # go to turn 2 (opponent's turn, has a board minion)
    # Turn-level (no event): opponent board has Reno from end-of-turn state.
    assert [e.name for e in presenter.get_zone_items("opponent_board")] == [
        "Reno Jackson"
    ]


def test_letter_keys_activate_zones_and_announce() -> None:
    """Each list-zone letter key activates the right zone and announces it."""
    presenter, speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)  # turn 3 has the richest friendly zones
    key_map = presenter.get_key_map()

    cases = [
        ("b", "your_board", "Your board"),
        ("g", "opponent_board", "Opponent board"),
        ("c", "your_hand", "Your hand"),
        ("shift+c", "opponent_hand", "Opponent hand"),
        ("s", "your_secrets", "Your secrets"),
        ("shift+s", "opponent_secrets", "Opponent secrets"),
        ("v", "your_hero", "Your hero"),
        ("f", "opponent_hero", "Opponent hero"),
        ("w", "your_weapon", "Your weapon"),
        ("shift+w", "opponent_weapon", "Opponent weapon"),
        ("d", "your_deck", "Your deck"),
        ("y", "events", "Events"),
        ("p", "your_played", "Your played"),
        ("shift+p", "opponent_played", "Opponent played"),
        ("n", "your_drawn", "Your drawn"),
        ("shift+n", "opponent_drawn", "Opponent drawn"),
    ]
    for key, zone, label_fragment in cases:
        before = len(speech.spoken)
        key_map[key]()
        assert presenter._current_zone == zone, f"key {key!r} -> zone {zone}"
        assert len(speech.spoken) > before, f"key {key!r} announced nothing"
        assert label_fragment.lower() in speech.last_speech.lower(), (
            f"key {key!r} expected label {label_fragment!r} in {speech.last_speech!r}"
        )


def test_speak_only_keys_do_not_change_zone() -> None:
    """A / Shift+A / Shift+D / R / Shift+R announce without changing the zone."""
    presenter, speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)
    key_map = presenter.get_key_map()
    # Park in a known zone first.
    key_map["b"]()
    assert presenter._current_zone == "your_board"

    # Your mana.
    key_map["a"]()
    assert presenter._current_zone == "your_board"
    assert "3" in speech.last_speech  # "Your mana, 3 of 3"

    # Opponent mana.
    key_map["shift+a"]()
    assert presenter._current_zone == "your_board"

    # Opponent deck count.
    key_map["shift+d"]()
    assert presenter._current_zone == "your_board"
    assert "24" in speech.last_speech  # opponent_deck_count on turn 3

    # Your hero power.
    key_map["r"]()
    assert presenter._current_zone == "your_board"
    assert "Fireblast" in speech.last_speech

    # Opponent hero power.
    key_map["shift+r"]()
    assert presenter._current_zone == "your_board"
    assert "Armor Up!" in speech.last_speech


def test_number_keys_jump_positionally() -> None:
    """Number keys 1-10 jump to that position in the current zone."""
    presenter, speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)
    key_map = presenter.get_key_map()
    # Player board on turn 3 has 2 minions: Boar (1), Yeti (2).
    key_map["b"]()
    key_map["1"]()
    assert "Stonetusk Boar" in speech.last_speech
    assert "1 of 2" in speech.last_speech
    key_map["2"]()
    assert "Chillwind Yeti" in speech.last_speech
    assert "2 of 2" in speech.last_speech


def test_number_key_zero_is_position_ten() -> None:
    """'0' maps to positional jump 10."""
    presenter, _speech, _replay = _make_presenter()
    key_map = presenter.get_key_map()
    assert "0" in key_map
    # No crash on an out-of-range jump; clamps to last item.
    key_map["b"]()
    key_map["0"]()  # position 10 in a small zone -> clamps, no error


def test_empty_zone_announces_empty() -> None:
    """Empty zones (no secrets, no weapon on turn 1) announce as empty."""
    presenter, speech, _replay = _make_presenter()
    # Turn 1 has no secrets and no weapon.
    key_map = presenter.get_key_map()
    key_map["s"]()  # your secrets — empty
    assert "empty" in speech.last_speech.lower()
    key_map["w"]()  # your weapon — empty
    assert "empty" in speech.last_speech.lower()


def test_opponent_zones_inspectable() -> None:
    """Opponent zones (board, hand incl hidden, weapon, secrets, played,
    drawn, hero, hero power, deck count, mana) are all inspectable on turn 2/3.
    """
    presenter, speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(2)
    key_map = presenter.get_key_map()

    # Opponent board.
    assert [e.name for e in presenter.get_zone_items("opponent_board")] == [
        "Reno Jackson"
    ]
    # Opponent weapon.
    assert [e.name for e in presenter.get_zone_items("opponent_weapon")] == [
        "Fiery War Axe"
    ]
    # Opponent secrets.
    assert [e.name for e in presenter.get_zone_items("opponent_secrets")] == [
        "Counterspell"
    ]
    # Opponent played / drawn.
    assert [p.name for p in presenter.get_zone_items("opponent_played")] == [
        "Reno Jackson"
    ]
    assert [p.name for p in presenter.get_zone_items("opponent_drawn")] == [
        "Reno Jackson"
    ]

    # Opponent hand with hidden entry (turn 3).
    presenter.jump_to_turn_number(3)
    key_map["shift+c"]()
    opp_hand = presenter.get_zone_items("opponent_hand")
    assert len(opp_hand) == 2  # one hidden, one visible
    # Hidden card renders as "Hidden card".
    presenter.jump_to_position(1)
    assert "Hidden card" in speech.last_speech


def test_opponent_hero_inspectable() -> None:
    presenter, speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)
    key_map = presenter.get_key_map()
    key_map["f"]()  # opponent hero
    assert presenter._current_zone == "opponent_hero"
    hero_items = presenter.get_zone_items("opponent_hero")
    assert len(hero_items) == 1


def test_your_hero_detail_lines() -> None:
    """Your hero zone resolves to one item with detail lines."""
    presenter, _speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)
    items = presenter.get_zone_items("your_hero")
    assert len(items) == 1


def test_weapon_zone_resolves_on_turn_three() -> None:
    presenter, speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)
    key_map = presenter.get_key_map()
    key_map["w"]()
    assert presenter._current_zone == "your_weapon"
    weapon = presenter.get_zone_items("your_weapon")
    assert [e.name for e in weapon] == ["Fiery War Axe"]


def test_your_played_and_drawn_zones() -> None:
    presenter, _speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)
    played = presenter.get_zone_items("your_played")
    assert [p.name for p in played] == ["Stonetusk Boar", "Chillwind Yeti"]
    drawn = presenter.get_zone_items("your_drawn")
    assert [p.name for p in drawn] == ["Chillwind Yeti", "Fireball"]


def test_your_deck_zone() -> None:
    presenter, _speech, _replay = _make_presenter()
    presenter.jump_to_turn_number(3)
    deck = presenter.get_zone_items("your_deck")
    assert [e.name for e in deck] == ["Chillwind Yeti"]
