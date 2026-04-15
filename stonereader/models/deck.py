"""Hearthstone deck models -- Deck (resolved cards) and DeckSummary (lightweight list display)."""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from hearthstone import deckstrings

from stonereader.models.card import Card, CardDatabase


@dataclass(frozen=True)
class Deck:
    """Represents a Hearthstone deck."""

    name: str
    format: str
    cards: Tuple[Tuple[Card, int], ...]
    hero_class: str
    deckstring: str = ""

    def total_cards(self) -> int:
        return sum(count for _, count in self.cards)

    def average_cost(self) -> float:
        if not self.cards:
            return 0.0
        total_cost = sum(card.cost * count for card, count in self.cards)
        total_cards = self.total_cards()
        return total_cost / total_cards if total_cards > 0 else 0.0

    def cards_by_cost(self) -> Dict[int, List[Tuple[Card, int]]]:
        cost_groups: Dict[int, List[Tuple[Card, int]]] = {}
        for card, count in self.cards:
            cost_groups.setdefault(card.cost, []).append((card, count))
        return cost_groups

    @property
    def total_dust_cost(self) -> int:
        dust_costs = {
            "COMMON": 40,
            "RARE": 100,
            "EPIC": 400,
            "LEGENDARY": 1600,
        }
        return sum(
            dust_costs.get(card.rarity, 0) * count for card, count in self.cards
        )

    @classmethod
    def from_deckstring(
        cls, deckstring: str, card_db: CardDatabase, name: str = "Imported Deck"
    ) -> "Deck":
        cards_data, heroes_data, format_data, _ = deckstrings.parse_deckstring(
            deckstring
        )
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
        hero_class = "NEUTRAL"
        if heroes_data:
            hero_card = card_db.get_card_by_dbf_id(heroes_data[0])
            if hero_card:
                hero_class = hero_card.card_class
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


@dataclass(frozen=True)
class DeckSummary:
    """Lightweight deck info for list display — no resolved cards."""

    deck_id: int
    name: str
    hero_class: str
    format: str
    deckstring: str
    created_at: str
