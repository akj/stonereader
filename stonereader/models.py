from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from hearthstone import deckstrings
from hearthstone.cardxml import load


@dataclass(frozen=True)
class Card:
    """Represents a Hearthstone card with complete tag access"""

    id: str
    dbf_id: int
    name: str
    cost: int
    attack: Optional[int]
    health: Optional[int]
    text: str
    rarity: str
    card_class: str
    card_type: str
    card_set: str = ""
    collectible: bool = True
    durability: Optional[int] = None

    # Store all card tags for flexible access
    tags: Dict[str, Any] = field(default_factory=dict)

    def has_tag(self, tag_name: str) -> bool:
        """Check if card has a specific tag"""
        if not self.tags:
            return False
        return bool(self.tags.get(tag_name, 0))

    def get_tag(self, tag_name: str, default=None):
        """Get the value of a specific tag"""
        if not self.tags:
            return default
        return self.tags.get(tag_name, default)

    @classmethod
    def from_cardxml(cls, cardxml_card):
        """Create Card instance from hearthstone library CardXML object"""

        # Convert all tags to string keys for easier access
        tags_dict = {}
        if hasattr(cardxml_card, "tags") and cardxml_card.tags:
            for tag_enum, value in cardxml_card.tags.items():
                # Store both enum name and numeric value
                tag_name = str(tag_enum).split(".")[-1]  # Get just the tag name
                tags_dict[tag_name] = value

        return cls(
            id=cardxml_card.id,
            dbf_id=cardxml_card.dbf_id if hasattr(cardxml_card, "dbf_id") else 0,
            name=cardxml_card.name or "",
            cost=cardxml_card.cost or 0,
            attack=cardxml_card.atk if cardxml_card.atk else None,
            health=cardxml_card.health if cardxml_card.health else None,
            text=cardxml_card.description or "",
            rarity=str(cardxml_card.rarity) if cardxml_card.rarity else "COMMON",
            card_class=str(cardxml_card.card_class)
            if cardxml_card.card_class
            else "NEUTRAL",
            card_type=str(cardxml_card.type) if cardxml_card.type else "MINION",
            card_set=str(cardxml_card.card_set) if cardxml_card.card_set else "",
            collectible=bool(cardxml_card.collectible),
            durability=cardxml_card.durability if cardxml_card.durability else None,
            tags=tags_dict,
        )

    def to_speech_text(self, verbosity: str = "normal") -> str:
        """Generate screen reader friendly text for this card"""
        if verbosity == "brief":
            return f"{self.name}, {self.cost} mana"

        parts = [f"{self.name}, {self.cost} mana cost"]

        if self.attack is not None and self.health is not None:
            parts.append(f"{self.attack} attack, {self.health} health")
        elif self.attack is not None:
            parts.append(f"{self.attack} attack")
        elif self.health is not None:
            parts.append(f"{self.health} health")

        if self.durability is not None:
            parts.append(f"{self.durability} durability")

        parts.append(f"{self.card_type.lower()}")

        if self.card_class != "NEUTRAL":
            parts.append(f"{self.card_class.lower()} class")

        if verbosity == "detailed" and self.text:
            parts.append(f"Text: {self.text}")

        return ", ".join(parts)


@dataclass(frozen=True)
class Deck:
    """Represents a Hearthstone deck"""

    name: str
    format: str
    cards: Tuple[Tuple[Card, int], ...]  # Immutable tuple of (card, count)
    hero_class: str
    deckstring: str = ""

    def total_cards(self) -> int:
        """Returns total number of cards in deck"""
        return sum(count for _, count in self.cards)

    def average_cost(self) -> float:
        """Returns average mana cost of cards in deck"""
        if not self.cards:
            return 0.0

        total_cost = sum(card.cost * count for card, count in self.cards)
        total_cards = self.total_cards()
        return total_cost / total_cards if total_cards > 0 else 0.0

    def cards_by_cost(self) -> Dict[int, List[Tuple[Card, int]]]:
        """Returns cards grouped by mana cost"""
        cost_groups = {}
        for card, count in self.cards:
            cost = card.cost
            if cost not in cost_groups:
                cost_groups[cost] = []
            cost_groups[cost].append((card, count))
        return cost_groups

    @property
    def total_dust_cost(self) -> int:
        """Returns total dust cost to craft all cards in deck"""
        dust_costs = {"COMMON": 40, "RARE": 100, "EPIC": 400, "LEGENDARY": 1600}

        total_dust = 0
        for card, count in self.cards:
            dust_per_card = dust_costs.get(card.rarity, 0)
            total_dust += dust_per_card * count
        return total_dust

    @classmethod
    def from_deckstring(
        cls, deckstring: str, card_db: "CardDatabase", name: str = "Imported Deck"
    ):
        """Create Deck instance from hearthstone deckstring"""
        # Parse the deckstring - returns (cards, heroes, format, sideboard)
        cards_data, heroes_data, format_data, _ = deckstrings.parse_deckstring(
            deckstring
        )

        # Convert to our Card objects using the provided database
        # Note: cards_data contains DBF IDs, not string IDs
        cards = []
        missing_cards = []
        for dbf_id, count in cards_data:
            card = card_db.get_card_by_dbf_id(dbf_id)
            if card:
                cards.append((card, count))
            else:
                missing_cards.append(dbf_id)

        if missing_cards:
            raise ValueError(f"Missing cards with DBF IDs: {missing_cards}")

        # Determine hero class from hero card
        # Note: heroes_data contains DBF IDs, not string IDs
        hero_class = "NEUTRAL"
        if heroes_data:
            hero_dbf_id = heroes_data[0]
            hero_card = card_db.get_card_by_dbf_id(hero_dbf_id)
            if hero_card:
                hero_class = hero_card.card_class

        # Determine format
        format_name = "Unknown"
        if format_data:
            format_name = "Standard" if format_data == 2 else "Wild"

        return cls(
            name=name,
            format=format_name,
            cards=tuple(cards),
            hero_class=hero_class,
            deckstring=deckstring,
        )


