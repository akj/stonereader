"""Exact saved-deck attribution for live games and replay backfills."""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Protocol

from stonereader.db import get_all_decks
from stonereader.models.card import CardDatabase
from stonereader.models.deck import Deck, DeckSummary
from stonereader.models.game_state import GameState
from stonereader.services._diff import diff
from stonereader.services._events import GameStarted

_NON_CONSTRUCTED_GAME_TYPES = {"BATTLEGROUNDS", "ARENA"}


class StatePublisher(Protocol):
    """The tracker subscription seam consumed by deck detection."""

    def subscribe(
        self, callback: Callable[[GameState | None, GameState], None]
    ) -> None: ...


def detect_deck(
    state: GameState,
    decks: Sequence[DeckSummary],
    card_db: CardDatabase,
) -> tuple[int, str] | None:
    """Return the sole exact 30-card saved-deck match, if one exists."""
    revealed = Counter(entity.card_id for entity in state.player_deck if entity.card_id)
    if sum(revealed.values()) != 30:
        return None

    matches: list[DeckSummary] = []
    for summary in decks:
        try:
            deck = Deck.from_deckstring(
                summary.deckstring,
                card_db,
                name=summary.name,
                allow_unknown=True,
            )
        except Exception:
            continue
        counts: Counter[str] = Counter()
        for card, count in deck.cards:
            if card.id:
                counts[card.id] += count
        if counts == revealed:
            matches.append(summary)
    if len(matches) != 1:
        return None
    match = matches[0]
    return match.deck_id, match.name


class DeckDetector:
    """Resolve one saved deck per Game and retain its name snapshot."""

    def __init__(
        self,
        tracker: StatePublisher,
        conn: sqlite3.Connection,
        card_db: CardDatabase,
    ) -> None:
        self._conn = conn
        self._card_db = card_db
        self._detected: tuple[int, str] | None = None
        self._attempted = False
        tracker.subscribe(self.on_state)

    def on_state(self, prev: GameState | None, curr: GameState) -> None:
        """Reset on Game start and attempt the exact match once at 30 cards."""
        if any(isinstance(event, GameStarted) for event in diff(prev, curr)):
            self._detected = None
            self._attempted = False
            return
        if self._attempted or curr.game_type in _NON_CONSTRUCTED_GAME_TYPES:
            return
        if sum(1 for entity in curr.player_deck if entity.card_id) < 30:
            return
        self._detected = detect_deck(curr, get_all_decks(self._conn), self._card_db)
        self._attempted = True

    def detected(self) -> tuple[int, str] | None:
        """Return ``(deck_id, name snapshot)`` for the current Game."""
        return self._detected
