"""Tests for stonereader.services._engine.

Issue #5: engine.apply() returns None; assertions read engine.current_state.
"""

from __future__ import annotations

import dataclasses
import time

import pytest

pytest.importorskip("stonereader.services._engine")

from stonereader.models.card import CardDatabase
from stonereader.services._diff import diff
from stonereader.services._engine import GameEngine
from stonereader.services._events import MinionDied
from stonereader.services._packets import (
    CreateGamePacket,
    FullEntityPacket,
    TagChangePacket,
)
from stonereader.services._parser import Parser


def test_apply_returns_none():
    """Issue #5: engine.apply is a pure mutator; subscribers diff state pairs."""
    engine = GameEngine()
    result = engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=((2, 1, "P1", 1, 1), (3, 2, "P2", 2, 2)),
        )
    )
    assert result is None


def test_emits_frozen_gamestate_snapshots():
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=((2, 1, "P1", 1, 1), (3, 2, "P2", 2, 2)),
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


def test_drawn_card_controller_reflects_log_controller():
    """state.opponent_drawn[i].controller is the raw CONTROLLER tag.

    WR-02: _friendly_player_id defaults to 1, so when the local player is
    assigned CONTROLLER=2 by the server (coin-flip), the entity buckets
    into opponent_drawn with the raw CONTROLLER tag (2). This test
    documents the existing behaviour so any future fix to
    _friendly_player_id can verify it doesn't regress raw-controller
    pass-through.
    """
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=(
                (2, 1, "LocalPlayer", 144115198130930503, 1),
                (3, 2, "Opponent", 144115198130930504, 2),
            ),
        )
    )
    # Register entity 10 as belonging to controller 2 with no zone yet.
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=10,
            card_id="CS2_023",
            tags={"CONTROLLER": 2, "ZONE": 0},  # Zone 0 = INVALID (not in hand yet)
        )
    )
    # Now entity 10 moves to HAND (Zone=3).
    engine.apply(TagChangePacket(packet_id=2, entity_id=10, tag="ZONE", value=3))
    state = engine.current_state
    assert state is not None
    drawn_for_eid = [pc for pc in state.opponent_drawn if pc.entity_id == 10]
    assert len(drawn_for_eid) == 1, (
        f"Expected one row for entity 10 in opponent_drawn; got {state.opponent_drawn}"
    )
    assert drawn_for_eid[0].controller == 2, (
        f"controller should be 2 (raw CONTROLLER tag), got {drawn_for_eid[0].controller}"
    )


def test_terminal_zone_entity_projected_to_graveyard():
    """A PLAY→GRAVEYARD entity must be projected into state.graveyard (with its
    terminal zone name) so the pure diff seam can still visit it.

    Before this projection the dead entity left every navigable zone, so the
    diff loop never visited it and the replay event drilldown silently dropped
    deaths/removals (PRD #7 / codex review round 4).
    """
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=((2, 1, "P1", 1, 1), (3, 2, "P2", 2, 2)),
        )
    )
    # A friendly (CONTROLLER=1) minion (CARDTYPE=4) alive in PLAY (ZONE=1).
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=10,
            card_id="EX1_001",
            tags={"CONTROLLER": 1, "ZONE": 1, "CARDTYPE": 4, "HEALTH": 3},
        )
    )
    prev = engine.current_state
    assert prev is not None
    assert [e.entity_id for e in prev.player_board] == [10]
    assert prev.graveyard == ()

    # The entity leaves play: ZONE -> GRAVEYARD (4).
    engine.apply(TagChangePacket(packet_id=2, entity_id=10, tag="ZONE", value=4))
    curr = engine.current_state
    assert curr is not None
    # It left the board and is now projected into the graveyard with the right zone.
    assert curr.player_board == ()
    assert [(e.entity_id, e.zone) for e in curr.graveyard] == [(10, "GRAVEYARD")]


def test_dead_minion_drives_minion_died_end_to_end():
    """End-to-end: a resolved MINION dying (PLAY→GRAVEYARD) projects into the
    graveyard and the diff seam emits MinionDied. The card type must resolve for
    the diff to distinguish a death from a removal, so this needs the
    CardDatabase (PRD #7 / codex review rounds 4-5).
    """
    try:
        card_db = CardDatabase.load()
    except Exception:  # pragma: no cover - environment-dependent fallback
        pytest.skip("CardDatabase unavailable (cardxml missing)")

    engine = GameEngine(card_db=card_db)
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=((2, 1, "P1", 1, 1), (3, 2, "P2", 2, 2)),
        )
    )
    # EX1_001 (Lightwarden) is a real MINION; CARDTYPE=4 places it on the board.
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=10,
            card_id="EX1_001",
            tags={"CONTROLLER": 1, "ZONE": 1, "CARDTYPE": 4, "HEALTH": 3},
        )
    )
    prev = engine.current_state
    assert prev is not None

    engine.apply(TagChangePacket(packet_id=2, entity_id=10, tag="ZONE", value=4))
    curr = engine.current_state
    assert curr is not None
    # The projected graveyard entity carries the resolved MINION card type.
    assert [e.card_type for e in curr.graveyard] == ["MINION"]

    deaths = [e for e in diff(prev, curr) if isinstance(e, MinionDied)]
    assert len(deaths) == 1
    assert deaths[0].entity_id == 10
    assert deaths[0].controller == 1


def test_mid_game_fixture_publishes_running_state(power_log_fixture):
    """mid_game.log contains CREATE_GAME → engine publishes a RUNNING state."""
    path = power_log_fixture("mid_game.log")  # skips if absent
    parser = Parser()
    engine = GameEngine()
    for line in path.read_text(encoding="utf-8").splitlines():
        for pkt in parser.feed_line(line):
            engine.apply(pkt)
    state = engine.current_state
    assert state is not None, (
        "mid_game.log must contain CREATE_GAME and publish a GameState"
    )
    assert state.game_state == "RUNNING"


def test_dual_source_fixture_no_duplicate_state_changes(power_log_fixture):
    """Real fixtures contain both PowerTaskList and GameState lines.

    Parser drops PowerTaskList; engine sees only GameState packets. Feeding
    the full fixture must produce the same final GameState as feeding only
    the GameState-prefixed lines.
    """
    path = power_log_fixture("mid_game.log")
    text = path.read_text(encoding="utf-8")
    # Run 1: full fixture
    p1, e1 = Parser(), GameEngine()
    for line in text.splitlines():
        for pkt in p1.feed_line(line):
            e1.apply(pkt)
    # Run 2: only GameState lines
    gs_only = "\n".join(line for line in text.splitlines() if "GameState." in line)
    p2, e2 = Parser(), GameEngine()
    for line in gs_only.splitlines():
        for pkt in p2.feed_line(line):
            e2.apply(pkt)
    s1, s2 = e1.current_state, e2.current_state
    assert s1 is not None and s2 is not None
    assert s1.turn == s2.turn
    assert s1.game_state == s2.game_state
    assert s1.player_deck_count == s2.player_deck_count
    assert s1.opponent_deck_count == s2.opponent_deck_count
    assert len(s1.player_drawn) == len(s2.player_drawn)
    assert len(s1.opponent_drawn) == len(s2.opponent_drawn)
    assert len(s1.player_played) == len(s2.player_played)
    assert len(s1.opponent_played) == len(s2.opponent_played)


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
