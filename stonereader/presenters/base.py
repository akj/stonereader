"""Base presenter and zone navigation mixin.

ZoneNavigationMixin provides cursor-per-zone navigation shared across all
presenters. Zone keys are always global (never modal). Each zone maintains
an independent cursor that persists across zone switches (DL-001).

BasePresenter holds the SpeechService reference and provides an announce()
convenience method.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from stonereader.speech_service import SpeechService


class BasePresenter:
    """Base class for all presenters."""

    def __init__(self, speech: SpeechService) -> None:
        self._speech = speech

    def announce(self, text: str) -> None:
        self._speech.speak(text)

    def get_key_map(self) -> Dict[str, Callable[[], None]]:
        """Return the key map for this presenter. Subclasses must override."""
        return {}


class ZoneNavigationMixin:
    """Cursor-per-zone navigation.

    Diminishing orienting messages (DL-008): handle_inapplicable_zone tracks
    per-key press counts. 1st = full help, 2nd = short, 3rd+ = silent.
    Counts reset on zone change.
    """

    _speech: SpeechService

    def _init_navigation(self, zones: List[str]) -> None:
        self._current_zone = zones[0] if zones else ""
        self._zone_cursors: Dict[str, int] = {z: 0 for z in zones}
        self._orienting_counts: Dict[str, int] = {}
        self._detail_cursor: int = -1

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        """Return item sequence for zone. Subclasses must override."""
        raise NotImplementedError

    def _format_item_speech(self, item: Any, position: int, total: int) -> str:
        suffix = f", {position} of {total}"
        if item is None:
            return "Unknown card" + suffix
        if isinstance(item, tuple) and len(item) == 2:
            card, count = item
            name = getattr(card, "name", str(card))
            return f"{name} x{count}" + suffix
        name = getattr(item, "name", str(item))
        return name + suffix

    def navigate_to_zone(self, zone_name: str, zone_label: str) -> None:
        self._current_zone = zone_name
        self._detail_cursor = 0
        self._orienting_counts.clear()
        items = self.get_zone_items(zone_name)
        if not items:
            self._speech.speak(f"{zone_label}: empty")
            return
        cursor = self._zone_cursors.get(zone_name, 0)
        cursor = max(0, min(cursor, len(items) - 1))
        self._zone_cursors[zone_name] = cursor
        text = f"{zone_label}, {self._format_item_speech(items[cursor], cursor + 1, len(items))}"
        self._speech.speak(text)

    def navigate_singleton_zone(
        self, zone_name: str, zone_label: str, content: str
    ) -> None:
        self._current_zone = zone_name
        self._detail_cursor = 0
        self._orienting_counts.clear()
        self._speech.speak(f"{zone_label}: {content}")

    def move_in_zone(self, delta: int) -> None:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        if not items:
            self._speech.speak(f"{zone}: empty")
            return
        cursor = self._zone_cursors.get(zone, 0) + delta
        cursor = max(0, min(cursor, len(items) - 1))
        self._zone_cursors[zone] = cursor
        self._detail_cursor = 0
        self._speech.speak(
            self._format_item_speech(items[cursor], cursor + 1, len(items))
        )

    def jump_to_position(self, pos: int) -> None:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        if not items:
            self._speech.speak(f"{zone}: empty")
            return
        cursor = max(0, min(pos - 1, len(items) - 1))
        self._zone_cursors[zone] = cursor
        self._detail_cursor = 0
        self._speech.speak(
            self._format_item_speech(items[cursor], cursor + 1, len(items))
        )

    def jump_to_first(self) -> None:
        self.jump_to_position(1)

    def jump_to_last(self) -> None:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        self.jump_to_position(len(items))

    def _current_item(self) -> Optional[Any]:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        if not items:
            return None
        cursor = self._zone_cursors.get(zone, 0)
        if cursor >= len(items):
            return None
        return items[cursor]

    def _extract_card(self, item: Any) -> Any:
        """Extract a Card from various item types."""
        from stonereader.models.card import Card
        from stonereader.models.game_state import GameEntity

        if isinstance(item, Card):
            return item
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], Card):
            return item[0]
        if isinstance(item, GameEntity) and item.base_card is not None:
            return item.base_card
        return None

    def read_detail_lines(self, item: Any, direction: int = 1) -> None:
        card = self._extract_card(item)
        if card is None:
            return
        lines = card.detail_lines()
        if not lines:
            return
        self._detail_cursor = max(
            0, min(self._detail_cursor + direction, len(lines) - 1)
        )
        self._speech.speak(lines[self._detail_cursor])

    def handle_inapplicable_zone(
        self, key: str, full_message: str, short_message: str
    ) -> None:
        count = self._orienting_counts.get(key, 0) + 1
        self._orienting_counts[key] = count
        if count == 1:
            self._speech.speak(full_message)
        elif count == 2:
            self._speech.speak(short_message)
