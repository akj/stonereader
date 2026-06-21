"""Replays browser presenter — newest-first replay history (Slice #14).

Single-zone list screen over ReplayStore.all_replays() (which already orders
rows newest-first). Enter opens the selected replay via an on_open callback;
Delete removes it from the store and re-announces the new count.

Per CLAUDE.md MVP rule: all speech goes through the presenter; the view is
passive. Speech text is produced here via the ZoneNavigationMixin
_format_item_speech override.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.services._replay_store import ReplayMeta, ReplayStore
from stonereader.speech_service import SpeechService

_REPLAYS_ZONE = "replays"
_ZONE_LABEL = "Replays"


def format_replay_row(meta: ReplayMeta) -> str:
    """Visual/spoken core for one replay row (no N-of-M suffix).

    e.g. "Mage vs Warrior, Won, 12 turns, 2026-06-20".
    """
    friendly = meta.friendly_class.title()
    opponent = meta.opponent_class.title()
    result = meta.result.title()
    date = str(meta.played_at)[:10]
    turns = meta.turns
    turn_word = "turn" if turns == 1 else "turns"
    return f"{friendly} vs {opponent}, {result}, {turns} {turn_word}, {date}"


class ReplaysPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages newest-first replay history navigation (open / delete)."""

    def __init__(self, speech: SpeechService, store: ReplayStore) -> None:
        super().__init__(speech)
        self._init_navigation([_REPLAYS_ZONE])
        self._store = store
        self._on_open: Callable[[ReplayMeta], None] | None = None
        self._on_changed: Callable[[], None] | None = None
        self._rows: list[ReplayMeta] = []
        self.refresh()

    # -- zone source -----------------------------------------------------

    def get_zone_items(self, zone_name: str) -> Sequence[ReplayMeta]:
        if zone_name == _REPLAYS_ZONE:
            return self._rows
        return []

    def cursor_for_zone(self, zone_name: str) -> int:
        """Public read of the zone cursor — view uses this, not _zone_cursors."""
        return self._zone_cursors.get(zone_name, 0)

    def _format_item_speech(self, item: Any, position: int, total: int) -> str:
        return f"{format_replay_row(item)}, {position} of {total}"

    # -- callbacks -------------------------------------------------------

    def set_on_open(self, callback: Callable[[ReplayMeta], None]) -> None:
        """Set the callback invoked with the selected ReplayMeta on open."""
        self._on_open = callback

    def set_on_changed(self, callback: Callable[[], None]) -> None:
        """Set the callback the presenter fires after the row list changes."""
        self._on_changed = callback

    # -- actions ---------------------------------------------------------

    def open_current(self) -> None:
        """Invoke on_open with the selected replay (no-op if list empty)."""
        item = self._current_item()
        if item is not None and self._on_open is not None:
            self._on_open(item)

    def delete_current(self) -> None:
        """Delete the selected replay, refresh, and announce the new count."""
        item = self._current_item()
        if item is None:
            return
        self._store.delete(item.id)
        self.refresh()
        remaining = self._rows
        if not remaining:
            self._speech.speak("No replays")
        else:
            count = len(remaining)
            noun = "replay" if count == 1 else "replays"
            self._speech.speak(f"Deleted. {count} {noun}")

    def refresh(self) -> None:
        """Re-read the store's replays (newest-first) into the zone."""
        self._rows = list(self._store.all_replays())
        # Keep the cursor in range after the row count changes.
        cursor = self._zone_cursors.get(_REPLAYS_ZONE, 0)
        if self._rows:
            cursor = max(0, min(cursor, len(self._rows) - 1))
        else:
            cursor = 0
        self._zone_cursors[_REPLAYS_ZONE] = cursor
        self._notify_changed()

    def _notify_changed(self) -> None:
        """Fire the view callback so its selected row tracks the presenter cursor."""
        if self._on_changed is not None:
            self._on_changed()

    # -- navigation (notify the view so its selection follows the cursor) -

    def move_in_zone(self, delta: int) -> None:
        super().move_in_zone(delta)
        self._notify_changed()

    def jump_to_first(self) -> None:
        super().jump_to_first()
        self._notify_changed()

    def jump_to_last(self) -> None:
        super().jump_to_last()
        self._notify_changed()

    def announce_entry(self) -> None:
        """Spoken on entering the screen: zone label + count (or empty)."""
        count = len(self._rows)
        if count == 0:
            self._speech.speak("No replays")
            return
        noun = "replay" if count == 1 else "replays"
        self._speech.speak(f"{_ZONE_LABEL}, {count} {noun}")

    # -- key map ---------------------------------------------------------

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        return {
            "left": lambda: self.move_in_zone(-1),
            "right": lambda: self.move_in_zone(1),
            "home": self.jump_to_first,
            "end": self.jump_to_last,
            "enter": self.open_current,
            "delete": self.delete_current,
        }
