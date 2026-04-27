"""Stub tests for WR-02 friendly-player resolution (Wave 0 scaffolding).

Each stub names a behavior locked by 03-VALIDATION.md WR-02 rows, plus
`test_mixed_timing_fallback` required by 03-REVIEWS.md HIGH #2 (events
before AND after fallback resolution must both be correctly bucketed).
Production code lands in plan 03-02; tests flip from xfail to passing
when that plan completes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    strict=False,
    reason="Wave 0 stub - implementation lands in plan 03-02",
)


def test_local_is_player_2() -> None:
    """WR-02 / D-18: AI heuristic resolves friendly to Player 2 when local
    player has lo!=0 and opponent has lo==0 (AI).
    Implementation target: plan 03-02.
    """
    pytest.xfail("not implemented yet — plan 03-02")


def test_ai_heuristic() -> None:
    """WR-02: `lo == 0` is opponent (AI), `lo != 0` is friendly. Resolution
    happens at CREATE_GAME time when both players' BattleTags are visible.
    Implementation target: plan 03-02.
    """
    pytest.xfail("not implemented yet — plan 03-02")


def test_show_entity_fallback() -> None:
    """WR-02: Both players have `lo != 0` (PvP); first SHOW_ENTITY into a
    HAND zone determines friendly_player_id (the local client reveals its
    own hand cards before opponent's).
    Implementation target: plan 03-02.
    """
    pytest.xfail("not implemented yet — plan 03-02")


def test_mixed_timing_fallback() -> None:
    """WR-02 (NEW per 03-REVIEWS.md HIGH #2): Events arriving BEFORE
    fallback resolution AND more events AFTER fallback resolution must
    both be correctly attributed in the final state — re-bucket from
    authoritative `_entities` state, not just swap accumulated lists.
    Implementation target: plan 03-02.
    """
    pytest.xfail("not implemented yet — plan 03-02")


def test_captured_fixtures_resolve(power_log_fixture) -> None:
    """WR-02 regression lock: all 4 captured fixtures (match_start, mid_game,
    game_end, reconnect) produce friendly_player_id == 1 (vs-AI captures).
    Implementation target: plan 03-02.
    """
    # Touch the fixture loader so the test correctly skips if fixtures absent.
    power_log_fixture("match_start.log")
    pytest.xfail("not implemented yet — plan 03-02")


def test_reconnect_resolves_friendly(power_log_fixture) -> None:
    """WR-02 (NEW per 03-REVIEWS.md HIGH #2): Reconnect log (second
    CREATE_GAME) re-resolves `friendly_player_id` correctly without
    leaking prior-game state.
    Implementation target: plan 03-02.
    """
    power_log_fixture("reconnect.log")
    pytest.xfail("not implemented yet — plan 03-02")
