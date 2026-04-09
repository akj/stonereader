"""Card Library presenter — search and browse the card database."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService


_RESULTS_ZONE = "results"


class CardBrowserPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages search state and navigation for the Card Library tab."""

    def __init__(self, speech: SpeechService, card_db: CardDatabase) -> None:
        super().__init__(speech)
        self._card_db = card_db
        self._results: list[Card] = sorted(
            card_db.collectible_cards, key=lambda c: c.name
        )
        self._init_navigation([_RESULTS_ZONE])
        self._on_state_changed: Callable[[list[Card], int], None] | None = None
        self._on_status_changed: Callable[[str], None] | None = None

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _RESULTS_ZONE:
            return self._results
        return []

    def search(self, query: str) -> None:
        """Run a search and announce the result count."""
        self._results = self._card_db.search_cards(query)
        self._zone_cursors[_RESULTS_ZONE] = 0
        self._detail_cursor = -1
        count = len(self._results)
        if count == 0:
            status = "No results"
        elif count == 1:
            status = "1 result"
        else:
            status = f"{count} results"
        self._speech.speak(status)
        if self._on_status_changed is not None:
            self._on_status_changed(status)
        self._notify_view()

    def set_on_state_changed(
        self, callback: Callable[[list[Card], int], None]
    ) -> None:
        self._on_state_changed = callback

    def set_on_status_changed(self, callback: Callable[[str], None]) -> None:
        self._on_status_changed = callback

    def _notify_view(self) -> None:
        if self._on_state_changed is not None:
            cursor = self._zone_cursors.get(_RESULTS_ZONE, 0)
            self._on_state_changed(self._results, cursor)

    def move_in_zone(self, delta: int) -> None:
        super().move_in_zone(delta)
        self._notify_view()

    def jump_to_first(self) -> None:
        super().jump_to_first()
        self._notify_view()

    def jump_to_last(self) -> None:
        super().jump_to_last()
        self._notify_view()

    def copy_current_card_name(self) -> str | None:
        """Return current card name and announce copy. View handles clipboard."""
        item = self._current_item()
        if item is None:
            return None
        card = self._extract_card(item)
        if card is None:
            return None
        self.announce(f"Copied {card.name}")
        return card.name

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        return {
            "left": lambda: self.move_in_zone(-1),
            "right": lambda: self.move_in_zone(1),
            "down": self._read_detail_down,
            "up": self._read_detail_up,
            "home": self.jump_to_first,
            "end": self.jump_to_last,
        }

    def _read_detail_down(self) -> None:
        item = self._current_item()
        if item is not None:
            self.read_detail_lines(item, direction=1)

    def _read_detail_up(self) -> None:
        item = self._current_item()
        if item is not None:
            self.read_detail_lines(item, direction=-1)
