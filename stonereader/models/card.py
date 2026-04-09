from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from hearthstone.cardxml import load


@dataclass(frozen=True)
class Card:
    """Represents a Hearthstone card with complete tag access."""

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
    tags: Dict[str, Any] = field(default_factory=dict)

    def has_tag(self, tag_name: str) -> bool:
        if not self.tags:
            return False
        return bool(self.tags.get(tag_name, 0))

    def get_tag(self, tag_name: str, default: Any = None) -> Any:
        if not self.tags:
            return default
        return self.tags.get(tag_name, default)

    @classmethod
    def from_cardxml(cls, cardxml_card: Any) -> "Card":
        tags_dict: Dict[str, Any] = {}
        if hasattr(cardxml_card, "tags") and cardxml_card.tags:
            for tag_enum, value in cardxml_card.tags.items():
                tag_name = str(tag_enum).split(".")[-1]
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
            card_class=(
                str(cardxml_card.card_class) if cardxml_card.card_class else "NEUTRAL"
            ),
            card_type=str(cardxml_card.type) if cardxml_card.type else "MINION",
            card_set=str(cardxml_card.card_set) if cardxml_card.card_set else "",
            collectible=bool(cardxml_card.collectible),
            durability=cardxml_card.durability if cardxml_card.durability else None,
            tags=tags_dict,
        )

    def to_speech_text(self) -> str:
        """Return card name only for navigation announcements (DL-004)."""
        return self.name

    def detail_lines(self) -> list[str]:
        """Return ordered detail lines for Up/Down inspection.

        Order: name, cost, attack/health (if applicable), type, class,
        text, set, rarity, durability (if applicable).
        """
        lines = [
            self.name,
            f"{self.cost} mana",
        ]
        if self.attack is not None and self.health is not None:
            lines.append(f"{self.attack} attack, {self.health} health")
        elif self.attack is not None:
            lines.append(f"{self.attack} attack")
        elif self.health is not None:
            lines.append(f"{self.health} health")
        lines.append(self.card_type.lower())
        if self.card_class != "NEUTRAL":
            lines.append(f"{self.card_class.lower()} class")
        if self.text:
            lines.append(self.text)
        if self.card_set:
            lines.append(f"Set: {self.card_set}")
        lines.append(self.rarity.lower())
        if self.durability is not None:
            lines.append(f"{self.durability} durability")
        return lines


@dataclass
class CardDatabase:
    """Card database with indexed lookups and search."""

    cards_by_id: Dict[str, Card] = field(default_factory=dict)
    cards_by_dbf_id: Dict[int, Card] = field(default_factory=dict)
    cards_by_name: Dict[str, Card] = field(default_factory=dict)
    cards_by_class: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_type: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_set: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_cost: Dict[int, List[Card]] = field(default_factory=dict)
    collectible_cards: List[Card] = field(default_factory=list)

    @classmethod
    def load(cls) -> "CardDatabase":
        db, _ = load()
        card_db = cls()
        for card_data in db.values():
            card = Card.from_cardxml(card_data)
            card_db.cards_by_id[card.id] = card
            card_db.cards_by_dbf_id[card.dbf_id] = card
            card_db.cards_by_name[card.name.lower()] = card
            card_db.cards_by_class.setdefault(card.card_class, []).append(card)
            card_db.cards_by_type.setdefault(card.card_type, []).append(card)
            card_db.cards_by_set.setdefault(card.card_set, []).append(card)
            card_db.cards_by_cost.setdefault(card.cost, []).append(card)
            if card.collectible:
                card_db.collectible_cards.append(card)
        return card_db

    def get_card_by_id(self, card_id: str) -> Optional[Card]:
        return self.cards_by_id.get(card_id)

    def get_card_by_dbf_id(self, dbf_id: int) -> Optional[Card]:
        return self.cards_by_dbf_id.get(dbf_id)

    def get_card_by_name(self, name: str) -> Optional[Card]:
        return self.cards_by_name.get(name.lower())

    def search_cards(
        self, query: str = "", filters: Optional[Dict[str, Any]] = None
    ) -> List[Card]:
        if filters is None:
            filters = {}
        candidates = self.collectible_cards.copy()
        if "card_class" in filters:
            candidates = [c for c in candidates if c.card_class == filters["card_class"]]
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
        if query:
            query_lower = query.lower()
            candidates = [
                c
                for c in candidates
                if query_lower in c.name.lower() or query_lower in c.text.lower()
            ]
        return sorted(candidates, key=lambda c: c.name)

    def get_cards_by_class(self, card_class: str) -> List[Card]:
        return self.cards_by_class.get(card_class, [])

    def get_cards_by_type(self, card_type: str) -> List[Card]:
        return self.cards_by_type.get(card_type, [])

    def get_cards_by_cost(self, cost: int) -> List[Card]:
        return self.cards_by_cost.get(cost, [])

    def get_cards_by_set(self, card_set: str) -> List[Card]:
        return self.cards_by_set.get(card_set, [])

    def total_cards(self) -> int:
        return len(self.cards_by_id)

    def total_collectible_cards(self) -> int:
        return len(self.collectible_cards)
