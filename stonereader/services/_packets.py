"""Internal Packet representation isolated from hslog (D-10).

Engine consumes these. Parser is the only translator from hslog.packets.*.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class Packet:
    """Base class for all internal packets.

    packet_id: monotonic id assigned by the parser to track which packets are new.
    """

    packet_id: int


@dataclass(frozen=True)
class CreateGamePacket(Packet):
    """The ``GameState.DebugPrintPower() - CREATE_GAME`` boundary.

    players is a tuple of (entity_id, player_id, name, hi, lo) per player.
    Both entity_id and player_id are retained (WR-02 / D-18): the engine's
    FriendlyPlayerExporter heuristic needs player_id distinctly from
    entity_id. hi/lo come from the Player's GameAccountId (lo == 0 marks
    an AI account).
    """

    game_entity_id: int
    players: Tuple[Tuple[int, int, str, int, int], ...] = ()
    initial_tags: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TagChangePacket(Packet):
    """A TAG_CHANGE packet — entity tag value changed."""

    entity_id: int
    tag: str  # GameTag enum name (e.g. "ZONE", "CONTROLLER", "PLAYSTATE")
    value: int  # Raw int value (engine resolves to enum names where useful)
    source_id: Optional[int] = None


@dataclass(frozen=True)
class BlockStartPacket(Packet):
    """A BLOCK_START packet — marks the beginning of a game action block."""

    block_type: str  # BlockType enum name (e.g. "ATTACK", "POWER", "PLAY")
    entity_id: int
    target_id: Optional[int] = None
    sub_option: Optional[int] = None


@dataclass(frozen=True)
class BlockEndPacket(Packet):
    """A synthetic BLOCK_END packet emitted after block children are walked."""

    block_type: str
    entity_id: int


@dataclass(frozen=True)
class FullEntityPacket(Packet):
    """A FULL_ENTITY packet — complete entity creation with all tags."""

    entity_id: int
    card_id: str  # may be empty string if hidden
    tags: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ShowEntityPacket(Packet):
    """Previously hidden entity is being revealed."""

    entity_id: int
    card_id: str
    tags: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class HideEntityPacket(Packet):
    """A HIDE_ENTITY packet — entity moved to a hidden zone."""

    entity_id: int
    zone: int  # raw Zone int (engine maps to name)


@dataclass(frozen=True)
class ChangeEntityPacket(Packet):
    """Entity transforms into a different card_id (e.g., Polymorph)."""

    entity_id: int
    card_id: str
    tags: Dict[str, int] = field(default_factory=dict)
