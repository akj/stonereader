"""Tests for stonereader.services._tracker (Plan 02-07 Task 1).

Covers:
- subscribe/unsubscribe API (D-02)
- subscriber exception isolation (Pitfall 3 / T-2-04)
- process-gone publishes ABANDONED state (issue #5)
- start/stop is idempotent and the wx.Timer reference clears (D-19 / LOG-05)

Issue #5: subscribers receive (prev, curr) GameState pairs, not events.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Optional

import pytest

from stonereader.models.game_state import GameState, Hero


def _make_running_state(turn: int = 1) -> GameState:
    hero = Hero(id="?", name="?", health=30, armor=0, hero_power="", hero_class="")
    return GameState(
        turn=turn,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=hero,
        opponent_hero=hero,
        game_state="RUNNING",
    )


def test_subscribe_unsubscribe():
    from stonereader.services import GameTracker

    tracker = GameTracker()

    def cb(prev: Optional[GameState], curr: GameState) -> None:
        return None

    tracker.subscribe(cb)
    assert cb in tracker._subscribers
    # Subscribing the same callback twice is a no-op (idempotent).
    tracker.subscribe(cb)
    assert tracker._subscribers.count(cb) == 1
    tracker.unsubscribe(cb)
    assert cb not in tracker._subscribers
    # Unsubscribing a callback that was never registered is a no-op.
    tracker.unsubscribe(cb)


def test_subscriber_exception_does_not_break_others(caplog):
    from stonereader.services import GameTracker

    tracker = GameTracker()
    good_called: list[tuple[Optional[GameState], GameState]] = []

    def bad(prev: Optional[GameState], curr: GameState) -> None:
        raise RuntimeError("boom")

    def good(prev: Optional[GameState], curr: GameState) -> None:
        good_called.append((prev, curr))

    tracker.subscribe(bad)
    tracker.subscribe(good)

    curr = _make_running_state()
    with caplog.at_level(logging.ERROR):
        tracker._dispatch(None, curr)

    assert len(good_called) == 1, (
        "good subscriber must still receive pair after bad raises"
    )
    assert good_called[0] == (None, curr)
    assert any("subscriber raised" in rec.message for rec in caplog.records)


def test_process_gone_publishes_abandoned_state(mock_process_detector):
    """Issue #5: when Hearthstone disappears mid-game, tracker dispatches a
    final (running_prev, abandoned_curr) pair instead of a synthetic event.
    """
    from stonereader.services import GameTracker

    tracker = GameTracker(process_detector=mock_process_detector)

    received: list[tuple[Optional[GameState], GameState]] = []
    tracker.subscribe(lambda prev, curr: received.append((prev, curr)))

    # Simulate a running game by stashing a RUNNING state as last published.
    running = _make_running_state(turn=7)
    tracker._last_published = running

    # Process running → not running.
    mock_process_detector.set_running(True, exe_dir=None)
    tracker._provide_path()
    mock_process_detector.set_running(False)
    tracker._provide_path()

    assert len(received) == 1, f"expected one dispatch on process-gone, got {received}"
    prev, curr = received[0]
    assert prev is running
    assert curr.game_state == "ABANDONED"
    assert curr.turn == running.turn  # final state preserves prior turn
    # Internal state clears so a fresh game can start cleanly.
    assert tracker._last_published is None


def test_process_gone_skips_dispatch_when_no_game_running(mock_process_detector):
    """If no game was in progress, process-gone is silent (no synthetic state)."""
    from stonereader.services import GameTracker

    tracker = GameTracker(process_detector=mock_process_detector)

    received: list[tuple[Optional[GameState], GameState]] = []
    tracker.subscribe(lambda prev, curr: received.append((prev, curr)))

    # No _last_published — nothing to abandon.
    mock_process_detector.set_running(True, exe_dir=None)
    tracker._provide_path()
    mock_process_detector.set_running(False)
    path = tracker._provide_path()

    assert path is None
    assert received == []


def test_process_gone_skips_dispatch_for_completed_game(mock_process_detector):
    """A COMPLETE game is already terminal; process-gone does not republish it."""
    from stonereader.services import GameTracker

    tracker = GameTracker(process_detector=mock_process_detector)

    received: list[tuple[Optional[GameState], GameState]] = []
    tracker.subscribe(lambda prev, curr: received.append((prev, curr)))

    completed = dataclasses.replace(_make_running_state(turn=12), game_state="COMPLETE")
    tracker._last_published = completed

    mock_process_detector.set_running(True, exe_dir=None)
    tracker._provide_path()
    mock_process_detector.set_running(False)
    tracker._provide_path()

    assert received == []


def test_configured_existing_log_path_wins_when_process_is_running(
    mock_process_detector,
    tmp_path,
):
    from stonereader.services import GameTracker

    custom = tmp_path / "Power.log"
    custom.write_text("", encoding="utf-8")
    mock_process_detector.set_running(True, exe_dir=None)
    tracker = GameTracker(
        process_detector=mock_process_detector,
        log_path_provider=lambda: custom,
    )

    assert tracker._provide_path() == custom


def test_start_stop_clean():
    wx = pytest.importorskip("wx")
    from stonereader.services import GameTracker

    app = wx.App()
    try:
        frame = wx.Frame(None)
        try:
            tracker = GameTracker()
            tracker.start(frame)
            assert tracker._started is True

            tracker.stop()
            assert tracker._started is False

            # stop() is idempotent — second call must not raise.
            tracker.stop()
            assert tracker._started is False
        finally:
            frame.Destroy()
    finally:
        app.Destroy()


# --- PRD #7: raw-line / reset fan-out seam (used by the replay recorder) ------


def test_add_raw_subscriber_forwards_lines_before_parsing():
    from stonereader.services import GameTracker

    tracker = GameTracker()
    seen: list[list[str]] = []
    tracker.add_raw_subscriber(lambda lines: seen.append(list(lines)), lambda: None)

    # Non-Power.log lines produce no packets, isolating the raw fan-out.
    tracker._on_lines(["alpha", "beta"])

    assert seen == [["alpha", "beta"]]


def test_add_raw_subscriber_forwards_reset():
    from stonereader.services import GameTracker

    tracker = GameTracker()
    resets: list[int] = []
    tracker.add_raw_subscriber(lambda lines: None, lambda: resets.append(1))

    tracker._on_watcher_reset()

    assert resets == [1]


def test_raw_line_listener_exception_is_isolated(caplog):
    from stonereader.services import GameTracker

    tracker = GameTracker()
    good_seen: list[list[str]] = []
    tracker.add_raw_subscriber(
        lambda lines: (_ for _ in ()).throw(RuntimeError("boom")), lambda: None
    )
    tracker.add_raw_subscriber(
        lambda lines: good_seen.append(list(lines)), lambda: None
    )

    with caplog.at_level(logging.ERROR):
        tracker._on_lines(["x"])  # must not raise

    assert good_seen == [["x"]], "a raising raw listener must not break others"
