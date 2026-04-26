"""Verify D-08 extension to GameState, Hero, GameEntity, and the new PlayedCard."""
from __future__ import annotations

import dataclasses

from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard


def _hero(name="P1"):
    return Hero(id=name, name=name, health=30, armor=0, hero_power="HP")


def _empty_state():
    return GameState(
        turn=1,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=_hero("P1"),
        opponent_hero=_hero("P2"),
    )


def test_hero_has_hero_class_default():
    h = _hero()
    assert h.hero_class == ""


def test_hero_hero_class_can_be_set():
    h = Hero(id="x", name="x", health=30, armor=0, hero_power="HP", hero_class="MAGE")
    assert h.hero_class == "MAGE"


def test_game_entity_has_drawn_turn_default():
    e = GameEntity(
        entity_id=1, card_id="X", base_card=None, name="X",
        cost=0, current_attack=0, current_health=0,
        card_type="MINION", zone="HAND", zone_position=1, controller=1,
    )
    assert e.drawn_turn == -1


def test_played_card_is_frozen_dataclass():
    pc = PlayedCard(entity_id=1, card_id="X", base_card=None, name="X", turn=2, controller=1)
    assert dataclasses.is_dataclass(pc)
    # frozen
    try:
        pc.turn = 3  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("PlayedCard must be frozen")


def test_game_state_new_fields_default():
    s = _empty_state()
    assert s.player_deck == ()
    assert s.player_played == ()
    assert s.opponent_played == ()
    assert s.player_drawn == ()
    assert s.opponent_drawn == ()
    assert s.game_state == "RUNNING"
    assert s.game_type == ""
    assert s.format_type == ""
    assert s.player_playstate == ""
    assert s.opponent_playstate == ""
    assert s.player_starting_hand == ()


def test_game_state_collections_are_tuples():
    # Pitfall 4: must be Tuple, never List, to preserve immutability
    pc = PlayedCard(entity_id=1, card_id="X", base_card=None, name="X", turn=2, controller=1)
    s = dataclasses.replace(_empty_state(), opponent_played=(pc,))
    assert isinstance(s.opponent_played, tuple)


def test_existing_construction_still_works():
    # Phase 1 / existing code constructs GameState with no new fields — must keep working.
    s = _empty_state()
    assert s.turn == 1
    assert s.player_hero.name == "P1"
