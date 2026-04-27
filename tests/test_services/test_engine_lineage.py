"""Stub tests for D-19 creation-lineage tracking (Wave 0 scaffolding).

Each stub names a behavior locked by 03-VALIDATION.md D-19 rows, plus
additional cases required by 03-REVIEWS.md MEDIUM 03-03 (nested-block
subject selection, lineage survives later SHOW_ENTITY reveal).
Production code lands in plan 03-03; tests flip from xfail to passing
when that plan completes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    strict=False,
    reason="Wave 0 stub - implementation lands in plan 03-03",
)


def test_lineage_recorded() -> None:
    """D-19: Synthetic BLOCK_START POWER + FULL_ENTITY in opponent HAND
    records lineage pointing at the block subject (creator card_id).
    Implementation target: plan 03-03.
    """
    pytest.xfail("not implemented yet — plan 03-03")


def test_no_lineage_for_normal_draw() -> None:
    """D-19: TAG_CHANGE outside any POWER block (a normal draw step) does
    NOT record lineage on the drawn card.
    Implementation target: plan 03-03.
    """
    pytest.xfail("not implemented yet — plan 03-03")


def test_no_lineage_for_friendly() -> None:
    """D-19: Same generation pattern but for a friendly entity — no
    lineage recorded (lineage is opponent-hand-only since the friendly
    card_id is already known).
    Implementation target: plan 03-03.
    """
    pytest.xfail("not implemented yet — plan 03-03")


def test_lineage_nested_blocks() -> None:
    """D-19 (NEW per 03-REVIEWS.md MEDIUM 03-03 #1): Nested POWER blocks
    (outer subject A, inner subject B, FULL_ENTITY arrives inside inner
    block) — lineage points at the INNERMOST subject (top of
    `_block_subjects` stack).
    Implementation target: plan 03-03.
    """
    pytest.xfail("not implemented yet — plan 03-03")


def test_show_entity_after_lineage() -> None:
    """D-19 (NEW per 03-REVIEWS.md MEDIUM 03-03 #2): A hidden hand entity
    gets lineage on FULL_ENTITY arrival; later SHOW_ENTITY reveals the
    card_id but lineage is preserved (sticky once set).
    Implementation target: plan 03-03.
    """
    pytest.xfail("not implemented yet — plan 03-03")


def test_reconnect_drops_lineage(power_log_fixture) -> None:
    """D-19 (Pitfall 7): `reconnect.log` second CREATE_GAME drops prior
    lineage — lineage state does NOT leak across game boundaries.
    Implementation target: plan 03-03.
    """
    power_log_fixture("reconnect.log")
    pytest.xfail("not implemented yet — plan 03-03")