@dataclass
class CardDatabase:
    """Optimized card database with fast lookups and search capabilities"""

    cards_by_id: Dict[str, Card] = field(default_factory=dict)
    cards_by_dbf_id: Dict[int, Card] = field(default_factory=dict)
    cards_by_name: Dict[str, Card] = field(default_factory=dict)

    # Cached search indexes for performance
    cards_by_class: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_type: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_set: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_cost: Dict[int, List[Card]] = field(default_factory=dict)

    collectible_cards: List[Card] = field(default_factory=list)

    @classmethod
    def load(cls) -> "CardDatabase":
        """Load and build the card database from hearthstone library"""
        # Load the raw card database
        db, _ = load()

        # Create our database instance
        card_db = cls()

        # Convert all cards and build indexes
        for card_data in db.values():
            # Convert to our Card model
            card = Card.from_cardxml(card_data)

            # Primary lookups
            card_db.cards_by_id[card.id] = card
            card_db.cards_by_dbf_id[card.dbf_id] = card
            card_db.cards_by_name[card.name.lower()] = card

            # Build search indexes
            # By class
            if card.card_class not in card_db.cards_by_class:
                card_db.cards_by_class[card.card_class] = []
            card_db.cards_by_class[card.card_class].append(card)

            # By type
            if card.card_type not in card_db.cards_by_type:
                card_db.cards_by_type[card.card_type] = []
            card_db.cards_by_type[card.card_type].append(card)

            # By set
            if card.card_set not in card_db.cards_by_set:
                card_db.cards_by_set[card.card_set] = []
            card_db.cards_by_set[card.card_set].append(card)

            # By cost
            if card.cost not in card_db.cards_by_cost:
                card_db.cards_by_cost[card.cost] = []
            card_db.cards_by_cost[card.cost].append(card)

            # Collectible cards
            if card.collectible:
                card_db.collectible_cards.append(card)

        return card_db

    def get_card_by_id(self, card_id: str) -> Optional[Card]:
        """Get card by string ID (e.g., 'EX1_116')"""
        return self.cards_by_id.get(card_id)

    def get_card_by_dbf_id(self, dbf_id: int) -> Optional[Card]:
        """Get card by DBF ID (e.g., 559)"""
        return self.cards_by_dbf_id.get(dbf_id)

    def get_card_by_name(self, name: str) -> Optional[Card]:
        """Get card by name (case-insensitive)"""
        return self.cards_by_name.get(name.lower())

    def search_cards(
        self, query: str = "", filters: Optional[Dict[str, Any]] = None
    ) -> List[Card]:
        """Search cards with optional filters"""
        if filters is None:
            filters = {}

        # Start with all collectible cards by default
        candidates = self.collectible_cards.copy()

        # Apply filters
        if "card_class" in filters:
            candidates = [
                c for c in candidates if c.card_class == filters["card_class"]
            ]

        if "card_type" in filters:
            candidates = [c for c in candidates if c.card_type == filters["card_type"]]

        if "card_set" in filters:
            candidates = [c for c in candidates if c.card_set == filters["card_set"]]

        if "cost" in filters:
            candidates = [c for c in candidates if c.cost == filters["cost"]]

        if "min_cost" in filters:
            candidates = [c for c in candidates if c.cost >= filters["min_cost"]]

        if "max_cost" in filters:
            candidates = [c for c in candidates if c.cost <= filters["max_cost"]]

        if "rarity" in filters:
            candidates = [c for c in candidates if c.rarity == filters["rarity"]]

        # Text search in name and description
        if query:
            query_lower = query.lower()
            candidates = [
                c
                for c in candidates
                if query_lower in c.name.lower() or query_lower in c.text.lower()
            ]

        # Sort by name for consistent results
        return sorted(candidates, key=lambda c: c.name)

    def get_cards_by_class(self, card_class: str) -> List[Card]:
        """Get all cards for a specific class"""
        return self.cards_by_class.get(card_class, [])

    def get_cards_by_type(self, card_type: str) -> List[Card]:
        """Get all cards of a specific type"""
        return self.cards_by_type.get(card_type, [])

    def get_cards_by_cost(self, cost: int) -> List[Card]:
        """Get all cards with a specific mana cost"""
        return self.cards_by_cost.get(cost, [])

    def get_cards_by_set(self, card_set: str) -> List[Card]:
        """Get all cards from a specific set"""
        return self.cards_by_set.get(card_set, [])

    def total_cards(self) -> int:
        """Get total number of cards in database"""
        return len(self.cards_by_id)

    def total_collectible_cards(self) -> int:
        """Get total number of collectible cards"""
        return len(self.collectible_cards)


@dataclass
class Hero:
    """Represents a Hearthstone hero"""

    id: str
    name: str
    health: int
    armor: int
    hero_power: str


@dataclass
class GameState:
    """Represents a moment in game time"""

    turn: int
    player_board: List[Card]
    opponent_board: List[Card]
    player_hand: List[Card]
    opponent_hand: List[Optional[Card]]  # None for hidden cards
    player_hero: Hero
    opponent_hero: Hero
