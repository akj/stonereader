"""GameTracker facade — the single public service Phase 3 imports.

Owns the lifecycle of:
  - ProcessDetector (D-03): is Hearthstone running?
  - PowerLogWatcher (D-01): tail Power.log via wx.Timer
  - Parser (D-09/D-10): hslog wrapper
  - GameEngine (D-05/D-06/D-07): pure Packet → GameState reducer

Subscribers register via subscribe()/unsubscribe() (D-02). Each (prev, curr)
GameState pair is delivered SYNCHRONOUSLY on the GUI thread; subscribers
MUST NOT block. Subscribers that want event-typed information call
`stonereader.services.diff` themselves (issue #5).

A subscriber that raises will NOT prevent other subscribers from receiving
the pair (Pitfall 3 / T-2-04). Iteration is over a snapshot copy so a
subscriber that calls unsubscribe() from inside its own handler doesn't
break the loop (T-2-04b).
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Callable, List, Optional

from stonereader.models.card import CardDatabase
from stonereader.models.game_state import GameState
from stonereader.services._engine import GameEngine
from stonereader.services._log_path import discover_power_log_path
from stonereader.services._parser import Parser
from stonereader.services._process_detect import ProcessDetector
from stonereader.services._watcher import PowerLogWatcher

logger = logging.getLogger(__name__)

SubscriberCallback = Callable[[Optional[GameState], GameState], None]


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
        log_path_provider: Callable[[], Optional[Path]] | None = None,
    ) -> None:
        self._card_db = card_db
        self._process_detector = process_detector or ProcessDetector()
        self._log_path_provider = log_path_provider
        self._parser = Parser()
        self._engine = GameEngine(card_db=card_db)
        self._watcher = PowerLogWatcher(
            path_provider=self._provide_path,
            on_lines=self._on_lines,
            on_reset=self._on_watcher_reset,
        )
        self._subscribers: List[SubscriberCallback] = []
        # Raw fan-out (PRD #7): the replay recorder needs the verbatim Power.log
        # lines BEFORE parsing, plus reset signals, so it can buffer a game's
        # excerpt and convert it to HSReplay XML on completion. These run ahead
        # of the parser/engine in _on_lines so a game's lines are buffered before
        # the COMPLETE (prev, curr) dispatch fires.
        self._raw_line_listeners: List[Callable[[List[str]], None]] = []
        self._raw_reset_listeners: List[Callable[[], None]] = []
        self._previously_running = False
        self._started = False
        # Issue #5: tracker holds the previously-published state so each
        # apply() call dispatches (prev, curr) where prev is the snapshot
        # before this packet's mutations and curr is the engine's new state.
        self._last_published: Optional[GameState] = None

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
        self._last_published = None
        self._started = False
        logger.info("GameTracker stopped")

    def subscribe(self, callback: SubscriberCallback) -> None:
        """Register a subscriber for (prev, curr) GameState pairs.

        Each call delivers (prev, curr); subscribers derive events via
        stonereader.services.diff(prev, curr) when they want event-typed
        information. One subscriber raising will not prevent other
        subscribers from receiving the pair (Pitfall 3 / T-2-04).
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: SubscriberCallback) -> None:
        """Remove a previously-subscribed callback. No-op if not registered."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def add_raw_subscriber(
        self,
        on_lines: Callable[[List[str]], None],
        on_reset: Callable[[], None],
    ) -> None:
        """Register a listener for raw Power.log lines and reset signals (PRD #7).

        ``on_lines`` receives the verbatim line batch BEFORE the parser/engine
        consume it; ``on_reset`` fires on Power.log rotation. Used by the replay
        recorder to buffer the live game's Power.log excerpt. Listener failures
        are isolated and never disturb live tracking.
        """
        self._raw_line_listeners.append(on_lines)
        self._raw_reset_listeners.append(on_reset)

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
                # Hearthstone disappeared — publish a final ABANDONED state if
                # a game was running and reset internal state.
                self._handle_process_gone()
            self._previously_running = running
        if not running:
            return None
        if self._log_path_provider is not None:
            configured = self._log_path_provider()
            if configured is not None and configured.exists():
                return configured
        return discover_power_log_path(self._process_detector.get_install_dir())

    def _handle_process_gone(self) -> None:
        """Hearthstone exited — publish a final ABANDONED state and reset."""
        logger.info("Hearthstone process gone — resetting tracker state")
        prev = self._last_published
        if prev is not None and prev.game_state == "RUNNING":
            abandoned = dataclasses.replace(prev, game_state="ABANDONED")
            self._dispatch(prev, abandoned)
        self._engine.reset()
        self._parser.reset()
        self._last_published = None
        # invalidate_cache() is best-effort — test doubles may not implement it.
        invalidate = getattr(self._process_detector, "invalidate_cache", None)
        if callable(invalidate):
            invalidate()

    def _on_watcher_reset(self) -> None:
        """Watcher detected file rotation. Reset parser + engine."""
        logger.info("Watcher reset — Power.log rotated or file disappeared")
        self._parser.reset()
        self._engine.reset()
        self._last_published = None
        for listener in list(self._raw_reset_listeners):
            try:
                listener()
            except Exception:
                logger.exception("raw reset listener raised — continuing")

    def _on_lines(self, lines: List[str]) -> None:
        """Watcher delivered new lines — push through parser and engine.

        After every packet apply(), if engine.current_state changed, dispatch
        (prev, curr) to subscribers (issue #5).
        """
        # Fan raw lines out to recorders BEFORE parsing, so a completing game's
        # lines are buffered before its COMPLETE (prev, curr) dispatch (PRD #7).
        for listener in list(self._raw_line_listeners):
            try:
                listener(lines)
            except Exception:
                logger.exception("raw line listener raised — continuing")
        for line in lines:
            try:
                packets = self._parser.feed_line(line)
            except Exception:
                logger.exception("parser failed on line; skipping")
                continue
            for pkt in packets:
                prev = self._last_published
                try:
                    self._engine.apply(pkt)
                except Exception:
                    logger.exception("engine failed on packet %s", type(pkt).__name__)
                    continue
                curr = self._engine.current_state
                if curr is None or curr is prev:
                    continue
                self._last_published = curr
                self._dispatch(prev, curr)

    def _dispatch(self, prev: Optional[GameState], curr: GameState) -> None:
        """Deliver (prev, curr) to all subscribers — isolating each (Pitfall 3)."""
        for callback in list(self._subscribers):
            try:
                callback(prev, curr)
            except Exception:
                logger.exception(
                    "subscriber raised — continuing with remaining subscribers"
                )
