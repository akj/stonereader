"""Typed events emitted by the game engine (D-06).

All events inherit from GameEvent. They are frozen dataclasses; subscribers
receive them via GameTracker.subscribe(callback). Each event carries enough
payload for Phase 3 announcements without requiring the subscriber to read
the GameState.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from stonereader.models.card import Card


@dataclass(frozen=True)
class GameEvent:
    """Base type for all engine-emitted events.

    timestamp: monotonic seconds since engine start
    turn: the in-game turn number when the event occurred (0 before mulligan resolution)
    """

    timestamp: float
    turn: int


# ------------------------------------------------------------------ Game lifecycle


@dataclass(frozen=True)
class GameStarted(GameEvent):
    """Emitted once per game when CREATE_GAME has been fully ingested and players are known.

    Fields beyond timestamp+turn:
      player_class: hero class for the local player (e.g. "MAGE")
      opponent_class: hero class for the opponent
      game_type: "RANKED" | "CASUAL" | "ARENA" | "BATTLEGROUNDS" | "" (unknown)
      format_type: "STANDARD" | "WILD" | "CLASSIC" | "TWIST" | "" (unknown)
    """

    player_class: str
    opponent_class: str
    game_type: str
    format_type: str


@dataclass(frozen=True)
class GameEnded(GameEvent):
    """Emitted when PLAYSTATE WON/LOST/TIED is observed for the local player."""

    player_playstate: str  # "WON" | "LOST" | "TIED"
    opponent_playstate: str


# ------------------------------------------------------------------ Turn lifecycle


@dataclass(frozen=True)
class TurnChanged(GameEvent):
    """Emitted whenever active_player flips."""

    active_player_id: int  # 1 = friendly, 2 = opponent


@dataclass(frozen=True)
class MulliganDone(GameEvent):
    """Emitted when both players finish their mulligan."""

    # No additional payload; the GameState snapshot will reflect starting_hand.


# ------------------------------------------------------------------ Card movement


@dataclass(frozen=True)
class CardDrawn(GameEvent):
    """Emitted when a card is drawn by either player."""

    entity_id: int
    card_id: str
    base_card: Optional[Card]
    name: str  # cached for speech ("" if hidden)
    controller: int  # 1 = friendly, 2 = opponent


@dataclass(frozen=True)
class CardPlayed(GameEvent):
    """Emitted when a card is played from hand."""

    entity_id: int
    card_id: str
    base_card: Optional[Card]
    name: str
    controller: int


@dataclass(frozen=True)
class CardRevealed(GameEvent):
    """Emitted when a previously-hidden card becomes visible (e.g., opponent secret triggers, joust reveal)."""

    entity_id: int
    card_id: str
    base_card: Optional[Card]
    name: str
    controller: int


@dataclass(frozen=True)
class CardRemoved(GameEvent):
    """Emitted when an entity leaves play in a way that doesn't fit Played/Drawn/Died."""

    entity_id: int
    card_id: str
    controller: int


# ------------------------------------------------------------------ Combat


@dataclass(frozen=True)
class AttackStarted(GameEvent):
    """Emitted at BlockType.ATTACK start. Payload identifies attacker/defender."""

    attacker_entity_id: int
    defender_entity_id: int
    attacker_controller: int


@dataclass(frozen=True)
class MinionDied(GameEvent):
    """Emitted when an entity moves to GRAVEYARD from PLAY zone."""

    entity_id: int
    card_id: str
    name: str
    controller: int


@dataclass(frozen=True)
class DamageDealt(GameEvent):
    """Emitted when a TagChange of DAMAGE is observed during a BlockType.ATTACK or POWER block."""

    target_entity_id: int
    amount: int
    target_controller: int
