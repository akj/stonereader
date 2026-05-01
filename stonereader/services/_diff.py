"""Pure GameState-pair diff (issue #4).

Derives a deterministic sequence of GameEvents from two GameState snapshots.
No I/O, no clock, no engine reference: imports only from stonereader.models
and stonereader.services._events. The same function serves Live game (engine
apply → new state → diff vs previous) and the future Replay viewer
(states[i] vs states[i+1]) with no asymmetry.

Output ordering (deterministic):
  1. Cold-start lifecycle: GameStarted (when prev is None and curr.game_state="RUNNING").
     Cold start emits *only* GameStarted; per-entity diffing requires a prev.
  2. End-of-game lifecycle: GameEnded (RUNNING → COMPLETE/ABANDONED).
  3. Turn lifecycle: TurnChanged, MulliganDone.
  4. Combat start: AttackStarted.
  5. Per-entity transitions, ordered by ascending entity_id. For each entity,
     at most one zone-class event (CardDrawn | CardPlayed | MinionDied |
     CardRemoved) followed by CardRevealed (if card_id became visible) and
     DamageDealt (if DAMAGE tag changed under an open ATTACK or POWER block).

Pure timestamps: every emitted event carries timestamp=0.0 — diff has no
clock. Consumers that want wall-clock should associate timestamps at the
state-publication layer, not derive them here.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

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
    TurnChanged,
)

_TERMINAL_GAME_STATES = ("COMPLETE", "ABANDONED")
_TERMINAL_ENTITY_ZONES = ("GRAVEYARD", "REMOVEDFROMGAME")


def _iter_entities(state: GameState) -> Iterable[GameEntity]:
    """Yield every GameEntity reachable from the published state."""
    yield from state.player_board
    yield from state.opponent_board
    yield from state.player_hand
    for ent in state.opponent_hand:
        if ent is not None:
            yield ent
    yield from state.player_secrets
    yield from state.opponent_secrets
    yield from state.player_deck
    if state.player_weapon is not None:
        yield state.player_weapon
    if state.opponent_weapon is not None:
        yield state.opponent_weapon


def _index_entities(state: GameState) -> Dict[int, GameEntity]:
    """Build entity_id → GameEntity map. Last writer wins on rare duplicates."""
    return {ent.entity_id: ent for ent in _iter_entities(state)}


def diff(prev: Optional[GameState], curr: GameState) -> Sequence[GameEvent]:
    events: List[GameEvent] = []
    turn = curr.turn

    if prev is None:
        if curr.game_state == "RUNNING":
            events.append(
                GameStarted(
                    timestamp=0.0,
                    turn=turn,
                    player_class=curr.player_hero.hero_class,
                    opponent_class=curr.opponent_hero.hero_class,
                    game_type=curr.game_type,
                    format_type=curr.format_type,
                )
            )
        return events

    if prev.game_state == "RUNNING" and curr.game_state in _TERMINAL_GAME_STATES:
        events.append(
            GameEnded(
                timestamp=0.0,
                turn=turn,
                player_playstate=curr.player_playstate,
                opponent_playstate=curr.opponent_playstate,
            )
        )

    if prev.active_player_id != curr.active_player_id:
        events.append(
            TurnChanged(
                timestamp=0.0,
                turn=turn,
                active_player_id=curr.active_player_id,
            )
        )

    if not prev.mulligan_complete and curr.mulligan_complete:
        events.append(MulliganDone(timestamp=0.0, turn=turn))

    if prev.attack_in_progress is None and curr.attack_in_progress is not None:
        aip = curr.attack_in_progress
        events.append(
            AttackStarted(
                timestamp=0.0,
                turn=turn,
                attacker_entity_id=aip.attacker_entity_id,
                defender_entity_id=aip.defender_entity_id,
                attacker_controller=aip.attacker_controller,
            )
        )

    damage_block_open = curr.attack_in_progress is not None or (
        bool(curr.block_stack) and curr.block_stack[-1] == "POWER"
    )

    prev_entities = _index_entities(prev)
    curr_entities = _index_entities(curr)
    for eid in sorted(curr_entities):
        curr_ent = curr_entities[eid]
        prev_ent = prev_entities.get(eid)
        prev_zone = prev_ent.zone if prev_ent is not None else ""

        if curr_ent.zone == "HAND" and prev_zone != "HAND":
            events.append(
                CardDrawn(
                    timestamp=0.0,
                    turn=turn,
                    entity_id=curr_ent.entity_id,
                    card_id=curr_ent.card_id,
                    base_card=curr_ent.base_card,
                    name=curr_ent.name,
                    controller=curr_ent.controller,
                )
            )
        elif (
            curr_ent.zone == "PLAY"
            and prev_zone != "PLAY"
            and curr.block_stack
            and curr.block_stack[-1] == "PLAY"
        ):
            events.append(
                CardPlayed(
                    timestamp=0.0,
                    turn=turn,
                    entity_id=curr_ent.entity_id,
                    card_id=curr_ent.card_id,
                    base_card=curr_ent.base_card,
                    name=curr_ent.name,
                    controller=curr_ent.controller,
                )
            )
        elif curr_ent.zone == "GRAVEYARD" and prev_zone == "PLAY":
            events.append(
                MinionDied(
                    timestamp=0.0,
                    turn=turn,
                    entity_id=curr_ent.entity_id,
                    card_id=curr_ent.card_id,
                    name=curr_ent.name,
                    controller=curr_ent.controller,
                )
            )
        elif (
            curr_ent.zone in _TERMINAL_ENTITY_ZONES
            and prev_zone not in _TERMINAL_ENTITY_ZONES
            and prev_zone != "PLAY"
        ):
            events.append(
                CardRemoved(
                    timestamp=0.0,
                    turn=turn,
                    entity_id=curr_ent.entity_id,
                    card_id=curr_ent.card_id,
                    controller=curr_ent.controller,
                )
            )

        if prev_ent is not None and not prev_ent.card_id and curr_ent.card_id:
            events.append(
                CardRevealed(
                    timestamp=0.0,
                    turn=turn,
                    entity_id=curr_ent.entity_id,
                    card_id=curr_ent.card_id,
                    base_card=curr_ent.base_card,
                    name=curr_ent.name,
                    controller=curr_ent.controller,
                )
            )

        if damage_block_open:
            curr_damage = int(curr_ent.tags.get("DAMAGE", 0) or 0)
            prev_damage = (
                int(prev_ent.tags.get("DAMAGE", 0) or 0) if prev_ent is not None else 0
            )
            if curr_damage != prev_damage:
                events.append(
                    DamageDealt(
                        timestamp=0.0,
                        turn=turn,
                        target_entity_id=curr_ent.entity_id,
                        amount=curr_damage,
                        target_controller=curr_ent.controller,
                    )
                )

    return events
