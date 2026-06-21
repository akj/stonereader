"""Tests for WR-02 friendly-player resolution (D-18).

Covers the AI-heuristic fast-path and the SHOW_ENTITY-into-HAND fallback
that mirror hslog.export.FriendlyPlayerExporter, mixed-timing event
re-attribution (03-REVIEWS.md HIGH #2), plus a regression lock against
the 4 captured Power.log fixtures (vs-AI captures must continue to
resolve friendly_player_id == 1) and a reconnect-specific test.
"""

from __future__ import annotations

import pytest

pytest.importorskip("stonereader.services._engine")

from stonereader.services._engine import GameEngine
from stonereader.services._packets import (
    CreateGamePacket,
    FullEntityPacket,
    ShowEntityPacket,
    TagChangePacket,
)
from stonereader.services._parser import Parser


def test_local_is_player_2() -> None:
    """AI heuristic: local player is Player 2 (CONTROLLER=2 by coin-flip)."""
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=(
                (2, 1, "AI Innkeeper", 0, 0),
                (3, 2, "LocalPlayer", 144115198130930503, 1),
            ),
        )
    )
    assert engine._friendly_player_id == 2
    assert engine._friendly_player_resolved is True


def test_ai_heuristic() -> None:
    """lo == 0 player is opponent (AI); lo != 0 player is friendly."""
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=(
                (2, 1, "LocalPlayer", 144115198130930503, 1),
                (3, 2, "AI Innkeeper", 0, 0),
            ),
        )
    )
    assert engine._friendly_player_id == 1
    assert engine._friendly_player_resolved is True


def test_show_entity_fallback() -> None:
    """Multiplayer (both lo != 0): first SHOW_ENTITY into HAND determines friendly."""
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=(
                (2, 1, "PlayerA", 144115198130930503, 1),
                (3, 2, "PlayerB", 144115198130930504, 2),
            ),
        )
    )
    # Default unresolved — engine keeps default 1.
    assert engine._friendly_player_id == 1
    assert engine._friendly_player_resolved is False
    # Pre-record entity 10 with controller 2 in some non-hand zone.
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=10,
            card_id="",
            tags={"CONTROLLER": 2, "ZONE": 0},
        )
    )
    # First SHOW_ENTITY into HAND on controller 2 → friendly is now 2.
    engine.apply(
        ShowEntityPacket(
            packet_id=2,
            entity_id=10,
            card_id="EX1_339",
            tags={"CONTROLLER": 2, "ZONE": 3},  # Zone 3 = HAND
        )
    )
    assert engine._friendly_player_id == 2
    assert engine._friendly_player_resolved is True


def test_mixed_timing_fallback() -> None:
    """03-REVIEWS.md HIGH #2: events fired BEFORE fallback resolution AND
    events fired AFTER fallback resolution must both end up in the correct
    bucket in the final GameState.

    Scenario: multiplayer game (both lo != 0). Player 2 is local.
    Sequence:
      1. CREATE_GAME — friendly defaults to 1 (wrong; will resolve to 2).
      2. Card A is drawn by controller 2 (the eventual friendly).
         Engine buckets it in opponent_drawn (because friendly==1).
      3. Card B is drawn by controller 1 (the eventual opponent).
         Engine buckets it in player_drawn (because friendly==1).
      4. SHOW_ENTITY into HAND on controller 2 → friendly resolves to 2.
      5. _rebucket_from_entities runs and re-attributes A and B authoritatively.
      6. Card C is drawn by controller 2 (friendly).
         Engine buckets it in player_drawn (because friendly==2 now).
      7. Card D is drawn by controller 1 (opponent).
         Engine buckets it in opponent_drawn.

    Final assertion: state.player_drawn contains A and C (controller 2);
    state.opponent_drawn contains B and D (controller 1).
    """
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=(
                (2, 1, "PlayerA", 144115198130930503, 1),
                (3, 2, "PlayerB", 144115198130930504, 2),
            ),
        )
    )
    # Pre-resolution: card A (controller 2) drawn.
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=100,
            card_id="A_CARD",
            tags={"CONTROLLER": 2, "ZONE": 2},  # 2 = DECK
        )
    )
    engine.apply(
        TagChangePacket(packet_id=2, entity_id=100, tag="ZONE", value=3),  # → HAND
    )
    # Pre-resolution: card B (controller 1) drawn.
    engine.apply(
        FullEntityPacket(
            packet_id=3,
            entity_id=101,
            card_id="B_CARD",
            tags={"CONTROLLER": 1, "ZONE": 2},
        )
    )
    engine.apply(
        TagChangePacket(packet_id=4, entity_id=101, tag="ZONE", value=3),
    )
    # Trigger fallback: SHOW_ENTITY for an entity with controller 2 into HAND.
    engine.apply(
        FullEntityPacket(
            packet_id=5,
            entity_id=200,
            card_id="",
            tags={"CONTROLLER": 2, "ZONE": 0},
        )
    )
    engine.apply(
        ShowEntityPacket(
            packet_id=6,
            entity_id=200,
            card_id="MULLIGAN_CARD",
            tags={"CONTROLLER": 2, "ZONE": 3},
        )
    )
    assert engine._friendly_player_id == 2
    assert engine._friendly_player_resolved is True
    # Post-resolution: card C (controller 2) drawn.
    engine.apply(
        FullEntityPacket(
            packet_id=7,
            entity_id=102,
            card_id="C_CARD",
            tags={"CONTROLLER": 2, "ZONE": 2},
        )
    )
    engine.apply(
        TagChangePacket(packet_id=8, entity_id=102, tag="ZONE", value=3),
    )
    # Post-resolution: card D (controller 1) drawn.
    engine.apply(
        FullEntityPacket(
            packet_id=9,
            entity_id=103,
            card_id="D_CARD",
            tags={"CONTROLLER": 1, "ZONE": 2},
        )
    )
    engine.apply(
        TagChangePacket(packet_id=10, entity_id=103, tag="ZONE", value=3),
    )
    state = engine.current_state
    assert state is not None
    # Friendly drawn must include entities 100 (A, ctrl 2) and 102 (C, ctrl 2).
    friendly_drawn_ids = sorted(r.entity_id for r in state.player_drawn)
    assert 100 in friendly_drawn_ids, (
        f"Pre-resolution card A (controller 2) should be re-attributed to friendly. "
        f"Got friendly_drawn ids: {friendly_drawn_ids}"
    )
    assert 102 in friendly_drawn_ids
    # Opponent drawn must include entities 101 (B, ctrl 1) and 103 (D, ctrl 1).
    opponent_drawn_ids = sorted(r.entity_id for r in state.opponent_drawn)
    assert 101 in opponent_drawn_ids, (
        f"Pre-resolution card B (controller 1) should remain in opponent. "
        f"Got opponent_drawn ids: {opponent_drawn_ids}"
    )
    assert 103 in opponent_drawn_ids


