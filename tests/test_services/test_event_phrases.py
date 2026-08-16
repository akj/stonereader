from __future__ import annotations

from stonereader.models.card import Card
from stonereader.models.game_state import GameEntity, GameState, Hero
from stonereader.services._event_phrases import phrase
from stonereader.services._events import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    CardRemoved,
    CardRevealed,
    DamageDealt,
    GameEnded,
    GameStarted,
    MinionDied,
    MulliganDone,
    TurnChanged,
)


def _card(card_id: str, name: str) -> Card:
    return Card(
        card_id,
        len(card_id),
        name,
        1,
        1,
        1,
        "",
        "COMMON",
        "NEUTRAL",
        "MINION",
    )


def _entity(entity_id: int, card: Card, controller: int) -> GameEntity:
    return GameEntity(
        entity_id,
        card.id,
        card,
        card.name,
        card.cost,
        card.attack or 0,
        card.health or 0,
        card.card_type,
        "PLAY",
        1,
        controller,
    )


def _state() -> GameState:
    attacker = _entity(10, _card("A", "Boar"), 1)
    target = _entity(20, _card("B", "Yeti"), 2)
    return GameState(
        turn=4,
        active_player_id=1,
        player_board=(attacker,),
        opponent_board=(target,),
        player_hand=(),
        opponent_hand=(),
        player_hero=Hero("p", "Jaina", 30, 0, "", "MAGE"),
        opponent_hero=Hero("o", "Garrosh", 30, 0, "", "WARRIOR"),
        player_playstate="LOST",
    )


def test_phrases_every_existing_event_type() -> None:
    state = _state()
    fireball = _card("F", "Fireball")
    cases = [
        (
            GameStarted(0, 0, "DEATHKNIGHT", "DEMONHUNTER", "RANKED", "STANDARD"),
            "Game started, Death Knight versus Demon Hunter",
        ),
        (GameEnded(0, 4, "WON", "LOST"), "Game over, lost"),
        (TurnChanged(0, 4, 1), "Turn 4, yours"),
        (TurnChanged(0, 4, 2), "Turn 4, opponent's"),
        (MulliganDone(0, 1), "Mulligan complete"),
        (CardDrawn(0, 4, 30, fireball.id, fireball, "Fireball", 1), "You drew Fireball"),
        (CardDrawn(0, 4, 31, "", None, "Secret", 2), "Opponent drew a card"),
        (CardPlayed(0, 4, 30, fireball.id, fireball, "Fireball", 1), "You played Fireball"),
        (CardPlayed(0, 4, 30, fireball.id, fireball, "Fireball", 2), "Opponent played Fireball"),
        (CardRevealed(0, 4, 30, fireball.id, fireball, "Fireball", 2), "Fireball revealed"),
        (CardRemoved(0, 4, 10, "A", 1), "Boar removed"),
        (AttackStarted(0, 4, 10, 20, 1), "Boar attacks Yeti"),
        (AttackStarted(0, 4, 99, 98, 1), "a minion attacks a minion"),
        (MinionDied(0, 4, 20, "B", "Yeti", 2), "Yeti died"),
    ]
    for event, expected in cases:
        assert phrase(event, state) == expected


def test_damage_is_filtered_as_cumulative_value_noise() -> None:
    assert phrase(DamageDealt(0, 4, 20, 3, 2), _state()) is None
