"""Home screen presenter -- navigate feature menu items."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService

_MENU_ZONE = "menu"

# Menu items -- order matches UI-SPEC home screen ListBox
MENU_ITEMS = ["Card Library", "Deck Manager", "Import Deck", "Live Game", "Replays"]


class HomePresenter(ZoneNavigationMixin, BasePresenter):
    """Manages home screen feature menu navigation."""

    def __init__(self, speech: SpeechService) -> None:
        super().__init__(speech)
        self._init_navigation([_MENU_ZONE])
        self._on_select: Callable[[str], None] | None = None

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _MENU_ZONE:
            return MENU_ITEMS
        return []

    def set_on_select(self, callback: Callable[[str], None]) -> None:
        """Set callback invoked when user presses Enter on a menu item."""
        self._on_select = callback

    def select_current(self) -> None:
        """Activate the currently highlighted menu item."""
        item = self._current_item()
        if item is not None and self._on_select is not None:
            self._on_select(str(item))

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
