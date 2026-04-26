"""Tests for stonereader.services._engine."""
from __future__ import annotations

import dataclasses
import time

import pytest

pytest.importorskip("stonereader.services._engine")

from stonereader.services._engine import GameEngine
from stonereader.services._events import GameStarted
from stonereader.services._packets import CreateGamePacket, TagChangePacket
from stonereader.services._parser import Parser


def test_emits_frozen_gamestate_snapshots():
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=((2, "P1", 1, 1), (3, "P2", 2, 2)),
        )
    )
    state = engine.current_state
    assert state is not None
    # Frozen
    try:
        state.turn = 99  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("GameState must be frozen")


def test_mid_game_fixture_emits_expected_events(power_log_fixture):
    path = power_log_fixture("mid_game.log")  # skips if absent
    parser = Parser()
    engine = GameEngine()
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        for pkt in parser.feed_line(line):
            events.extend(engine.apply(pkt))
    assert any(
        isinstance(e, GameStarted) for e in events
    ), "mid_game.log must contain CREATE_GAME and emit GameStarted"


def test_dual_source_fixture_no_duplicates(power_log_fixture):
    # Real fixtures contain both PowerTaskList and GameState lines.
    # Parser drops PowerTaskList; engine sees only GameState packets.
    # Therefore: feeding the same fixture once vs feeding it once with
    # PowerTaskList lines stripped must produce identical event counts.
    path = power_log_fixture("mid_game.log")
    text = path.read_text(encoding="utf-8")
    # Run 1: full fixture
    p1, e1 = Parser(), GameEngine()
    evs1 = []
    for line in text.splitlines():
        for pkt in p1.feed_line(line):
            evs1.extend(e1.apply(pkt))
    # Run 2: only GameState lines
    gs_only = "\n".join(line for line in text.splitlines() if "GameState." in line)
    p2, e2 = Parser(), GameEngine()
    evs2 = []
    for line in gs_only.splitlines():
        for pkt in p2.feed_line(line):
            evs2.extend(e2.apply(pkt))
    assert len(evs1) == len(
        evs2
    ), f"Duplicate detection failed: full={len(evs1)} GameState-only={len(evs2)}"


def test_tick_under_50ms(power_log_fixture):
    path = power_log_fixture("mid_game.log")
    # Take first 1000 lines (a single-tick worst case)
    lines = path.read_text(encoding="utf-8").splitlines()[:1000]
    parser = Parser()
    engine = GameEngine()
    start = time.perf_counter()
    for line in lines:
        for pkt in parser.feed_line(line):
            engine.apply(pkt)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 50, f"Tick took {elapsed_ms:.1f}ms (budget 50ms)"
