"""Card Library category menu presenter -- browse card categories."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService

_MENU_ZONE = "menu"

# Category items -- order matches the ListBox in the view
CATEGORY_ITEMS = [
    "All Cards",
    "Demon Hunter",
    "Death Knight",
    "Druid",
    "Hunter",
    "Mage",
    "Neutral",
    "Paladin",
    "Priest",
    "Rogue",
    "Shaman",
    "Warlock",
    "Warrior",
]

# Map display names to CardDatabase card_class values
CATEGORY_TO_FILTER: dict[str, str | None] = {
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


class CardLibraryPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages category menu navigation for the Card Library."""

    def __init__(self, speech: SpeechService) -> None:
        super().__init__(speech)
        self._init_navigation([_MENU_ZONE])
        self._on_select: Callable[[str], None] | None = None

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _MENU_ZONE:
            return CATEGORY_ITEMS
        return []

    def set_on_select(self, callback: Callable[[str], None]) -> None:
        """Set callback invoked when user presses Enter on a category."""
        self._on_select = callback

    def select_current(self) -> None:
        """Activate the currently highlighted category."""
        item = self._current_item()
        if item is not None and self._on_select is not None:
            self._on_select(str(item))

    def announce_entry(self) -> None:
        """Announce on entering the card library screen."""
        cursor = self._zone_cursors.get(_MENU_ZONE, 0)
        items = self.get_zone_items(_MENU_ZONE)
        total = len(items)
        if items:
            self._speech.speak(
                f"Card Library, {items[cursor]}, {cursor + 1} of {total}"
            )

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        return {
            "up": lambda: self.move_in_zone(-1),
            "down": lambda: self.move_in_zone(1),
            "left": lambda: self.move_in_zone(-1),
            "right": lambda: self.move_in_zone(1),
            "enter": self.select_current,
            "home": self.jump_to_first,
            "end": self.jump_to_last,
        }
