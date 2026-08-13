"""Shared hslog PacketTree -> internal Packet translator (D-10).

This module is the single place that knows how to turn an hslog ``PacketTree``
(``hslog.packets.*``) into the ordered list of StoneReader internal
``_packets.*`` the engine consumes. It is used by BOTH:

* the live :class:`stonereader.services._parser.Parser`, which feeds lines into
  an ``hslog.LogParser`` incrementally and delegates per-packet translation and
  the tree-walk recursion here, and
* the future Replay loader, which parses a whole ``.log`` file into a complete
  ``PacketTree`` and calls :func:`translate_packet_tree` on it directly.

It imports ONLY hslog packet types and ``stonereader.services._packets`` — no
wx, no I/O, no clock. Keeping it pure lets a Replay loader reuse the exact same
translation the live pipeline uses, guaranteeing the two paths agree.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from hslog import packets as hslog_packets

from stonereader.services._packets import (
    BlockEndPacket,
    BlockStartPacket,
    ChangeEntityPacket,
    CreateGamePacket,
    FullEntityPacket,
    HideEntityPacket,
    Packet,
    ShowEntityPacket,
    TagChangePacket,
)


def translate_packet_tree(tree: Any) -> List[Packet]:
    """Flatten an hslog ``PacketTree`` into ordered internal ``Packet`` objects.

    Walks ``tree.packets`` in order, recursing into ``Block.packets`` children.
    For each ``Block`` node a :class:`BlockStartPacket` is emitted, then its
    children, then a matching :class:`BlockEndPacket` (only when the block was
    actually closed in the log, i.e. ``ended`` is true). ``packet_id`` is
    assigned monotonically from 0 in emission order.

    This is a PURE function: it has no I/O, no clock, and no hslog parsing —
    it only translates an already-parsed tree. The live ``Parser`` reuses the
    same per-packet helpers below so the incremental and whole-file paths
    produce identical packet sequences.
    """
    out: List[Packet] = []
    counter = _IdCounter()
    _walk_tree(getattr(tree, "packets", []) or [], out, counter.next)
    return out


class _IdCounter:
    """Monotonic packet-id allocator used by the pure whole-tree walk."""

    def __init__(self, start: int = 0) -> None:
        self._next = start

    def next(self) -> int:
        i = self._next
        self._next += 1
        return i


def _walk_tree(
    hslog_pkts: Any,
    out: List[Packet],
    next_id: Callable[[], int],
) -> None:
    """Recursively walk hslog packets, appending translated internal packets.

    Block nodes emit a BlockStartPacket, then their children, then (if the
    block closed) a BlockEndPacket. Leaf packets are translated via
    :func:`translate_packet`.
    """
    for hp in hslog_pkts:
        if isinstance(hp, hslog_packets.Block):
            out.append(make_block_start(hp, next_id()))
            _walk_tree(getattr(hp, "packets", []) or [], out, next_id)
            if getattr(hp, "ended", False):
                out.append(make_block_end(hp, next_id()))
            continue
        translated = translate_packet(hp, next_id)
        if translated is not None:
            out.append(translated)


def translate_packet(hp: Any, next_id: Callable[[], int]) -> Optional[Packet]:
    """Translate a single non-Block hslog leaf packet to an internal Packet.

    Returns ``None`` for packet types the engine does not consume in v1
    (MetaData, Choices, ResetGame). ``next_id`` is a callable yielding the
    next monotonic packet id; it is only invoked when a packet is actually
    produced, so skipped packets never consume an id.

    Block packets are intentionally NOT handled here — the BlockStart /
    BlockEnd pair is emitted by the walker (or, for the live parser, around
    the recursion into block children). Use :func:`make_block_start` /
    :func:`make_block_end` for those.
    """
    if isinstance(hp, hslog_packets.CreateGame):
        players = tuple(
            (
                # entity_id is on PlayerReference (Player.entity is a
                # PlayerReference with .entity_id, not a plain int).
                player_entity_id(p),
                getattr(p, "player_id", 0) or 0,  # player_id (PlayerID=N)
                player_name(p),
                getattr(p, "hi", 0) or 0,
                getattr(p, "lo", 0) or 0,
            )
            for p in getattr(hp, "players", []) or []
        )
        return CreateGamePacket(
            packet_id=next_id(),
            game_entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
            players=players,
            initial_tags=tags_to_dict(getattr(hp, "tags", None)),
        )
    if isinstance(hp, hslog_packets.TagChange):
        return TagChangePacket(
            packet_id=next_id(),
            entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
            tag=tag_name(getattr(hp, "tag", "")),
            value=enum_to_int(getattr(hp, "value", 0)),
            source_id=getattr(hp, "source", None),
        )
    if isinstance(hp, hslog_packets.FullEntity):
        return FullEntityPacket(
            packet_id=next_id(),
            entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
            card_id=str(getattr(hp, "card_id", "") or ""),
            tags=tags_to_dict(getattr(hp, "tags", None)),
        )
    if isinstance(hp, hslog_packets.ShowEntity):
        return ShowEntityPacket(
            packet_id=next_id(),
            entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
            card_id=str(getattr(hp, "card_id", "") or ""),
            tags=tags_to_dict(getattr(hp, "tags", None)),
        )
    if isinstance(hp, hslog_packets.HideEntity):
        return HideEntityPacket(
            packet_id=next_id(),
            entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
            # zone may be a Zone enum or an int
            zone=enum_to_int(getattr(hp, "zone", 0)),
        )
    if isinstance(hp, hslog_packets.ChangeEntity):
        return ChangeEntityPacket(
            packet_id=next_id(),
            entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
            card_id=str(getattr(hp, "card_id", "") or ""),
            tags=tags_to_dict(getattr(hp, "tags", None)),
        )
    # MetaData, Choices, ResetGame — not consumed by engine in v1
    return None


def make_block_start(hp: Any, packet_id: int) -> BlockStartPacket:
    """Build a BlockStartPacket from an hslog Block node."""
    return BlockStartPacket(
        packet_id=packet_id,
        block_type=block_type_name(hp),
        entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
        # Block uses .target (not .target_id) and .suboption (not .sub_option)
        target_id=getattr(hp, "target", None),
        sub_option=getattr(hp, "suboption", None),
    )


def make_block_end(hp: Any, packet_id: int) -> BlockEndPacket:
    """Build the synthetic BlockEndPacket emitted after a Block's children."""
    return BlockEndPacket(
        packet_id=packet_id,
        block_type=block_type_name(hp),
        entity_id=normalize_entity_id(getattr(hp, "entity", 0)),
    )


