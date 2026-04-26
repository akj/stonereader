"""Tests for stonereader.services._tracker (Plan 02-07 Task 1).

Covers:
- subscribe/unsubscribe API (D-02)
- subscriber exception isolation (Pitfall 3 / T-2-04)
- process-gone resets tracker state (D-03)
- start/stop is idempotent and the wx.Timer reference clears (D-19 / LOG-05)
"""
from __future__ import annotations

import logging

import pytest


def test_subscribe_unsubscribe():
    from stonereader.services import GameTracker

    tracker = GameTracker()

    def cb(event, state):
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
    from stonereader.services import GameStarted, GameTracker

    tracker = GameTracker()
    good_called = []

    def bad(event, state):
        raise RuntimeError("boom")

    def good(event, state):
        good_called.append(event)

    tracker.subscribe(bad)
    tracker.subscribe(good)

    event = GameStarted(
        timestamp=0.0,
        turn=0,
        player_class="MAGE",
        opponent_class="WARRIOR",
        game_type="CASUAL",
        format_type="STANDARD",
    )
    with caplog.at_level(logging.ERROR):
        tracker._dispatch(event, None)

    assert len(good_called) == 1, "good subscriber must still receive event after bad raises"
    assert any("subscriber raised" in rec.message for rec in caplog.records)


def test_process_gone_resets_state(mock_process_detector):
    from stonereader.services import GameTracker

    tracker = GameTracker(process_detector=mock_process_detector)

    # Simulate Hearthstone running — _provide_path records that running == True
    mock_process_detector.set_running(True, exe_dir=None)
    tracker._provide_path()
    assert tracker._previously_running is True

    # Process gone — _provide_path returns None and flips _previously_running
    mock_process_detector.set_running(False)
    path = tracker._provide_path()
    assert path is None
    assert tracker._previously_running is False


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
