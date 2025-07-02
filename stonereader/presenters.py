from typing import Dict
from hearthstone import cardxml, deckstrings
import models

class CardBrowserPresenter:
    """Handles card search and browsing logic"""
    def search_cards(self, query: str, filters: Dict):
        pass

    def get_card_details(self, card_id: str):
        """Fetches detailed information about a card"""
        pass
    def format_for_speech(self, card: models.Card, detail_level: str):
        """Formats card information for speech output"""
        pass

class DeckManagerPresenter:
    """Handles deck import/export and management"""
    def import_deck_string(self, deck_string: str):
        pass

    def export_deck_string(self, deck: models.Deck):
        pass

    def validate_deck(self, deck: models.Deck):
        pass

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
