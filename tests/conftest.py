"""Shared test fixtures."""

from __future__ import annotations

from typing import Callable, List, Optional

from stonereader.models.game_state import GameState


SubscriberCallback = Callable[[Optional[GameState], GameState], None]


class MockGameTracker:
    """Test double for GameTracker — exposes subscribe/unsubscribe/current_state.

    Mirrors the public surface from stonereader.services._tracker.GameTracker
    without needing real wx, hslog, or Power.log access. Tests drive
    `dispatch(prev, curr)` directly to simulate engine state publication.

    Idempotent subscribe and per-subscriber exception isolation match the
    production GameTracker._dispatch contract (Phase 2 D-02, Pitfall 3).

    Exceptions raised inside subscribers during `dispatch` are CAPTURED in
    `self.caught_exceptions` rather than re-raised — this matches production
    behavior, but keeps debugging visibility for tests that need to verify
    exception isolation explicitly (per 03-REVIEWS.md 03-01 LOW concern).
    """

    def __init__(self) -> None:
        self._subscribers: List[SubscriberCallback] = []
        self._current_state: Optional[GameState] = None
        # Visible to tests so isolation behavior can be asserted (rather
        # than silently swallowed). Production GameTracker logs via
        # `logger.exception` in `_dispatch`; here we capture for inspection.
        self.caught_exceptions: List[Exception] = []

    def subscribe(self, callback: SubscriberCallback) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: SubscriberCallback) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    @property
    def current_state(self) -> Optional[GameState]:
        return self._current_state

    def set_state(self, state: Optional[GameState]) -> None:
        """Test helper: stash the state mock returns from `current_state`."""
        self._current_state = state

    def dispatch(
        self, prev: Optional[GameState], curr: GameState
    ) -> None:
        """Test helper: deliver (prev, curr) to every subscriber synchronously.

        Mirrors `GameTracker._dispatch` exception-isolation: one raising
        subscriber does NOT prevent later subscribers from receiving the
        pair. The exception is captured in `self.caught_exceptions` so
        tests can assert on isolation without losing the original error.
        """
        self._current_state = curr
        for cb in list(self._subscribers):
            try:
                cb(prev, curr)
            except Exception as exc:
                # Capture for visibility (do NOT re-raise — production
                # GameTracker._dispatch isolates subscribers identically).
                self.caught_exceptions.append(exc)
