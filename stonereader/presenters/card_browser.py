"""Card Browser presenter -- browse and search cards within a category."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService

_RESULTS_ZONE = "results"
_CATEGORY_TO_FILTER: dict[str, str | None] = {
    "All Cards": None,
    "Demon Hunter": "DEMONHUNTER",
    "Death Knight": "DEATHKNIGHT",
    "Druid": "DRUID",
    "Hunter": "HUNTER",
    "Mage": "MAGE",
    "Neutral": "NEUTRAL",
    "Paladin": "PALADIN",
    "Priest": "PRIEST",
    "Rogue": "ROGUE",
    "Shaman": "SHAMAN",
    "Warlock": "WARLOCK",
    "Warrior": "WARRIOR",
}
_CATEGORY_ORDER = list(_CATEGORY_TO_FILTER.keys())
_PAGE_SIZE = 10


class CardBrowserPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages card navigation and search for a filtered card list.

    Receives a category_label and optional card_class filter. All collectible
    cards matching the filter are loaded initially. The search() method further
    narrows results by name/text query.
    """

    def __init__(
        self,
        speech: SpeechService,
        card_db: CardDatabase,
        category_label: str = "All Cards",
        card_class_filter: str | None = None,
    ) -> None:
        super().__init__(speech)
        self._card_db = card_db
        self._category_label = category_label
        try:
            self._class_index = _CATEGORY_ORDER.index(category_label)
        except ValueError:
            self._class_index = 0
        self._class_filter = card_class_filter
        self._mana_filter: int | None = None
        self._filters = self._build_filters()
        self._results: list[Card] = self._card_db.search_cards(filters=self._filters)
        self._init_navigation([_RESULTS_ZONE])
        self._on_state_changed: Callable[[list[Card], int], None] | None = None
        self._on_status_changed: Callable[[str], None] | None = None
        self._on_request_search: Callable[[], str | None] | None = None

    def _build_filters(self) -> dict[str, Any] | None:
        f: dict[str, Any] = {}
        if self._class_filter:
            f["card_class"] = self._class_filter
        if self._mana_filter is not None:
            if self._mana_filter == 9:
                f["min_cost"] = 9
            else:
                f["cost"] = self._mana_filter
        return f or None

    def _recompute_results(self) -> None:
        self._filters = self._build_filters()
        self._results = self._card_db.search_cards(filters=self._filters)
        self._zone_cursors[_RESULTS_ZONE] = 0
        self._detail_cursor = -1

    def _build_status_string(self) -> str:
        parts = [self._category_label]
        if self._mana_filter is not None:
            mana_label = (
                "9+ mana" if self._mana_filter == 9 else f"{self._mana_filter} mana"
            )
            parts.append(mana_label)
        count = len(self._results)
        parts.append(f"{count} card" if count == 1 else f"{count} cards")
        return ", ".join(parts)

    def _emit_status(self) -> None:
        status = self._build_status_string()
        self._speech.speak(status)
        if self._on_status_changed is not None:
            self._on_status_changed(status)

    def cycle_class(self, direction: int) -> None:
        """Advance (+1) or retreat (-1) the active class with wrap-around."""
        self._class_index = (self._class_index + direction) % len(_CATEGORY_ORDER)
        label = _CATEGORY_ORDER[self._class_index]
        self._category_label = label
        self._class_filter = _CATEGORY_TO_FILTER[label]
        self._recompute_results()
        self._emit_status()
        self._notify_view()

    def apply_mana_filter(self, digit: int) -> None:
        """Single-select mana-cost filter.

        Press digit -> filter to that cost. Press same digit again -> clear.
        Press different digit -> replace. "9" matches cost >= 9.
        """
        if self._mana_filter == digit:
            self._mana_filter = None
        else:
            self._mana_filter = digit
        self._recompute_results()
        self._emit_status()
        self._notify_view()

    def page(self, direction: int) -> None:
        """Move the results cursor by _PAGE_SIZE in `direction`, clamping."""
        if not self._results:
            return
        cursor = self._zone_cursors.get(_RESULTS_ZONE, 0)
        cursor = max(0, min(cursor + direction * _PAGE_SIZE, len(self._results) - 1))
        self._zone_cursors[_RESULTS_ZONE] = cursor
        self._detail_cursor = 0
        item = self._results[cursor]
        self._speech.speak(
            self._format_item_speech(item, cursor + 1, len(self._results))
        )
        self._notify_view()

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _RESULTS_ZONE:
            return self._results
        return []

    def search(self, query: str) -> None:
        """Run a search within the current category and announce the result count."""
        self._results = self._card_db.search_cards(query, self._filters)
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

    def announce_entry(self) -> None:
        """Announce on entering the card browser for this category."""
        count = len(self._results)
        cursor = self._zone_cursors.get(_RESULTS_ZONE, 0)
        if not self._results:
            self._speech.speak(f"{self._category_label}: no cards")
            return
        item = self._results[cursor]
        self._speech.speak(
            f"{self._category_label}, {self._format_item_speech(item, cursor + 1, count)}"
        )

    def set_on_state_changed(self, callback: Callable[[list[Card], int], None]) -> None:
        self._on_state_changed = callback

    def set_on_status_changed(self, callback: Callable[[str], None]) -> None:
        self._on_status_changed = callback

    def set_on_request_search(self, callback: Callable[[], str | None]) -> None:
        """Set callback that shows search dialog and returns query or None."""
        self._on_request_search = callback

    def open_search(self) -> None:
        """Trigger the search dialog via the view callback."""
        if self._on_request_search is not None:
            query = self._on_request_search()
            if query is not None:
                self.search(query)

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
        key_map: dict[str, Callable[[], None]] = {
            "left": lambda: self.move_in_zone(-1),
            "right": lambda: self.move_in_zone(1),
            "down": self._read_detail_down,
            "up": self._read_detail_up,
            "home": self.jump_to_first,
            "end": self.jump_to_last,
            "tab": lambda: self.cycle_class(1),
            "shift+tab": lambda: self.cycle_class(-1),
            "pagedown": lambda: self.page(1),
            "pageup": lambda: self.page(-1),
        }
        for digit in range(10):
            key_map[str(digit)] = lambda d=digit: self.apply_mana_filter(d)
        return key_map

    def _read_detail_down(self) -> None:
        item = self._current_item()
        if item is not None:
            self.read_detail_lines(item, direction=1)

    def _read_detail_up(self) -> None:
        item = self._current_item()
        if item is not None:
            self.read_detail_lines(item, direction=-1)
