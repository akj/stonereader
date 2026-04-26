"""GameTracker facade — the single public service Phase 3 imports.

Owns the lifecycle of:
  - ProcessDetector (D-03): is Hearthstone running?
  - PowerLogWatcher (D-01): tail Power.log via wx.Timer
  - Parser (D-09/D-10): hslog wrapper
  - GameEngine (D-05/D-06/D-07): events + frozen GameState

Subscribers register via subscribe()/unsubscribe() (D-02). Each event is
delivered SYNCHRONOUSLY on the GUI thread; subscribers MUST NOT block.

A subscriber that raises will NOT prevent other subscribers from receiving
the event (Pitfall 3 / T-2-04). Iteration is over a snapshot copy so a
subscriber that calls unsubscribe() from inside its own handler doesn't
break the loop (T-2-04b).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional

from stonereader.models.card import CardDatabase
from stonereader.models.game_state import GameState
from stonereader.services._engine import GameEngine
from stonereader.services._events import GameEnded, GameEvent
from stonereader.services._log_path import discover_power_log_path
from stonereader.services._parser import Parser
from stonereader.services._process_detect import ProcessDetector
from stonereader.services._watcher import PowerLogWatcher

logger = logging.getLogger(__name__)

SubscriberCallback = Callable[[GameEvent, Optional[GameState]], None]


class GameTracker:
    """Public facade — the only services symbol Phase 3 should need.

    Lifecycle:
        tracker = GameTracker(card_db=card_db)
        tracker.subscribe(my_callback)
        tracker.start(parent=frame)  # AFTER frame.Show() (Pitfall 9)
        ...
        tracker.stop()  # idempotent (D-19)
    """

    def __init__(
        self,
        card_db: Optional[CardDatabase] = None,
        process_detector: Optional[ProcessDetector] = None,
    ) -> None:
        self._card_db = card_db
        self._process_detector = process_detector or ProcessDetector()
        self._parser = Parser()
        self._engine = GameEngine(card_db=card_db)
        self._watcher = PowerLogWatcher(
            path_provider=self._provide_path,
            on_lines=self._on_lines,
            on_reset=self._on_watcher_reset,
        )
        self._subscribers: List[SubscriberCallback] = []
        self._previously_running = False
        self._started = False

    # ------------------------------------------------------------- Public API

    def start(self, parent) -> None:
        """Start the underlying Timer parented to a wx.Window.

        Pitfall 9: call AFTER frame.Show().
        """
        if self._started:
            return
        self._watcher.start(parent)
        self._started = True
        logger.info("GameTracker started")

    def stop(self) -> None:
        """Stop the wx.Timer cleanly. D-19: idempotent; tracker state cleared."""
        if not self._started:
            return
        self._watcher.stop()
        self._engine.reset()
        self._parser.reset()
        self._started = False
        logger.info("GameTracker stopped")

    def subscribe(self, callback: SubscriberCallback) -> None:
        """Register a subscriber for engine events.

        Each event delivers (event, current_state). One subscriber raising
        will not prevent other subscribers from receiving the event
        (Pitfall 3 / T-2-04).
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: SubscriberCallback) -> None:
        """Remove a previously-subscribed callback. No-op if not registered."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    @property
    def current_state(self) -> Optional[GameState]:
        """Return the latest frozen GameState snapshot, or None before any game."""
        return self._engine.current_state

    # ------------------------------------------------------------ Internals

    def _provide_path(self) -> Optional[Path]:
        """Watcher path_provider — checks process state every tick (D-03)."""
        running, _ = self._process_detector.is_running()
        if running != self._previously_running:
            if not running:
                # Hearthstone disappeared — emit synthetic GameEnded if a game
                # was running and reset internal state.
                self._handle_process_gone()
            self._previously_running = running
        if not running:
            return None
        return discover_power_log_path(self._process_detector.get_install_dir())

    def _handle_process_gone(self) -> None:
        """Hearthstone exited — reset state and notify subscribers."""
        logger.info("Hearthstone process gone — resetting tracker state")
        state = self._engine.current_state
        if state is not None and state.game_state == "RUNNING":
            self._dispatch(
                GameEnded(
                    timestamp=0.0,
                    turn=state.turn,
                    player_playstate="",
                    opponent_playstate="",
                ),
                state,
            )
        self._engine.reset()
        self._parser.reset()
        # invalidate_cache() is best-effort — test doubles may not implement it.
        invalidate = getattr(self._process_detector, "invalidate_cache", None)
        if callable(invalidate):
            invalidate()

    def _on_watcher_reset(self) -> None:
        """Watcher detected file rotation. Reset parser + engine."""
        logger.info("Watcher reset — Power.log rotated or file disappeared")
        self._parser.reset()
        self._engine.reset()

    def _on_lines(self, lines: List[str]) -> None:
        """Watcher delivered new lines — push through parser and engine."""
        for line in lines:
            try:
                packets = self._parser.feed_line(line)
            except Exception:
                logger.exception("parser failed on line; skipping")
                continue
            for pkt in packets:
                try:
                    events = self._engine.apply(pkt)
                except Exception:
                    logger.exception(
                        "engine failed on packet %s", type(pkt).__name__
                    )
                    continue
                for event in events:
                    self._dispatch(event, self._engine.current_state)

    def _dispatch(self, event: GameEvent, state: Optional[GameState]) -> None:
        """Deliver event to all subscribers — isolating each (Pitfall 3)."""
        for callback in list(self._subscribers):
            try:
                callback(event, state)
            except Exception:
                logger.exception(
                    "subscriber raised — continuing with remaining subscribers"
                )