def normalize_entity_id(entity: Any) -> int:
    """Coerce hslog's ``entity`` (int or PlayerReference) to a plain int.

    gap-closure 03-07 (Rule 3): hslog emits TAG_CHANGE on player entities
    with ``entity`` set to a PlayerReference (not an int). The engine keys
    ``_entities`` by integer entity_id, so without normalization the player
    entity rows recorded under int 2/3 (from CreateGame) never match the
    TagChange lookups for RESOURCES, RESOURCES_USED, MAXRESOURCES, etc.
    """
    if entity is None:
        return 0
    if isinstance(entity, int):
        return entity
    eid = getattr(entity, "entity_id", None)
    if isinstance(eid, int):
        return eid
    try:
        return int(entity)
    except (TypeError, ValueError):
        return 0


def tag_name(tag: Any) -> str:
    """Return tag name string. hslog gives us either an enum or an int."""
    if hasattr(tag, "name"):
        return tag.name
    return str(tag)


def player_entity_id(p: Any) -> int:
    """Extract the integer EntityID from a hslog Player record.

    Player.entity is a PlayerReference (with .entity_id) when hslog
    successfully parsed an EntityID=N field; treat any other shape
    defensively and fall back to player_id.

    WR-04: shares the PlayerReference / int coercion logic with
    :func:`normalize_entity_id` so the two helpers cannot drift apart on
    future hslog shape changes. ``player_entity_id`` adds the ``player_id``
    fallback that ``normalize_entity_id`` does not need (TagChange paths
    have no ``player_id`` to fall back to).
    """
    ent = getattr(p, "entity", None)
    eid = normalize_entity_id(ent) if ent is not None else 0
    if eid:
        return eid
    return int(getattr(p, "player_id", 0) or 0)


def player_name(p: Any) -> str:
    """Extract a printable name. Prefer Player.name, fall back to
    PlayerReference.name (set by hslog when the player resolves).
    """
    name = getattr(p, "name", None)
    if name:
        return str(name)
    ent = getattr(p, "entity", None)
    ref_name = getattr(ent, "name", None) if ent is not None else None
    if ref_name:
        return str(ref_name)
    return ""


def block_type_name(hp: Any) -> str:
    """Return block type name string from a Block packet."""
    t = getattr(hp, "type", None)
    if t is None:
        return ""
    if hasattr(t, "name"):
        return t.name
    return str(t)


def enum_to_int(value: Any) -> int:
    """Convert an enum value or int to a plain int."""
    if hasattr(value, "value"):
        return int(value.value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def tags_to_dict(tags: Any) -> dict:
    """Convert hslog tags (list of (GameTag, value) tuples) to a str-keyed dict.

    hslog stores tags as a list of 2-tuples: [(GameTag.ZONE, Zone.DECK), ...].
    We flatten to {tag_name: int_value} for the engine.
    """
    if not tags:
        return {}
    result: dict = {}
    for item in tags:
        try:
            tag, value = item
            tag_str = tag.name if hasattr(tag, "name") else str(tag)
            int_value = int(value.value) if hasattr(value, "value") else int(value)
            result[tag_str] = int_value
        except (TypeError, ValueError, AttributeError):
            # Malformed tag entry — skip rather than crash.
            continue
    return result
