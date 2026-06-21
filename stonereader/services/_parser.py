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

from stonereader.services import _hslog_translator as translator
from stonereader.services._exceptions import ParserError
from stonereader.services._packets import Packet

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
        # Block py-ids whose BlockEndPacket has already been emitted. A block's
        # BlockStart is emitted (and the block added to _seen_ids) the first
        # time it is walked, but the block may not be ``ended`` yet — hslog
        # closes it only when the BLOCK_END line is later parsed. We emit the
        # matching BlockEnd on the subsequent walk where it has closed, once.
        self._emitted_block_ends: Set[int] = set()
        self._next_packet_id: int = 0
        self._missing_enums_logged: Set[Tuple[str, Any]] = set()
        # Deferred emission tracking for CreateGame: hslog appends Player rows
        # to the in-progress CreateGame after the CREATE_GAME line is parsed,
        # so we cannot emit it on first sight. We defer until either a NEW
        # top-level packet appears after it OR the parser's entity_packet
        # state shows we have moved past the CreateGame's player block.
        self._pending_create_game_pyid: Optional[int] = None

    def reset(self) -> None:
        """Drop all hslog state and start fresh. Called on file rotation."""
        self._hslog = LogParser()
        self._seen_ids.clear()
        self._emitted_block_ends.clear()
        self._next_packet_id = 0
        self._pending_create_game_pyid = None
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

    def _walk(self, hslog_pkts: Any, out: List[Packet]) -> bool:
        """Recursively walk hslog packets and translate unseen ones, IN ORDER.

        Per-packet translation and packet construction are delegated to
        :mod:`stonereader.services._hslog_translator` (the shared, pure
        translator the Replay loader also uses). This method owns only the
        live-incremental concerns hslog forces on us: deferring emission while
        a packet is still being built, deduping via py-id, and emitting a
        block's BlockEnd on the walk where the block has closed.

        Emission is strictly tree-ordered: the walk HALTS at the first packet
        that is not ready yet — a CreateGame/entity packet hslog is still
        building, or a block whose BlockEnd cannot be emitted yet. Halting
        (rather than skipping ahead) keeps a later sibling, or a block's own
        BlockEnd, from jumping in front of a deferred child; otherwise the live
        stream diverges from ``translate_packet_tree`` over the same tree and the
        engine processes packets outside their block context. The deferred
        packet settles on a later line and the next walk resumes from it.

        Returns True if the walk halted (the caller must stop too), False if it
        reached the end of this packet list.
        """
        pkts_list = list(hslog_pkts)
        for idx, hp in enumerate(pkts_list):
            pyid = id(hp)
            is_last = idx == len(pkts_list) - 1
            if pyid in self._seen_ids:
                # Recurse into block children even if the block itself was seen,
                # because new children may have been appended since last walk.
                if isinstance(hp, hslog_packets.Block):
                    if self._walk(hp.packets, out):
                        return True
                    if not self._maybe_emit_block_end(hp, pyid, out):
                        return True
                continue
            # Defer CreateGame emission until subsequent packets exist OR the
            # hslog parser state confirms we've moved past Player parsing.
            # This is necessary because hslog appends Player rows to the
            # in-progress CreateGame *after* the CREATE_GAME line is parsed,
            # so emitting on first sight gives us players=().
            if isinstance(hp, hslog_packets.CreateGame) and is_last:
                if self._create_game_still_building(hp):
                    self._pending_create_game_pyid = pyid
                    return True
            # gap-closure 03-07 (Rule 3): same defer pattern for FullEntity,
            # ShowEntity, and ChangeEntity. hslog appends `tag=...` rows to
            # the in-progress entity packet on subsequent lines, so emitting
            # on first sight produced an empty tags dict — silently swallowing
            # ZONE / CONTROLLER / CARDTYPE / HEALTH / etc. The captured-fixture
            # integration test in tests/test_services/test_engine_live_state.py
            # surfaces this; engine_live_state's hero / deck / mana assertions
            # cannot pass while the engine never sees any of these tags.
            if (
                is_last
                and isinstance(
                    hp,
                    (
                        hslog_packets.FullEntity,
                        hslog_packets.ShowEntity,
                        hslog_packets.ChangeEntity,
                    ),
                )
                and self._entity_packet_still_building(hp)
            ):
                return True
            self._seen_ids.add(pyid)
            if pyid == self._pending_create_game_pyid:
                self._pending_create_game_pyid = None
            if isinstance(hp, hslog_packets.Block):
                # Emit BlockStart, walk children, then BlockEnd once closed.
                out.append(translator.make_block_start(hp, self._next_id()))
                if self._walk(hp.packets, out):
                    return True
                if not self._maybe_emit_block_end(hp, pyid, out):
                    return True
            else:
                translated = translator.translate_packet(hp, self._next_id)
                if translated is not None:
                    out.append(translated)
        return False

    def _maybe_emit_block_end(self, hp: Any, pyid: int, out: List[Packet]) -> bool:
        """Emit a Block's BlockEndPacket once, on the walk where it has closed.

        A block's BlockStart is emitted the first time the block is seen, but
        the block is rarely ``ended`` at that moment — hslog sets ``ended``
        only when the BLOCK_END line is parsed (often several lines later).
        We therefore emit the matching BlockEnd here, on whichever walk first
        observes ``ended`` true, guarded by ``_emitted_block_ends`` so it fires
        exactly once. This makes the live stream balance its BlockStart /
        BlockEnd pairs, matching ``translate_packet_tree`` over the same tree.

        Returns True if the block is closed (BlockEnd emitted now or on a prior
        walk), False if it must stay open because hslog has not parsed its
        BLOCK_END yet — the caller halts so nothing after the block emits ahead
        of its (possibly still-arriving) children or its own BlockEnd.
        """
        if pyid in self._emitted_block_ends:
            return True
        if not getattr(hp, "ended", False):
            return False
        self._emitted_block_ends.add(pyid)
        out.append(translator.make_block_end(hp, self._next_id()))
        return True

    def _entity_packet_still_building(self, hp: Any) -> bool:
        """True if hslog's parser is still appending tag rows to this packet.

        hslog tracks the currently-being-built entity packet via
        ``_parsing_state.entity_packet``. While the packet is the active
        target, more `tag=...` rows may be appended on subsequent lines.
        Once a new packet starts (or hslog moves into a different parsing
        target), the entity packet is stable and safe to translate.
        """
        try:
            state = self._hslog._parsing_state
            entity_packet = getattr(state, "entity_packet", None)
        except AttributeError:
            return False
        return entity_packet is hp

    def _create_game_still_building(self, hp: Any) -> bool:
        """True if hslog is still appending Player rows to this CreateGame.

        We defer CreateGame emission until either (a) the next top-level
        packet appears after it (which means parsing has moved past the
        Player block), or (b) hslog's entity_packet state indicates we've
        moved past the CreateGame and its players.
        """
        try:
            state = self._hslog._parsing_state
            entity_packet = getattr(state, "entity_packet", None)
        except AttributeError:
            return False
        if entity_packet is None:
            return False
        # If entity_packet is the CreateGame itself, parsing is still inside
        # the GameEntity portion (which precedes Player rows).
        if entity_packet is hp:
            return True
        # If entity_packet is a Player whose parent is the in-progress
        # CreateGame, more Player rows may still arrive.
        if isinstance(entity_packet, hslog_packets.CreateGame.Player):
            for player in getattr(hp, "players", []) or []:
                if player is entity_packet:
                    return True
        return False

    def _next_id(self) -> int:
        """Return next monotonic packet id."""
        i = self._next_packet_id
        self._next_packet_id += 1
        return i