def test_captured_fixtures_resolve(power_log_fixture) -> None:
    """All 4 captured fixtures (vs-AI) must produce friendly_player_id == 1."""
    for name in ("match_start.log", "mid_game.log", "game_end.log", "reconnect.log"):
        path = power_log_fixture(name)  # skips if absent
        parser = Parser()
        engine = GameEngine()
        for line in path.read_text(encoding="utf-8").splitlines():
            for pkt in parser.feed_line(line):
                engine.apply(pkt)
        assert engine._friendly_player_id == 1, (
            f"{name}: expected friendly_player_id=1, got {engine._friendly_player_id}"
        )


def test_reconnect_resolves_friendly(power_log_fixture) -> None:
    """03-REVIEWS.md HIGH #2: reconnect log (second CREATE_GAME) re-resolves
    friendly without leaking prior-game state.

    The captured reconnect.log is a vs-AI capture, so both CREATE_GAMEs
    should resolve friendly_player_id=1. Verify that after the second
    CREATE_GAME, _friendly_player_resolved is True (re-fired the heuristic)
    and the value matches expectations.
    """
    path = power_log_fixture("reconnect.log")  # skips if absent
    parser = Parser()
    engine = GameEngine()
    for line in path.read_text(encoding="utf-8").splitlines():
        for pkt in parser.feed_line(line):
            engine.apply(pkt)
    # Final state: friendly is 1 (vs-AI capture).
    assert engine._friendly_player_id == 1
    assert engine._friendly_player_resolved is True


# --- force_friendly_player (replay loading; codex review finding) -------------


def _vs_ai_create() -> CreateGamePacket:
    """A CREATE_GAME whose AI heuristic resolves friendly = player 1."""
    return CreateGamePacket(
        packet_id=0,
        game_entity_id=1,
        players=(
            (2, 1, "LocalPlayer", 144115198130930503, 1),
            (3, 2, "AI Innkeeper", 0, 0),
        ),
    )


def test_force_friendly_player_overrides_heuristic() -> None:
    """A replay's friendly side is authoritative metadata. force_friendly_player
    must override the engine's CREATE_GAME heuristic result and mark it final so
    the SHOW_ENTITY fallback cannot change it. (Without this, the loader's
    pre-seed was wiped by CREATE_GAME's reset() and Player-2 replays could be
    oriented from the wrong side.)
    """
    engine = GameEngine()
    engine.apply(_vs_ai_create())
    assert engine._friendly_player_id == 1  # heuristic picked player 1

    engine.force_friendly_player(2)  # e.g. a Player-2 replay
    assert engine._friendly_player_id == 2
    assert engine._friendly_player_resolved is True


def test_force_friendly_player_ignores_out_of_range() -> None:
    """Out-of-range player ids are a no-op (defensive)."""
    engine = GameEngine()
    engine.apply(_vs_ai_create())
    before = engine._friendly_player_id
    engine.force_friendly_player(0)
    engine.force_friendly_player(99)
    assert engine._friendly_player_id == before
