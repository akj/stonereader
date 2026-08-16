from __future__ import annotations

from dataclasses import replace

from stonereader.models.card import Card
from stonereader.models.game_state import GameEntity, GameState, Hero
from stonereader.models.replay import ReplayState
from stonereader.services._events import CardPlayed, GameStarted, TurnChanged
from stonereader.surfaces._replay_turns import turns


def _hero(name: str, hero_class: str) -> Hero:
    return Hero("hero", name, 30, 0, "", hero_class)


def _card() -> Card:
    return Card(
        "BOAR",
        1,
        "Boar",
        1,
        1,
        1,
        "",
        "COMMON",
        "NEUTRAL",
        "MINION",
    )


def _entity(zone: str) -> GameEntity:
    card = _card()
    return GameEntity(10, card.id, card, card.name, 1, 1, 1, "MINION", zone, 1, 1)


def _state(turn: int, active: int, **overrides) -> GameState:
    values = {
        "player_board": (),
        "opponent_board": (),
        "player_hand": (),
        "opponent_hand": (),
        "player_hero": _hero("Jaina", "MAGE"),
        "opponent_hero": _hero("Garrosh", "WARRIOR"),
    }
    values.update(overrides)
    return GameState(turn=turn, active_player_id=active, **values)


def test_groups_turn_zero_as_turn_one_prelude_and_uses_last_state() -> None:
    opening = _state(0, 1, player_hand=(_entity("HAND"),))
    turn_one_start = replace(opening, turn=1, active_player_id=2)
    turn_one_end = replace(
        turn_one_start,
        player_hand=(),
        player_board=(_entity("PLAY"),),
        block_stack=("PLAY",),
    )
    turn_two = replace(turn_one_end, turn=2, active_player_id=1, block_stack=())

    result = turns(
        ReplayState(
            states=(opening, turn_one_start, turn_one_end, turn_two),
            friendly_player_id=2,
        )
    )

    assert [turn.number for turn in result] == [1, 2]
    assert result[0].state is turn_one_end
    assert result[1].state is turn_two
    assert [turn.is_friendly for turn in result] == [True, False]
    assert any(isinstance(event, GameStarted) for event in result[0].events)
    assert any(isinstance(event, CardPlayed) for event in result[0].events)
    assert any(isinstance(event, TurnChanged) for event in result[1].events)


def test_empty_replay_has_no_turns() -> None:
    assert turns(ReplayState(states=(), friendly_player_id=1)) == []
