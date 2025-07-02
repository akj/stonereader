from typing import List, Optional, Tuple

class Card:
    """Represents a Hearthstone card with accessibility metadata"""
    id: str
    name: str
    cost: int
    attack: Optional[int]
    health: Optional[int]
    text: str
    rarity: str
    card_class: str
    card_type: str
    
    def to_speech_text(self, verbosity='medium') -> str:
        """Returns screen reader friendly text representation"""
        return ''

class Deck:
    """Represents a Hearthstone deck"""
    name: str
    format: str
    cards: List[Tuple[Card, int]]  # (card, count)
    hero_class: str
    
class Hero:
    """Represents a Hearthstone hero"""
    id: str
    name: str
    health: int
    armor: int
    hero_power: str

class GameState:
    """Represents a moment in game time"""
    turn: int
    player_board: List[Card]
    opponent_board: List[Card]
    player_hand: List[Card]
    opponent_hand: List[Optional[Card]]  # None for hidden cards
    player_hero: Hero
    opponent_hero: Hero
