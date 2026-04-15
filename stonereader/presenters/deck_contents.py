"""Deck contents presenter -- browse cards in a selected deck."""

from __future__ import annotations

from typing import Any, Callable, Sequence, Tuple

from stonereader.models.card import Card
from stonereader.models.deck import Deck
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService

_CARDS_ZONE = "cards"


class DeckContentsPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages card list navigation for a single deck's contents."""

    def __init__(self, speech: SpeechService, deck: Deck) -> None:
        super().__init__(speech)
        self._deck = deck
        self._cards: list[Tuple[Card, int]] = list(deck.cards)
        self._init_navigation([_CARDS_ZONE])
        self._on_state_changed: Callable[
            [list[Tuple[Card, int]], int], None
        ] | None = None

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _CARDS_ZONE:
            return self._cards
        return []

    def set_on_state_changed(
        self, callback: Callable[[list[Tuple[Card, int]], int], None]
    ) -> None:
        self._on_state_changed = callback

    def _notify_view(self) -> None:
        if self._on_state_changed is not None:
            cursor = self._zone_cursors.get(_CARDS_ZONE, 0)
            self._on_state_changed(self._cards, cursor)

    def move_in_zone(self, delta: int) -> None:
        super().move_in_zone(delta)
        self._notify_view()

    def jump_to_first(self) -> None:
        super().jump_to_first()
        self._notify_view()

    def jump_to_last(self) -> None:
        super().jump_to_last()
        self._notify_view()

    def announce_deck_header(self) -> None:
        """Speak deck metadata when first entering the deck view.

        Format: '{Deck name}: {total} cards, {Class}, {Format}'
        Per UI-SPEC speech format contract.
        """
        total = self._deck.total_cards()
        self._speech.speak(
            f"{self._deck.name}: {total} cards, "
            f"{self._deck.hero_class}, {self._deck.format}"
        )

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
