import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from hearthstone.cardxml import load


CARD_CLASS_NAMES: dict[str, str] = {
    "DEMONHUNTER": "Demon Hunter",
    "DEATHKNIGHT": "Death Knight",
    "DRUID": "Druid",
    "HUNTER": "Hunter",
    "MAGE": "Mage",
    "NEUTRAL": "Neutral",
    "PALADIN": "Paladin",
    "PRIEST": "Priest",
    "ROGUE": "Rogue",
    "SHAMAN": "Shaman",
    "WARLOCK": "Warlock",
    "WARRIOR": "Warrior",
}


def _strip_tags(text: str) -> str:
    """Strip HTML tags, game markup, and normalize whitespace in card text."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\\n", " ").replace("\n", " ")
    # Remove spell damage scaling markers ($)
    text = text.replace("$", "")
    # Replace underscore joiners with spaces
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
    spell_school: str = ""
    flavor_text: str = ""
    artist: str = ""
    rune_blood: int = 0
    rune_frost: int = 0
    rune_unholy: int = 0
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
        from hearthstone.enums import GameTag

        tags_dict: Dict[str, Any] = {}
        rune_blood = 0
        rune_frost = 0
        rune_unholy = 0
        if hasattr(cardxml_card, "tags") and cardxml_card.tags:
            for tag_enum, value in cardxml_card.tags.items():
                tag_name = tag_enum.name if hasattr(tag_enum, "name") else str(tag_enum)
                tags_dict[tag_name] = value
            rune_blood = cardxml_card.tags.get(GameTag.COST_BLOOD, 0)
            rune_frost = cardxml_card.tags.get(GameTag.COST_FROST, 0)
            rune_unholy = cardxml_card.tags.get(GameTag.COST_UNHOLY, 0)

        spell_school = ""
        if getattr(cardxml_card, "spell_school", None):
            ss = cardxml_card.spell_school
            spell_school = ss.name if hasattr(ss, "name") else str(ss)

        return cls(
            id=cardxml_card.id,
            dbf_id=cardxml_card.dbf_id if hasattr(cardxml_card, "dbf_id") else 0,
            name=cardxml_card.name or "",
            cost=cardxml_card.cost or 0,
            attack=cardxml_card.atk if cardxml_card.atk else None,
            health=cardxml_card.health if cardxml_card.health else None,
            text=_strip_tags(cardxml_card.description or ""),
            rarity=cardxml_card.rarity.name if cardxml_card.rarity else "COMMON",
            card_class=(
                cardxml_card.card_class.name if cardxml_card.card_class else "NEUTRAL"
            ),
            card_type=cardxml_card.type.name if cardxml_card.type else "MINION",
            card_set=cardxml_card.card_set.name if cardxml_card.card_set else "",
            collectible=bool(cardxml_card.collectible),
            durability=cardxml_card.durability if cardxml_card.durability else None,
            spell_school=spell_school,
            flavor_text=getattr(cardxml_card, "flavortext", "") or "",
            artist=getattr(cardxml_card, "artist", "") or "",
            rune_blood=rune_blood,
            rune_frost=rune_frost,
            rune_unholy=rune_unholy,
            tags=tags_dict,
        )

    def to_speech_text(self) -> str:
        """Return card name only for navigation announcements (DL-004)."""
        return self.name

    def detail_lines(self) -> list[str]:
        """Return ordered detail lines for Up/Down inspection.

        Order matches HearthstoneAccess convention:
        name, cost, runes (DK), stats, text, spell school, type,
        rarity, set, flavor, artist.
        """
        lines = [
            self.name,
            f"{self.cost} mana",
        ]
        # Runes (Death Knight only)
        runes: list[str] = []
        if self.rune_blood:
            runes.append(f"{self.rune_blood} blood")
        if self.rune_frost:
            runes.append(f"{self.rune_frost} frost")
        if self.rune_unholy:
            runes.append(f"{self.rune_unholy} unholy")
        if runes:
            lines.append(", ".join(runes))
        # Stats — varies by card type
        if self.card_type == "WEAPON":
            # Weapons: health field holds durability
            if self.attack is not None and self.health is not None:
                lines.append(f"{self.attack} attack, {self.health} durability")
            elif self.attack is not None:
                lines.append(f"{self.attack} attack")
        elif self.attack is not None and self.health is not None:
            lines.append(f"{self.attack} attack, {self.health} health")
        elif self.attack is not None:
            lines.append(f"{self.attack} attack")
        elif self.health is not None:
            lines.append(f"{self.health} health")
        # Card text
        if self.text:
            lines.append(self.text)
        # Spell school
        if self.spell_school:
            lines.append(self.spell_school.lower())
        # Type
        lines.append(self.card_type.lower())
        # Rarity
        lines.append(self.rarity.lower())
        # Set
        if self.card_set:
            lines.append(self.card_set)
        # Flavor text
        if self.flavor_text:
            lines.append(self.flavor_text)
        # Artist
        if self.artist:
            lines.append(self.artist)
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
