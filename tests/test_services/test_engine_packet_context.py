"""Issue #3: packet-level context lifted onto GameState.

The engine continues to emit GameEvents as it does today. These tests assert on
GameState fields that mirror packet-level facts the engine currently tracks
privately (block_stack, mulligan completion, attack-in-progress), so a future
pure diff function can recover the same events without engine internals.

Pattern follows tests/test_services/test_engine_live_state.py: drive the engine
through representative packet sequences and assert on engine.current_state.
"""

from __future__ import annotations

import pytest

pytest.importorskip("stonereader.services._engine")

from stonereader.models.game_state import AttackInProgress, GameState
from stonereader.services._engine import GameEngine
from stonereader.services._packets import (
    BlockEndPacket,
    BlockStartPacket,
    CreateGamePacket,
    FullEntityPacket,
    TagChangePacket,
)

_MULLIGAN_DONE = 4  # hearthstone.enums.Mulligan.DONE


def _engine_with_game() -> GameEngine:
    """Engine with CREATE_GAME applied — gives us a published GameState to inspect."""
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=((2, 1, "P1", 1, 1), (3, 2, "P2", 2, 2)),
        )
    )
    assert engine.current_state is not None
    return engine


def _state(engine: GameEngine) -> GameState:
    state = engine.current_state
    assert state is not None
    return state


def test_block_stack_populates_on_block_start() -> None:
    """state.block_stack reflects the open block types when a BlockStart arrives."""
    engine = _engine_with_game()
    assert _state(engine).block_stack == ()

    engine.apply(BlockStartPacket(packet_id=1, block_type="POWER", entity_id=10))

    assert _state(engine).block_stack == ("POWER",)


def test_block_stack_pops_on_block_end() -> None:
    """state.block_stack pops the most recently opened block on BlockEnd."""
    engine = _engine_with_game()
    engine.apply(BlockStartPacket(packet_id=1, block_type="POWER", entity_id=10))
    engine.apply(BlockStartPacket(packet_id=2, block_type="ATTACK", entity_id=20))
    assert _state(engine).block_stack == ("POWER", "ATTACK")

    engine.apply(BlockEndPacket(packet_id=3, block_type="ATTACK", entity_id=20))
    assert _state(engine).block_stack == ("POWER",)

    engine.apply(BlockEndPacket(packet_id=4, block_type="POWER", entity_id=10))
    assert _state(engine).block_stack == ()


def test_attack_in_progress_populates_on_attack_block_start() -> None:
    """state.attack_in_progress mirrors the attacker/defender/controller payload
    that AttackStarted carries today."""
    engine = _engine_with_game()
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=42,
            card_id="CS2_023",
            tags={"CONTROLLER": 2},
        )
    )
    assert _state(engine).attack_in_progress is None

    engine.apply(
        BlockStartPacket(packet_id=2, block_type="ATTACK", entity_id=42, target_id=99)
    )

    assert _state(engine).attack_in_progress == AttackInProgress(
        attacker_entity_id=42,
        defender_entity_id=99,
        attacker_controller=2,
    )


def test_attack_in_progress_clears_on_block_end() -> None:
    """state.attack_in_progress returns to None when the ATTACK block closes."""
    engine = _engine_with_game()
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=42,
            card_id="CS2_023",
            tags={"CONTROLLER": 2},
        )
    )
    engine.apply(
        BlockStartPacket(packet_id=2, block_type="ATTACK", entity_id=42, target_id=99)
    )
    assert _state(engine).attack_in_progress is not None

    engine.apply(BlockEndPacket(packet_id=3, block_type="ATTACK", entity_id=42))

    assert _state(engine).attack_in_progress is None


def test_mulligan_complete_flips_on_mulligan_done() -> None:
    """state.mulligan_complete starts False and becomes True when MULLIGAN_STATE=DONE."""
    engine = _engine_with_game()
    assert _state(engine).mulligan_complete is False

    engine.apply(
        TagChangePacket(
            packet_id=1, entity_id=2, tag="MULLIGAN_STATE", value=_MULLIGAN_DONE
        )
    )

    assert _state(engine).mulligan_complete is True
