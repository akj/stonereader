"""Import Deck presenter -- validate and import deckstrings."""

from __future__ import annotations

import sqlite3
from typing import Callable

from stonereader.db import save_deck
from stonereader.models.card import CardDatabase
from stonereader.models.deck import Deck
from stonereader.presenters.base import BasePresenter
from stonereader.speech_service import SpeechService


class ImportDeckPresenter(BasePresenter):
    """Handles deckstring validation and deck import.

    Does NOT use ZoneNavigationMixin -- the import screen uses TextCtrl
    fields and buttons with standard Tab navigation, not zone-based
    keyboard navigation.
    """

    def __init__(
        self,
        speech: SpeechService,
        db_conn: sqlite3.Connection,
        card_db: CardDatabase,
    ) -> None:
        super().__init__(speech)
        self._db_conn = db_conn
        self._card_db = card_db
        self._on_import_success: Callable[[], None] | None = None
        self._on_show_error: Callable[[str, str], None] | None = None

    def set_on_import_success(self, callback: Callable[[], None]) -> None:
        """Set callback invoked after successful import."""
        self._on_import_success = callback

    def set_on_show_error(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """Set callback to show error dialog. Args: (message, title)."""
        self._on_show_error = callback

    def validate_and_import(
        self, deckstring: str, name: str
    ) -> bool:
        """Validate inputs and import deck. Returns True on success.

        Error handling per D-07: validation errors shown via wx.MessageBox.
        Exception handling per RESEARCH.md Pitfall 2: catch ValueError,
        TypeError, and broad Exception from parse_deckstring.
        """
        if not deckstring.strip():
            self._show_error("Enter a deck code to import.")
            return False
        if not name.strip():
            self._show_error("Enter a name for this deck.")
            return False
        try:
            deck = Deck.from_deckstring(
                deckstring.strip(), self._card_db, name.strip()
            )
        except ValueError as exc:
            # Distinguish our "Missing cards" ValueError from library parse errors
            if "Missing cards" in str(exc):
                self._show_error(
                    "Some cards in this deck were not found in the card "
                    "database. The deck code may be from a newer expansion."
                )
            else:
                self._show_error(
                    "Invalid deck code. Check that you copied the full "
                    "code from Hearthstone and try again."
                )
            return False
        except (TypeError, Exception):
            self._show_error(
                "Invalid deck code. Check that you copied the full "
                "code from Hearthstone and try again."
            )
            return False

        save_deck(
            self._db_conn,
            deck.name,
            deck.hero_class,
            deck.format,
            deckstring.strip(),
        )
        self._speech.speak(f"{deck.name} imported")

        if self._on_import_success is not None:
            self._on_import_success()
        return True

    def _show_error(self, message: str) -> None:
        """Show error via view callback or fallback to speech."""
        if self._on_show_error is not None:
            self._on_show_error(message, "Error")
        else:
            self._speech.speak(message)

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        """Return empty key map -- import screen uses Tab navigation."""
        return {}
