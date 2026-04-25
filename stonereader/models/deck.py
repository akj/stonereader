"""Hearthstone deck models -- Deck (resolved cards) and DeckSummary (lightweight list display)."""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from hearthstone import deckstrings

from stonereader.models.card import Card, CardDatabase


class MissingCardsError(ValueError):
    """Raised when a deckstring references DBF IDs not present in the card database.

    Subclass of ValueError so existing `except ValueError` handlers continue to
    catch it. Exposes the missing DBF IDs as a tuple for diagnostic display.
    """

    def __init__(self, missing_dbf_ids: tuple[int, ...]) -> None:
        self.missing_dbf_ids = missing_dbf_ids
        super().__init__(f"Missing cards with DBF IDs: {list(missing_dbf_ids)}")


def _make_placeholder_card(dbf_id: int) -> Card:
    """Build a placeholder Card for an unknown DBF ID (graceful-degrade import)."""
    return Card(
        id=f"UNKNOWN_{dbf_id}",
        dbf_id=dbf_id,
        name=f"Unknown card #{dbf_id}",
        cost=0,
        attack=None,
        health=None,
        text="",
        rarity="COMMON",
        card_class="NEUTRAL",
        card_type="MINION",
        card_set="",
        collectible=False,
    )


def count_unknown_cards(deck: "Deck") -> int:
    """Return the number of placeholder (unknown) Card entries in a Deck.

    Used by ImportDeckPresenter to announce 'N unknown cards' after a
    graceful-degrade import. Counts (card, count) tuples whose card.id
    starts with 'UNKNOWN_'.
    """
    return sum(count for card, count in deck.cards if card.id.startswith("UNKNOWN_"))


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
        return sum(dust_costs.get(card.rarity, 0) * count for card, count in self.cards)

    @classmethod
    def from_deckstring(
        cls,
        deckstring: str,
        card_db: CardDatabase,
        name: str = "Imported Deck",
        *,
        allow_unknown: bool = False,
    ) -> "Deck":
        """Parse a deckstring into a Deck.

        By default (allow_unknown=False), raises MissingCardsError if any DBF
        ID in the deckstring is not present in card_db. The error's
        missing_dbf_ids attribute lists the offending IDs for diagnostics.

        With allow_unknown=True, missing DBF IDs become placeholder Card
        entries (id prefixed with UNKNOWN_, collectible=False). This lets a
        deckstring from a newer expansion still import when the local card
        database is older. The original deckstring is preserved on the Deck so
        a later refresh can re-resolve the unknown cards.
        """
        cards_data, heroes_data, format_data, _ = deckstrings.parse_deckstring(
            deckstring
        )
        cards: list[tuple[Card, int]] = []
        missing_dbf_ids: list[int] = []
        for dbf_id, count in cards_data:
            card = card_db.get_card_by_dbf_id(dbf_id)
            if card is not None:
                cards.append((card, count))
            elif allow_unknown:
                cards.append((_make_placeholder_card(dbf_id), count))
                missing_dbf_ids.append(dbf_id)
            else:
                missing_dbf_ids.append(dbf_id)
        if missing_dbf_ids and not allow_unknown:
            raise MissingCardsError(tuple(missing_dbf_ids))
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
