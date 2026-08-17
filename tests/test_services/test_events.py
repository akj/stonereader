"""Verify the 11 event classes from D-06."""
from __future__ import annotations

import dataclasses

from stonereader.services import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    CardRemoved,
    CardRevealed,
    DamageDealt,
    GameEnded,
    GameEvent,
    GameStarted,
    MinionDied,
    MulliganDone,
    TurnChanged,
)


ALL_EVENTS = [
    GameStarted,
    GameEnded,
    TurnChanged,
    MulliganDone,
    CardDrawn,
    CardPlayed,
    CardRevealed,
    CardRemoved,
    AttackStarted,
    MinionDied,
    DamageDealt,
]


def test_all_events_inherit_from_game_event():
    for cls in ALL_EVENTS:
        assert issubclass(cls, GameEvent), f"{cls.__name__} must inherit GameEvent"


def test_all_events_are_frozen_dataclasses():
    for cls in ALL_EVENTS + [GameEvent]:
        name = cls.__name__
        assert dataclasses.is_dataclass(cls), f"{name} must be a dataclass"
        params = getattr(cls, "__dataclass_params__")
        assert params.frozen, f"{name} must be frozen"


def test_game_started_payload_shape():
    ev = GameStarted(
        timestamp=1.0,
        turn=0,
        player_class="MAGE",
        opponent_class="WARRIOR",
        game_type="CASUAL",
        format_type="STANDARD",
    )
    assert ev.player_class == "MAGE"
    assert ev.opponent_class == "WARRIOR"


def test_card_drawn_payload_shape():
    ev = CardDrawn(
        timestamp=1.0,
        turn=1,
        entity_id=42,
        card_id="EX1_001",
        base_card=None,
        name="Lightwell",
        controller=1,
    )
    assert ev.entity_id == 42
    assert ev.controller == 1


def test_event_count_is_11():
    assert len(ALL_EVENTS) == 11  # one short of D-06's "12 events incl. base"
    # 11 concrete + 1 base = 12 total exports
    from stonereader.services import __all__

    for name in [
        "GameEvent",
        "GameStarted",
        "GameEnded",
        "TurnChanged",
        "MulliganDone",
        "CardDrawn",
        "CardPlayed",
        "CardRevealed",
        "CardRemoved",
        "AttackStarted",
        "MinionDied",
        "DamageDealt",
    ]:
        assert name in __all__
