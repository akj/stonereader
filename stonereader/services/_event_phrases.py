"""One user-facing phrasing seam for derived game events (ADR-0010)."""

from __future__ import annotations

from collections.abc import Iterable

from stonereader.models.game_state import GameEntity, GameState
from stonereader.services._events import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    CardRemoved,
    CardRevealed,
    DamageDealt,
    GameEnded,
    GameEvent,
    GameStarted,
    MinionDied,
    MulliganDone,
    SecretPlayed,
    SecretRevealed,
    TurnChanged,
)

# The preset table also names hero-power-use and trigger/deathrattle events.
# GameState does not yet retain the packet/block context needed to derive them.


def phrase(event: GameEvent, state: GameState) -> str | None:
    """Return the shared subject-first phrase, or ``None`` for filtered noise."""
    if isinstance(event, GameStarted):
        return (
            f"Game started, {_spoken_enum(event.player_class)} versus "
            f"{_spoken_enum(event.opponent_class)}"
        )
    if isinstance(event, GameEnded):
        playstate = state.player_playstate or event.player_playstate
        result = {
            "WON": "won",
            "LOST": "lost",
            "CONCEDED": "lost",
            "TIED": "tied",
        }.get(playstate.upper(), "tied")
        return f"Game over, {result}"
    if isinstance(event, TurnChanged):
        side = "yours" if event.active_player_id == 1 else "opponent's"
        return f"Turn {event.turn}, {side}"
    if isinstance(event, MulliganDone):
        return "Mulligan complete"
    if isinstance(event, CardDrawn):
        if event.controller != 1:
            return "Opponent drew a card"
        return f"You drew {_event_name(event.name)}"
    if isinstance(event, CardPlayed):
        subject = "You" if event.controller == 1 else "Opponent"
        return f"{subject} played {_event_name(event.name)}"
    if isinstance(event, SecretPlayed):
        subject = "You" if event.controller == 1 else "Opponent"
        return f"{subject} played a secret"
    if isinstance(event, SecretRevealed):
        return f"Secret revealed, {_event_name(event.name)}"
    if isinstance(event, CardRevealed):
        return f"{_event_name(event.name)} revealed"
    if isinstance(event, CardRemoved):
        return f"{_entity_name(state, event.entity_id, 'Unknown card')} removed"
    if isinstance(event, AttackStarted):
        attacker = _entity_name(state, event.attacker_entity_id, "a minion")
        target = _entity_name(state, event.defender_entity_id, "a minion")
        return f"{attacker} attacks {target}"
    if isinstance(event, MinionDied):
        return f"{_event_name(event.name)} died"
    if isinstance(event, DamageDealt):
        # DAMAGE is a cumulative tag value, not a trustworthy per-hit amount.
        return None
    return None


def _spoken_enum(value: str) -> str:
    if not value:
        return "Unknown"
    return {
        "DEATHKNIGHT": "Death Knight",
        "DEMONHUNTER": "Demon Hunter",
    }.get(value.upper(), value.replace("_", " ").title())


def _event_name(value: str) -> str:
    return value or "Unknown card"


def _entity_name(state: GameState, entity_id: int, fallback: str) -> str:
    for entity in _entities(state):
        if entity.entity_id == entity_id:
            return entity.name or (
                entity.base_card.name if entity.base_card is not None else fallback
            )
    return fallback


def _entities(state: GameState) -> Iterable[GameEntity]:
    yield from state.player_board
    yield from state.opponent_board
    yield from state.player_hand
    yield from (entity for entity in state.opponent_hand if entity is not None)
    yield from state.player_secrets
    yield from state.opponent_secrets
    yield from state.player_deck
    yield from state.graveyard
    if state.player_weapon is not None:
        yield state.player_weapon
    if state.opponent_weapon is not None:
        yield state.opponent_weapon
    if state.player_hero_entity is not None:
        yield state.player_hero_entity
    if state.opponent_hero_entity is not None:
        yield state.opponent_hero_entity
