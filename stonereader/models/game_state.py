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


@dataclass(frozen=True)
class GameState:
    """Represents a moment in game time."""

    turn: int
    active_player_id: int
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
