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
from stonereader.spoken import card_label, class_name

# The preset table also names hero-power-use and trigger/deathrattle events.
# GameState does not yet retain the packet/block context needed to derive them.


def phrase(event: GameEvent, state: GameState) -> str | None:
    """Return the shared subject-first phrase, or ``None`` for filtered noise."""
    if isinstance(event, GameStarted):
        return (
            f"Game started, {class_name(event.player_class)} versus "
            f"{class_name(event.opponent_class)}"
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
        # The Replay Viewer's turn prefix already names the side and number.
        return "Start of turn"
    if isinstance(event, MulliganDone):
        return "Mulligan complete"
    if isinstance(event, CardDrawn):
        if event.controller != 1:
            return "Opponent drew a card"
        return f"You drew {card_label(event.name, event.card_id, event.base_card)}"
    if isinstance(event, CardPlayed):
        subject = "You" if event.controller == 1 else "Opponent"
        name = card_label(event.name, event.card_id, event.base_card)
        return f"{subject} played {name}"
    if isinstance(event, SecretPlayed):
        subject = "You" if event.controller == 1 else "Opponent"
        return f"{subject} played a secret"
    if isinstance(event, SecretRevealed):
        return f"Secret revealed, {card_label(event.name, event.card_id)}"
    if isinstance(event, CardRevealed):
        return f"{card_label(event.name, event.card_id, event.base_card)} revealed"
    if isinstance(event, CardRemoved):
        name = _entity_name(state, event.entity_id, "Unknown card")
        entity = _entity(state, event.entity_id)
        # A weapon goes to the graveyard only when destroyed: broken, or
        # replaced by a newly equipped one.
        if (
            entity is not None
            and entity.card_type == "WEAPON"
            and entity.zone == "GRAVEYARD"
        ):
            return f"{name} destroyed"
        return f"{name} removed"
    if isinstance(event, AttackStarted):
        attacker = _entity_name(state, event.attacker_entity_id, "a minion")
        target = _entity_name(state, event.defender_entity_id, "a minion")
        return f"{attacker} attacks {target}"
    if isinstance(event, MinionDied):
        return f"{card_label(event.name, event.card_id)} died"
    if isinstance(event, DamageDealt):
        # DAMAGE is a cumulative tag value, not a trustworthy per-hit amount.
        return None
    return None


def _entity_name(state: GameState, entity_id: int, fallback: str) -> str:
    entity = _entity(state, entity_id)
    if entity is None:
        return fallback
    if entity.name:
        return entity.name
    if entity.base_card is not None:
        return entity.base_card.name
    # Only a hidden entity, with no id, takes the caller's fallback.
    return card_label("", entity.card_id) if entity.card_id else fallback


def _entity(state: GameState, entity_id: int) -> GameEntity | None:
    return next(
        (entity for entity in _entities(state) if entity.entity_id == entity_id),
        None,
    )


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
