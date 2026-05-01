"""Live Game presenter — subscribe to GameTracker, expose 4 zones for SR navigation.

Zones (D-05 + LIVE-03 cards_drawn per 03-REVIEWS.md HIGH #1):
    remaining_deck — sorted (Card, count) tuples; D-13 row format.
    opponent_hand  — OpponentHandRow per visible opponent-hand entity; D-14 format.
    opponent_played — PlayedCard list; D-15 format.
    cards_drawn    — PlayedCard list, most-recent-first; LIVE-03 ("cards drawn this game").

Subscriber contract (D-07): _on_state NEVER calls SpeechService. Speech
only happens via user-initiated paths (navigate_to_zone / move_in_zone /
announce_deck_counts / announce_opponent_hand_count / jump_to_zone /
read_detail_lines).

Auto-detection (D-10/D-11): runs once when player_deck reaches 30 revealed
cards; strict multiset match (0 or 2+ → Unknown deck).

Public accessors for view/app/tests (per 03-REVIEWS.md HIGH #3):
    current_title() -> str
    cursor_for_zone(zone_name) -> int
    detected_deck_name() -> Optional[str]
    current_state_snapshot() -> Optional[GameState]
    current_mana_summary() -> str
    announce_opponent_hand_count() -> None  (speak-only)
    announce_deck_counts() -> None          (speak-only)
    jump_to_zone(zone_name) -> None
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

from stonereader.db import get_all_decks
from stonereader.models.card import Card, CardDatabase
from stonereader.models.deck import Deck, DeckSummary
from stonereader.models.game_state import GameState, PlayedCard
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.services import GameTracker
from stonereader.services._diff import diff
from stonereader.services._events import (
    GameEnded,
    GameStarted,
)
from stonereader.speech_service import SpeechService

_REMAINING_DECK_ZONE = "remaining_deck"
_OPPONENT_HAND_ZONE = "opponent_hand"
_OPPONENT_PLAYED_ZONE = "opponent_played"
_CARDS_DRAWN_ZONE = "cards_drawn"  # LIVE-03 per 03-REVIEWS.md HIGH #1.

_ZONE_LABELS = {
    _REMAINING_DECK_ZONE: "Remaining deck zone",
    _OPPONENT_HAND_ZONE: "Opponent hand zone",
    _OPPONENT_PLAYED_ZONE: "Opponent played zone",
    _CARDS_DRAWN_ZONE: "Cards drawn zone",
}

# Pitfall 8: non-Constructed modes (Battlegrounds, Arena) don't reveal 30 cards.
_NON_CONSTRUCTED_GAME_TYPES = {"BATTLEGROUNDS", "ARENA"}


@dataclass(frozen=True)
class OpponentHandRow:
    """Presenter-layer view of an opponent-hand entity (D-14 row shape)."""

    position: int
    identity: Optional[Card]
    drawn_turn: int
    lineage: str


class LiveGamePresenter(ZoneNavigationMixin, BasePresenter):
    """Four-zone presenter for live Hearthstone game state."""

    def __init__(
        self,
        speech: SpeechService,
        db_conn: sqlite3.Connection,
        tracker: GameTracker,
        card_db: CardDatabase,
    ) -> None:
        super().__init__(speech)
        self._db_conn = db_conn
        self._tracker = tracker
        self._card_db = card_db
        self._init_navigation(
            [
                _REMAINING_DECK_ZONE,
                _OPPONENT_HAND_ZONE,
                _OPPONENT_PLAYED_ZONE,
                _CARDS_DRAWN_ZONE,
            ]
        )
        # Per-game cache.
        self._current_state: Optional[GameState] = None
        self._detected_deck_name: Optional[str] = None
        self._detection_attempted: bool = False
        self._original_deck_cards: Optional[Tuple[Tuple[Card, int], ...]] = None
        # View-callback fields.
        self._on_state_changed: Optional[Callable[[], None]] = None
        self._on_title_changed: Optional[Callable[[str], None]] = None
        # Subscribe to tracker.
        self._tracker.subscribe(self._on_state)

    # ---------------------------------------------- Lifecycle / Subscription

    def cleanup(self) -> None:
        """Unsubscribe from tracker. Idempotent."""
        self._tracker.unsubscribe(self._on_state)

    def _on_state(
        self, prev: Optional[GameState], curr: GameState
    ) -> None:
        """Subscriber entrypoint (issue #5). NEVER calls speech (D-07).

        Lifecycle branches re-derive via diff(prev, curr); the presenter
        does not depend on the engine constructing GameStarted/GameEnded.
        """
        self._current_state = curr
        events = diff(prev, curr)
        if any(isinstance(ev, GameStarted) for ev in events):
            self._detected_deck_name = None
            self._detection_attempted = False
            self._original_deck_cards = None
            for zone in self._zone_cursors:
                self._zone_cursors[zone] = 0
            self._notify_view()
            return
        if any(isinstance(ev, GameEnded) for ev in events):
            self._notify_view()
            return
        if (
            not self._detection_attempted
            and curr.game_type not in _NON_CONSTRUCTED_GAME_TYPES
        ):
            revealed_count = sum(
                1 for e in curr.player_deck if e.card_id
            )
            if revealed_count >= 30:
                self._run_auto_detection(curr)
                self._detection_attempted = True
        self._notify_view()

    # ---------------------------------------------- Auto-detection (D-10/D-11)

    def _run_auto_detection(self, state: GameState) -> None:
        revealed: Counter = Counter(
            e.card_id for e in state.player_deck if e.card_id
        )
        if sum(revealed.values()) != 30:
            return
        matches: List[Tuple[DeckSummary, Deck]] = []
        for deck_summary in get_all_decks(self._db_conn):
            try:
                parsed = Deck.from_deckstring(
                    deck_summary.deckstring,
                    self._card_db,
                    name=deck_summary.name,
                    allow_unknown=True,
                )
            except Exception:
                continue  # Malformed deckstring — skip silently (V11 mitigation).
            deck_counts: Counter = Counter()
            for card, count in parsed.cards:
                deck_counts[card.id] += count
            if deck_counts == revealed:
                matches.append((deck_summary, parsed))
        if len(matches) == 1:
            self._detected_deck_name = matches[0][0].name
            self._original_deck_cards = matches[0][1].cards
        else:
            self._detected_deck_name = None
            self._original_deck_cards = None

    # ---------------------------------------------- Zone items + speech

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _REMAINING_DECK_ZONE:
            return self._compute_remaining_deck()
        if zone_name == _OPPONENT_HAND_ZONE:
            return self._compute_opponent_hand_view()
        if zone_name == _OPPONENT_PLAYED_ZONE:
            state = self._current_state
            return list(state.opponent_played) if state else []
        if zone_name == _CARDS_DRAWN_ZONE:
            return self._compute_cards_drawn_view()
        return []

    def _compute_remaining_deck(self) -> List[Tuple[Card, int]]:
        state = self._current_state
        if state is None:
            return []
        if self._detected_deck_name and self._original_deck_cards:
            drawn_counts: Counter = Counter(
                pc.card_id for pc in state.player_drawn if pc.card_id
            )
            rows: List[Tuple[Card, int]] = []
            for card, original_count in self._original_deck_cards:
                remaining = max(0, original_count - drawn_counts.get(card.id, 0))
                rows.append((card, remaining))
            rows.sort(key=lambda r: (r[0].cost, r[0].name))
            return rows
        counts: dict[str, int] = {}
        cards: dict[str, Card] = {}
        for entity in state.player_deck:
            if entity.base_card is None or not entity.card_id:
                continue
            counts[entity.card_id] = counts.get(entity.card_id, 0) + 1
            cards[entity.card_id] = entity.base_card
        grouped = [(cards[cid], counts[cid]) for cid in counts]
        grouped.sort(key=lambda pair: (pair[0].cost, pair[0].name))
        return grouped

    def _compute_opponent_hand_view(self) -> List[OpponentHandRow]:
        state = self._current_state
        if state is None:
            return []
        rows: List[OpponentHandRow] = []
        for idx, entity in enumerate(state.opponent_hand):
            if entity is None:
                continue
            rows.append(
                OpponentHandRow(
                    position=idx + 1,
                    identity=entity.base_card,
                    drawn_turn=entity.drawn_turn,
                    lineage=entity.creation_lineage,
                )
            )
        return rows

    def _compute_cards_drawn_view(self) -> List[PlayedCard]:
        """LIVE-03: cards drawn this game, most-recently-drawn first."""
        state = self._current_state
        if state is None:
            return []
        return list(reversed(state.player_drawn))

    def _format_item_speech(
        self, item: Any, position: int, total: int
    ) -> str:
        suffix = f", {position} of {total}"
        zone = self._current_zone
        if zone == _REMAINING_DECK_ZONE and isinstance(item, tuple) and len(item) == 2:
            card, count = item
            copies = "1 copy" if count == 1 else f"{count} copies"
            return f"{card.name}, {copies}" + suffix
        if zone == _OPPONENT_HAND_ZONE and isinstance(item, OpponentHandRow):
            identity = item.identity.name if item.identity else "unknown"
            # 03-REVIEWS.md MEDIUM #5: drawn_turn==-1 → "unknown".
            turn_str = "unknown" if item.drawn_turn == -1 else str(item.drawn_turn)
            if item.lineage:
                return (
                    f"Position {item.position}, {identity}, generated by "
                    f"{item.lineage} turn {turn_str}" + suffix
                )
            return (
                f"Position {item.position}, {identity}, "
                f"drawn turn {turn_str}" + suffix
            )
        if zone == _OPPONENT_PLAYED_ZONE and isinstance(item, PlayedCard):
            return f"Turn {item.turn}, {item.name}" + suffix
        if zone == _CARDS_DRAWN_ZONE and isinstance(item, PlayedCard):
            # LIVE-03: "Turn 3, Fireball, drawn" (suffix added afterward).
            return f"Turn {item.turn}, {item.name}, drawn" + suffix
        return super()._format_item_speech(item, position, total)

    # ---------------------------------------------- View / callbacks

    def set_on_state_changed(self, callback: Callable[[], None]) -> None:
        self._on_state_changed = callback

    def set_on_title_changed(self, callback: Callable[[str], None]) -> None:
        self._on_title_changed = callback

    def _notify_view(self) -> None:
        if self._on_state_changed is not None:
            self._on_state_changed()
        if self._on_title_changed is not None:
            self._on_title_changed(self.current_title())

    # ---------------------------------------------- Public accessors (REVIEWS HIGH #3)

    def current_title(self) -> str:
        """Panel title text. Public accessor — view/tests use this, not _format_title."""
        state = self._current_state
        if state is None:
            return "No game in progress"
        player_class = (state.player_hero.hero_class or "").strip()
        opponent_class = (state.opponent_hero.hero_class or "").strip()
        matchup = " vs ".join(filter(None, [player_class, opponent_class])) or "Game"
        deck_name = self._detected_deck_name or "Unknown deck"
        return f"{matchup} — {deck_name}"

    def cursor_for_zone(self, zone_name: str) -> int:
        """Public read of zone cursor — view uses this instead of _zone_cursors."""
        return self._zone_cursors.get(zone_name, 0)

    def detected_deck_name(self) -> Optional[str]:
        """Public read of detection result."""
        return self._detected_deck_name

    def current_state_snapshot(self) -> Optional[GameState]:
        """Public read of last-cached GameState — app uses this instead of _current_state."""
        return self._current_state

    def current_mana_summary(self) -> str:
        """Panel-only mana surfacing (LIVE-07; Open Q2: no separate hotkey)."""
        state = self._current_state
        if state is None:
            return ""
        return (
            f"You {state.player_mana}/{state.player_max_mana}, "
            f"opponent {state.opponent_mana}/{state.opponent_max_mana}"
        )

    # ---------------------------------------------- Hotkey-callable surface

    def jump_to_zone(self, zone_name: str) -> None:
        """Public entry for global hotkeys (browse-open) and home menu."""
        label = _ZONE_LABELS.get(zone_name, zone_name)
        items = self.get_zone_items(zone_name)
        self._current_zone = zone_name
        if not items:
            self._speech.speak(f"{label}: empty")
            return
        cursor = self._zone_cursors.get(zone_name, 0)
        cursor = max(0, min(cursor, len(items) - 1))
        self._zone_cursors[zone_name] = cursor
        first_row = self._format_item_speech(items[cursor], cursor + 1, len(items))
        self._speech.speak(f"{label}, {len(items)} cards. {first_row}")

    def announce_deck_counts(self) -> None:
        """LIVE-06 / D-16: 'N left, opponent M.' via speak-only hotkey."""
        state = self._current_state
        if state is None:
            self._speech.speak("No game in progress.")
            return
        self._speech.speak(
            f"{state.player_deck_count} left, "
            f"opponent {state.opponent_deck_count}."
        )

    def announce_opponent_hand_count(self) -> None:
        """LIVE-05 / 03-REVIEWS.md HIGH #3: 'Opponent has N cards.' speak-only hotkey.

        Public accessor so the app wiring does not bypass presenter
        ownership of speech and state interpretation.
        """
        state = self._current_state
        if state is None:
            self._speech.speak("No game in progress.")
            return
        count = sum(1 for e in state.opponent_hand if e is not None)
        self._speech.speak(f"Opponent has {count} cards.")

    # ---------------------------------------------- Nav overrides

    def move_in_zone(self, delta: int) -> None:
        super().move_in_zone(delta)
        self._notify_view()

    def jump_to_first(self) -> None:
        super().jump_to_first()
        self._notify_view()

    def jump_to_last(self) -> None:
        super().jump_to_last()
        self._notify_view()

    def read_detail_lines(self, item: Any, direction: int = 1) -> None:
        card: Optional[Card] = None
        if isinstance(item, OpponentHandRow):
            card = item.identity
        elif isinstance(item, PlayedCard):
            card = item.base_card
        if card is None:
            super().read_detail_lines(item, direction)
            return
        super().read_detail_lines(card, direction)

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        # 10 keys total per 03-UI-SPEC §"Keyboard Contract" + 03-CHECKER blocker #1.
        # Number keys 1/2/3/4 switch among the 4 zones (matches "zone keys are
        # always global — no enter/exit required" rule from CLAUDE.md).
        return {
            "left": lambda: self.move_in_zone(-1),
            "right": lambda: self.move_in_zone(1),
            "down": lambda: self.read_detail_lines(self._current_item(), 1),
            "up": lambda: self.read_detail_lines(self._current_item(), -1),
            "home": self.jump_to_first,
            "end": self.jump_to_last,
            "1": lambda: self.navigate_to_zone(_REMAINING_DECK_ZONE, "Remaining Deck"),
            "2": lambda: self.navigate_to_zone(_OPPONENT_PLAYED_ZONE, "Opponent Played"),
            "3": lambda: self.navigate_to_zone(_OPPONENT_HAND_ZONE, "Opponent Hand"),
            "4": lambda: self.navigate_to_zone(_CARDS_DRAWN_ZONE, "Cards Drawn"),
        }
