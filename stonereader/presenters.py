from typing import Dict, List, Optional

from . import models


class CardBrowserPresenter:
    """Handles card search and browsing logic"""

    def __init__(self, card_db: models.CardDatabase):
        self.card_db = card_db

    def search_cards(
        self, query: str = "", filters: Optional[Dict] = None
    ) -> List[models.Card]:
        """Search for cards using the card database"""
        if filters is None:
            filters = {}
        return self.card_db.search_cards(query, filters)

    def get_card_details(self, card_id: str) -> Optional[models.Card]:
        """Fetches detailed information about a card"""
        return self.card_db.get_card_by_id(card_id)

    def get_card_by_name(self, name: str) -> Optional[models.Card]:
        """Get card by name"""
        return self.card_db.get_card_by_name(name)

    def format_card_details(self, card: models.Card) -> str:
        """Formats complete card information for display"""
        # Build basic stats
        stats = []
        if card.attack is not None:
            stats.append(f"{card.attack} attack")
        if card.health is not None:
            stats.append(f"{card.health} health")
        if card.durability is not None:
            stats.append(f"{card.durability} durability")

        # Build abilities list using tag access
        abilities = []
        ability_tags = [
            ("TAUNT", "taunt"),
            ("CHARGE", "charge"),
            ("RUSH", "rush"),
            ("DIVINE_SHIELD", "divine shield"),
            ("LIFESTEAL", "lifesteal"),
            ("POISONOUS", "poisonous"),
            ("STEALTH", "stealth"),
            ("WINDFURY", "windfury"),
        ]

        for tag_name, ability_name in ability_tags:
            if card.has_tag(tag_name):
                abilities.append(ability_name)

        # Build complete card details
        parts = [
            f"{card.name}",
            f"{card.cost} mana {card.card_type.lower()}",
            f"{card.rarity.lower()} {card.card_class.lower()}",
        ]

        if stats:
            parts.append(", ".join(stats))

        if abilities:
            parts.append(f"Abilities: {', '.join(abilities)}")

        if card.text:
            parts.append(f"Effect: {card.text}")

        if card.card_set:
            parts.append(f"From {card.card_set}")

        return ". ".join(parts) + "."


class DeckManagerPresenter:
    """Handles deck import/export and management"""

    def __init__(self, card_db: models.CardDatabase):
        self.card_db = card_db

    def import_deck_string(
        self, deck_string: str, name: str = "Imported Deck"
    ) -> models.Deck:
        """Import a deck from a deckstring"""
        return models.Deck.from_deckstring(deck_string, self.card_db, name)

    def export_deck_string(self, deck: models.Deck) -> str:
        """Export deck to deckstring format"""
        return deck.deckstring

    def validate_deck(self, deck: models.Deck) -> List[str]:
        """Validate deck construction rules - accepts any parseable deckstring"""
        # Since we're importing any deck parseable by hearthstone.deckstrings,
        # we don't need to enforce standard construction rules
        return []

    def format_card_details(self, card: models.Card) -> str:
        """Formats complete card information for display"""
        # Build basic stats
        stats = []
        if card.attack is not None:
            stats.append(f"{card.attack} attack")
        if card.health is not None:
            stats.append(f"{card.health} health")
        if card.durability is not None:
            stats.append(f"{card.durability} durability")

        # Build abilities list using tag access
        abilities = []
        ability_tags = [
            ("TAUNT", "taunt"),
            ("CHARGE", "charge"),
            ("RUSH", "rush"),
            ("DIVINE_SHIELD", "divine shield"),
            ("LIFESTEAL", "lifesteal"),
            ("POISONOUS", "poisonous"),
            ("STEALTH", "stealth"),
            ("WINDFURY", "windfury"),
        ]

        for tag_name, ability_name in ability_tags:
            if card.has_tag(tag_name):
                abilities.append(ability_name)

        # Build complete card details
        parts = [
            f"{card.name}",
            f"{card.cost} mana {card.card_type.lower()}",
            f"{card.rarity.lower()} {card.card_class.lower()}",
        ]

        if stats:
            parts.append(", ".join(stats))

        if abilities:
            parts.append(f"Abilities: {', '.join(abilities)}")

        if card.text:
            parts.append(f"Effect: {card.text}")

        if card.card_set:
            parts.append(f"From {card.card_set}")

        return ". ".join(parts) + "."


class ReplayViewerPresenter:
    """Handles game replay navigation and state"""

    def load_replay(self, file_path: str):
        """Loads a game replay from a file"""
        pass

    def next_turn(self):
        """Advances to the next turn in the replay"""
        pass

    def previous_turn(self):
        """Reverts to the previous turn in the replay"""
        pass

    def jump_to_turn(self, turn: int):
        """Jumps to a specific turn in the replay"""
        pass

    def get_current_board_state(self) -> models.GameState | None:
        """Retrieves the current board state from the replay"""
        pass
