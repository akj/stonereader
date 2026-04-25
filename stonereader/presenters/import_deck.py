"""Import Deck presenter -- validate and import deckstrings."""

from __future__ import annotations

import sqlite3
from typing import Callable

from stonereader.db import save_deck
from stonereader.models.card import CardDatabase
from stonereader.models.deck import Deck, MissingCardsError, count_unknown_cards
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

    def set_on_show_error(self, callback: Callable[[str, str], None]) -> None:
        """Set callback to show error dialog. Args: (message, title)."""
        self._on_show_error = callback

    def validate_and_import(self, deckstring: str, name: str) -> bool:
        """Validate inputs and import deck. Returns True on success.

        Uses graceful-degrade import (Deck.from_deckstring(..., allow_unknown=True))
        so a deckstring referencing cards from a newer expansion still imports;
        unknown cards become placeholder Card entries. The user is told how many
        cards were unknown via the success announcement (UAT Gap 1, DECK-01).
        """
        if not deckstring.strip():
            self._show_error("Enter a deck code to import.")
            return False
        if not name.strip():
            self._show_error("Enter a name for this deck.")
            return False
        try:
            deck = Deck.from_deckstring(
                deckstring.strip(),
                self._card_db,
                name.strip(),
                allow_unknown=True,
            )
        except MissingCardsError as exc:
            # Should not fire because allow_unknown=True; kept as defense-in-depth
            # in case a future refactor re-enables strict mode.
            self._show_error(self._format_missing_cards_message(exc.missing_dbf_ids))
            return False
        except ValueError:
            self._show_error(
                "Invalid deck code. Check that you copied the full "
                "code from Hearthstone and try again."
            )
            return False
        except TypeError:
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

        unknown_count = count_unknown_cards(deck)
        if unknown_count == 1:
            announcement = f"{deck.name} imported, 1 unknown card"
        elif unknown_count > 1:
            announcement = f"{deck.name} imported, {unknown_count} unknown cards"
        else:
            announcement = f"{deck.name} imported"
        self._speech.speak(announcement)

        if self._on_import_success is not None:
            self._on_import_success()
        return True

    def _show_error(self, message: str) -> None:
        """Show error via view callback or fallback to speech."""
        if self._on_show_error is not None:
            self._on_show_error(message, "Error")
        else:
            self._speech.speak(message)

    def _format_missing_cards_message(self, missing_dbf_ids: tuple[int, ...]) -> str:
        """Format the missing-cards error dialog text with specific DBF IDs.

        Invoked when a strict-mode caller hits MissingCardsError. The DBF IDs are
        listed so the user/developer can identify which cards (and thus which
        expansion) the local card database is missing.
        """
        if not missing_dbf_ids:
            return (
                "Some cards in this deck were not found in the card database. "
                "The deck code may be from a newer expansion."
            )
        ids_text = ", ".join(str(d) for d in missing_dbf_ids)
        return (
            f"Some cards in this deck were not found in the card database "
            f"(DBF IDs: {ids_text}). The deck code may be from a newer expansion."
        )

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        """Return empty key map -- import screen uses Tab navigation."""
        return {}
