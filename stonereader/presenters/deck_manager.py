"""Deck Manager presenter -- browse, delete, and export saved decks."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Sequence

from stonereader.db import delete_deck, get_all_decks
from stonereader.models.card import CardDatabase
from stonereader.models.deck import Deck, DeckSummary
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService

_DECKS_ZONE = "decks"


class DeckManagerPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages deck list navigation, deletion, and export."""

    def __init__(
        self,
        speech: SpeechService,
        db_conn: sqlite3.Connection,
        card_db: CardDatabase,
    ) -> None:
        super().__init__(speech)
        self._db_conn = db_conn
        self._card_db = card_db
        self._decks: list[DeckSummary] = []
        self._init_navigation([_DECKS_ZONE])
        self._on_state_changed: Callable[
            [list[DeckSummary], int], None
        ] | None = None
        self._on_open_deck: Callable[[Deck], None] | None = None
        self._on_request_delete_confirm: Callable[
            [str], bool
        ] | None = None
        self._export_callback: Callable[[str], None] | None = None
        self.load_decks()

    def load_decks(self) -> None:
        """Reload decks from database, sorted by created_at DESC (D-09)."""
        self._decks = get_all_decks(self._db_conn)
        cursor = self._zone_cursors.get(_DECKS_ZONE, 0)
        if self._decks:
            self._zone_cursors[_DECKS_ZONE] = min(
                cursor, len(self._decks) - 1
            )
        else:
            self._zone_cursors[_DECKS_ZONE] = 0

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _DECKS_ZONE:
            return self._decks
        return []

    def _format_item_speech(
        self, item: Any, position: int, total: int
    ) -> str:
        """Override for D-08: 'Name, Class, Format, N of M'."""
        if isinstance(item, DeckSummary):
            return (
                f"{item.name}, {item.hero_class}, {item.format}, "
                f"{position} of {total}"
            )
        return super()._format_item_speech(item, position, total)

    def set_on_state_changed(
        self, callback: Callable[[list[DeckSummary], int], None]
    ) -> None:
        self._on_state_changed = callback

    def set_on_open_deck(
        self, callback: Callable[[Deck], None]
    ) -> None:
        """Set callback invoked when user presses Enter to open a deck."""
        self._on_open_deck = callback

    def set_on_request_delete_confirm(
        self, callback: Callable[[str], bool]
    ) -> None:
        """Set callback that shows delete confirmation dialog.

        The callback receives the deck name and returns True if user
        confirmed deletion, False otherwise.
        """
        self._on_request_delete_confirm = callback

    def set_on_export(
        self, callback: Callable[[str], None]
    ) -> None:
        """Set callback that handles clipboard write for export."""
        self._export_callback = callback

    def _notify_view(self) -> None:
        if self._on_state_changed is not None:
            cursor = self._zone_cursors.get(_DECKS_ZONE, 0)
            self._on_state_changed(self._decks, cursor)

    def move_in_zone(self, delta: int) -> None:
        super().move_in_zone(delta)
        self._notify_view()

    def jump_to_first(self) -> None:
        super().jump_to_first()
        self._notify_view()

    def jump_to_last(self) -> None:
        super().jump_to_last()
        self._notify_view()

    def open_current_deck(self) -> None:
        """Open the currently selected deck's card list (D-11)."""
        item = self._current_item()
        if item is None:
            return
        if not isinstance(item, DeckSummary):
            return
        try:
            deck = Deck.from_deckstring(
                item.deckstring, self._card_db, item.name
            )
        except (ValueError, TypeError, Exception):
            self._speech.speak("Could not load deck cards")
            return
        if self._on_open_deck is not None:
            self._on_open_deck(deck)

    def delete_current_deck(self) -> None:
        """Delete the currently selected deck with confirmation (D-13, D-14).

        Shows confirmation dialog via view callback. On confirmation:
        - Deletes from database
        - Reloads deck list
        - Moves cursor to next deck (or previous if last was deleted)
        - Announces '{Name} deleted'
        """
        item = self._current_item()
        if item is None or not isinstance(item, DeckSummary):
            return

        # Request confirmation from view (shows wx.MessageDialog)
        if self._on_request_delete_confirm is not None:
            confirmed = self._on_request_delete_confirm(item.name)
            if not confirmed:
                return

        deck_name = item.name
        cursor_before = self._zone_cursors.get(_DECKS_ZONE, 0)
        delete_deck(self._db_conn, item.deck_id)
        self.load_decks()

        if not self._decks:
            self._speech.speak("Deck Manager: no saved decks")
        else:
            # D-13: cursor moves to next deck, or previous if was last
            new_cursor = min(cursor_before, len(self._decks) - 1)
            self._zone_cursors[_DECKS_ZONE] = new_cursor
            self._speech.speak(f"{deck_name} deleted")
        self._notify_view()

    def export_current_deckstring(self) -> str | None:
        """Return deckstring of current deck for clipboard copy (D-15).

        Announces 'Deck code copied to clipboard'. View handles clipboard.
        """
        item = self._current_item()
        if item is None or not isinstance(item, DeckSummary):
            return None
        self._speech.speak("Deck code copied to clipboard")
        return item.deckstring

    def announce_entry(self) -> None:
        """Announce on entering the deck manager screen."""
        if not self._decks:
            self._speech.speak("Deck Manager: no saved decks")
        else:
            cursor = self._zone_cursors.get(_DECKS_ZONE, 0)
            total = len(self._decks)
            item = self._decks[cursor]
            self._speech.speak(
                f"Deck Manager, {self._format_item_speech(item, cursor + 1, total)}"
            )

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        return {
            "left": lambda: self.move_in_zone(-1),
            "right": lambda: self.move_in_zone(1),
            "up": lambda: self.move_in_zone(-1),
            "down": lambda: self.move_in_zone(1),
            "enter": self.open_current_deck,
            "home": self.jump_to_first,
            "end": self.jump_to_last,
            "delete": self.delete_current_deck,
            "c": self._export_to_clipboard,
        }

    def _export_to_clipboard(self) -> None:
        """Trigger export -- presenter returns deckstring, view handles clipboard."""
        deckstring = self.export_current_deckstring()
        if deckstring is not None and self._export_callback is not None:
            self._export_callback(deckstring)
