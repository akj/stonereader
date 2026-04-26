"""Wrap hslog.LogParser with isolation per D-10.

The engine and tracker never import hslog. This file is the only translator
from hslog.packets.* into our internal _packets.* types.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Set, Tuple

from hslog import LogParser
from hslog import packets as hslog_packets
from hslog.exceptions import (
    CorruptLogError,
    NoSuchEnum,
    ParsingError,
    RegexParsingError,
)

from stonereader.services._exceptions import ParserError
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

logger = logging.getLogger(__name__)


class Parser:
    """Translate Power.log lines into a stream of internal Packet objects.

    Stateful — accumulates hslog parser state across calls. After each feed_line
    the parser walks any newly-emitted hslog packets and translates them to
    internal Packet types. The engine consumes the returned list.

    Reset via ``reset()`` whenever the watcher detects a file rotation or
    Hearthstone process disappearance.
    """

    def __init__(self) -> None:
        self._hslog: LogParser = LogParser()
        self._seen_ids: Set[int] = set()
        self._next_packet_id: int = 0
        self._missing_enums_logged: Set[Tuple[str, Any]] = set()

    def reset(self) -> None:
        """Drop all hslog state and start fresh. Called on file rotation."""
        self._hslog = LogParser()
        self._seen_ids.clear()
        self._next_packet_id = 0
        # Keep _missing_enums_logged across resets — same enum drift appears
        # across multiple files after a Hearthstone patch.

    def feed_line(self, line: str) -> List[Packet]:
        """Feed one line and return any newly-emitted packets (zero or more)."""
        try:
            self._hslog.read_line(line)
        except RegexParsingError as exc:
            logger.warning("hslog regex parse failed: %s", exc)
            return []
        except NoSuchEnum as exc:
            key = ("NoSuchEnum", str(exc))
            if key not in self._missing_enums_logged:
                self._missing_enums_logged.add(key)
                logger.warning("hslog NoSuchEnum (logged once): %s", exc)
            return []
        except CorruptLogError as exc:
            logger.error("hslog corrupt-log error: %s", exc)
            raise ParserError(f"corrupt log: {exc}") from exc
        except ParsingError as exc:
            logger.warning("hslog generic parse error: %s", exc)
            return []
        except Exception:
            logger.exception("unexpected error in hslog.read_line")
            return []

        return self._collect_new_packets()

    def _collect_new_packets(self) -> List[Packet]:
        """Walk the in-progress packet tree and translate any unseen packets."""
        try:
            tree = self._hslog._parsing_state.packet_tree
        except AttributeError:
            # Different hslog version — soft-fail.
            return []
        if tree is None:
            return []
        out: List[Packet] = []
        self._walk(tree.packets, out)
        return out

    def _walk(self, hslog_pkts: Any, out: List[Packet]) -> None:
        """Recursively walk hslog packets and translate unseen ones."""
        for hp in hslog_pkts:
            pyid = id(hp)
            if pyid in self._seen_ids:
                # Recurse into block children even if the block itself was seen,
                # because new children may have been appended since last walk.
                if isinstance(hp, hslog_packets.Block):
                    self._walk(hp.packets, out)
                continue
            self._seen_ids.add(pyid)
            translated = self._translate(hp)
            if translated is not None:
                out.append(translated)
            if isinstance(hp, hslog_packets.Block):
                # Walk block children before emitting synthetic BlockEnd.
                self._walk(hp.packets, out)
                # Only emit BlockEnd if block is fully closed (ended=True).
                if getattr(hp, "ended", False):
                    out.append(
                        BlockEndPacket(
                            packet_id=self._next_id(),
                            block_type=self._block_type_name(hp),
                            entity_id=getattr(hp, "entity", 0) or 0,
                        )
                    )

    def _next_id(self) -> int:
        """Return next monotonic packet id."""
        i = self._next_packet_id
        self._next_packet_id += 1
        return i

    def _translate(self, hp: Any) -> Optional[Packet]:
        """Translate an hslog packet to internal Packet, or None to skip."""
        if isinstance(hp, hslog_packets.CreateGame):
            players = tuple(
                (
                    # Player uses .entity (EntityID) and .player_id (PlayerID)
                    getattr(p, "entity", 0) or getattr(p, "player_id", 0),
                    str(getattr(p, "name", "") or ""),
                    getattr(p, "hi", 0) or 0,
                    getattr(p, "lo", 0) or 0,
                )
                for p in getattr(hp, "players", []) or []
            )
            return CreateGamePacket(
                packet_id=self._next_id(),
                game_entity_id=getattr(hp, "entity", 0) or 0,
                players=players,
                initial_tags=self._tags_to_dict(getattr(hp, "tags", None)),
            )
        if isinstance(hp, hslog_packets.TagChange):
            return TagChangePacket(
                packet_id=self._next_id(),
                entity_id=getattr(hp, "entity", 0) or 0,
                tag=self._tag_name(getattr(hp, "tag", "")),
                value=self._enum_to_int(getattr(hp, "value", 0)),
                source_id=getattr(hp, "source", None),
            )
        if isinstance(hp, hslog_packets.Block):
            return BlockStartPacket(
                packet_id=self._next_id(),
                block_type=self._block_type_name(hp),
                entity_id=getattr(hp, "entity", 0) or 0,
                # Block uses .target (not .target_id) and .suboption (not .sub_option)
                target_id=getattr(hp, "target", None),
                sub_option=getattr(hp, "suboption", None),
            )
        if isinstance(hp, hslog_packets.FullEntity):
            return FullEntityPacket(
                packet_id=self._next_id(),
                entity_id=getattr(hp, "entity", 0) or 0,
                card_id=str(getattr(hp, "card_id", "") or ""),
                tags=self._tags_to_dict(getattr(hp, "tags", None)),
            )
        if isinstance(hp, hslog_packets.ShowEntity):
            return ShowEntityPacket(
                packet_id=self._next_id(),
                entity_id=getattr(hp, "entity", 0) or 0,
                card_id=str(getattr(hp, "card_id", "") or ""),
                tags=self._tags_to_dict(getattr(hp, "tags", None)),
            )
        if isinstance(hp, hslog_packets.HideEntity):
            return HideEntityPacket(
                packet_id=self._next_id(),
                entity_id=getattr(hp, "entity", 0) or 0,
                # zone may be a Zone enum or an int
                zone=self._enum_to_int(getattr(hp, "zone", 0)),
            )
        if isinstance(hp, hslog_packets.ChangeEntity):
            return ChangeEntityPacket(
                packet_id=self._next_id(),
                entity_id=getattr(hp, "entity", 0) or 0,
                card_id=str(getattr(hp, "card_id", "") or ""),
                tags=self._tags_to_dict(getattr(hp, "tags", None)),
            )
        # MetaData, Choices, ResetGame — not consumed by engine in v1
        return None

    @staticmethod
    def _tag_name(tag: Any) -> str:
        """Return tag name string. hslog gives us either an enum or an int."""
        if hasattr(tag, "name"):
            return tag.name
        return str(tag)

    @staticmethod
    def _block_type_name(hp: Any) -> str:
        """Return block type name string from a Block packet."""
        t = getattr(hp, "type", None)
        if t is None:
            return ""
        if hasattr(t, "name"):
            return t.name
        return str(t)

    @staticmethod
    def _enum_to_int(value: Any) -> int:
        """Convert an enum value or int to a plain int."""
        if hasattr(value, "value"):
            return int(value.value)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _tags_to_dict(tags: Any) -> dict:
        """Convert hslog tags (list of (GameTag, value) tuples) to a string-keyed dict.

        hslog stores tags as a list of 2-tuples: [(GameTag.ZONE, Zone.DECK), ...].
        We flatten to {tag_name: int_value} for the engine.
        """
        if not tags:
            return {}
        result: dict = {}
        for item in tags:
            try:
                tag, value = item
                tag_name = tag.name if hasattr(tag, "name") else str(tag)
                int_value = int(value.value) if hasattr(value, "value") else int(value)
                result[tag_name] = int_value
            except (TypeError, ValueError, AttributeError):
                # Malformed tag entry — skip rather than crash.
                continue
        return result
