"""Game state models for StoneReader.

Frozen dataclasses representing Hearthstone game entities, heroes, and state
snapshots. All models are immutable by design — construct new instances rather
than mutating existing ones.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from stonereader.models.card import Card


@dataclass(frozen=True)
class Hero:
    """Represents a Hearthstone hero."""

    id: str
    name: str
    health: int
    armor: int
    hero_power: str
    # NEW (Phase 2): hero class for matchup announcements (LIVE-08, GameStarted payload)
    hero_class: str = ""  # "MAGE", "WARRIOR", etc. (matches Card.card_class enum)


@dataclass(frozen=True)
class GameEntity:
    """Represents an entity on board/hand at a snapshot."""

    entity_id: int
    card_id: str
    base_card: Optional[Card]
    name: str
    cost: int
    current_attack: int
    current_health: int
    card_type: str
    zone: str
    zone_position: int
    controller: int
    exhausted: bool = False
    enchantment_names: Tuple[str, ...] = ()
    tags: Dict[str, Any] = field(default_factory=dict)
    # NEW (Phase 2): turn the entity was drawn into hand (for DIFF-01 deferred,
    # but cheap to capture now). 0 = mulligan; -1 = unknown (opponent hidden).
    drawn_turn: int = -1


@dataclass(frozen=True)
class PlayedCard:
    """A card played during the game, with the turn it was played on.

    Mirrors HDT's CardsPlayedThisMatch entry and Firestone's ShortCardWithTurn.
    Used to drive LIVE-04 (opponent played-in-order).
    """

    entity_id: int  # the entity at time of play (may have left board)
    card_id: str  # current card_id at time of play
    base_card: Optional[Card]  # resolved Card (None if hidden at play time)
    name: str  # convenience for speech
    turn: int  # the turn the play happened (0 = mulligan-into-hand)
    controller: int  # 1 = friendly, 2 = opponent (matches PlayerID semantics)


@dataclass(frozen=True)
class GameState:
    """Represents a moment in game time."""

    turn: int
    active_player_id: int

    # Zone snapshots (existing — DO NOT REORDER)
    player_board: Tuple[GameEntity, ...]
    opponent_board: Tuple[GameEntity, ...]
    player_hand: Tuple[GameEntity, ...]
    opponent_hand: Tuple[Optional[GameEntity], ...]
    player_hero: Hero
    opponent_hero: Hero
    player_weapon: Optional[GameEntity] = None
    opponent_weapon: Optional[GameEntity] = None
    player_secrets: Tuple[GameEntity, ...] = ()
    opponent_secrets: Tuple[GameEntity, ...] = ()
    player_mana: int = 0
    player_max_mana: int = 0
    opponent_mana: int = 0
    opponent_max_mana: int = 0
    player_deck_count: int = 0
    opponent_deck_count: int = 0

    # NEW (Phase 2) — drives LIVE-02 player remaining deck
    player_deck: Tuple[GameEntity, ...] = ()
    # opponent_deck NOT exposed — Hearthstone never reveals it; count only.

    # NEW (Phase 2) — drives LIVE-04 opponent played in order
    player_played: Tuple[PlayedCard, ...] = ()
    opponent_played: Tuple[PlayedCard, ...] = ()

    # NEW (Phase 2) — drives LIVE-03 cards-drawn history
    player_drawn: Tuple[
        PlayedCard, ...
    ] = ()  # uses PlayedCard for shape parity (turn = draw turn)
    opponent_drawn: Tuple[
        PlayedCard, ...
    ] = ()  # opponent draws may have unknown card_id

    # NEW (Phase 2) — drives game lifecycle queries
    game_state: str = "RUNNING"  # "RUNNING" | "COMPLETE"
    game_type: str = ""  # "RANKED" | "CASUAL" | "ARENA" | "BATTLEGROUNDS" | ""
    format_type: str = ""  # "STANDARD" | "WILD" | "CLASSIC" | "TWIST" | ""
    player_playstate: str = ""  # "" | "PLAYING" | "WON" | "LOST" | "TIED"
    opponent_playstate: str = ""

    # NEW (Phase 2) — drives auto-deck-detect (LIVE-08, deferred to Phase 3 but cheap to capture)
    player_starting_hand: Tuple[GameEntity, ...] = ()
