"""Live replay recorder — auto-save completed live games as HSReplay XML (Slice #12).

The recorder sits between the live pipeline's raw Power.log lines and the
:class:`~stonereader.services._replay_store.ReplayStore`. It buffers EVERY line
the watcher delivers and, when the tracker publishes a ``COMPLETE``
``GameState``, re-parses that buffer into an hslog ``PacketTree``, serialises
the just-completed game to HSReplay XML, derives metadata from the completed
state, and persists it with ``source='live_auto'``.

Design — segment at ingestion, parse one game at a time
-------------------------------------------------------
The recorder splits raw lines into game segments on the top-level
``CREATE_GAME`` marker as they arrive. Each segment is later fed to a FRESH
:class:`hslog.LogParser`: hslog does not support parsing multiple games on one
parser (upstream issue #19), because player state can leak across game
boundaries. The watcher's ordering still makes this safe: it delivers the raw
batch before the tracker publishes the resulting COMPLETE ``GameState``.

Selecting the right tree
------------------------
The LAST parsed tree is NOT necessarily the just-completed game: a single
watcher tick can carry the finishing game's terminal lines *and* the next
game's ``CREATE_GAME`` (the raw listener buffers the whole batch before the
parser dispatches the first ``COMPLETE``). Taking ``games[-1]`` would then
serialise the next, partial game under the completed game's metadata. So on
``COMPLETE`` the recorder selects the FIRST segment whose tree reached a
terminal ``PLAYSTATE`` and, when a later game has already started, preserves
that segment instead of dropping it after the flush.

Lifecycle hooks (wired in app.py, NOT here):
  - ``on_lines``  : called by the watcher's ``on_lines`` — ALWAYS accumulates.
  - ``on_reset``  : called by the watcher's ``on_reset`` — drops the buffer.
  - ``on_state``  : subscribed to the tracker — flushes on COMPLETE, drops on
    ABANDONED.

Failure isolation
-----------------
The entire COMPLETE handler is wrapped so a parse / XML / store failure is
logged and SWALLOWED — auto-save must never crash the live tracker. Processed
segments are removed in a ``finally`` regardless of success: a broken game is
dropped rather than re-attempted on the next state, while later segments remain
available for their own COMPLETE transition.

UI-free: no wx, no clock beyond the injected ``now`` (tz-aware for HSReplay
timestamp round-tripping).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, List, Optional

from hearthstone.enums import GameTag, PlayState
from hsreplay.document import HSReplayDocument

from stonereader.models.game_state import GameState
from stonereader.services._replay_store import ReplayStore

logger = logging.getLogger(__name__)

# A new game in the Power.log opens with this exact GameState marker, and hslog
# segments PacketTrees on it (the indented ``PowerTaskList`` CREATE_GAME does
# NOT start a new tree). The marker itself belongs to the segment it opens.
_GAME_CREATE_MARKER = "GameState.DebugPrintPower() - CREATE_GAME"

# PLAYSTATE values that mark a finished game (mirrors GameEngine._handle_playstate:
# CONCEDED counts as finished — that side simply lost).
_TERMINAL_PLAYSTATES = frozenset(
    int(s) for s in (PlayState.WON, PlayState.LOST, PlayState.TIED, PlayState.CONCEDED)
)


def _default_now() -> datetime:
    """Production clock: tz-aware UTC now (HSReplay timestamps must round-trip)."""
    return datetime.now(timezone.utc)


@dataclass
class _Segment:
    """Raw lines for one game and the time its CREATE_GAME marker arrived.

    ``start_time`` is optional only for a defensive markerless head. The live
    watcher normally backfills from CREATE_GAME, but retaining pre-marker lines
    makes resets and unusual attachment timing harmless rather than lossy.
    """

    start_time: Optional[datetime]
    lines: List[str]


@dataclass
class _ParsedSegment:
    """One segment's parser outputs kept together for selection and saving."""

    index: int
    segment: _Segment
    tree: Any
    game_meta: dict[str, Any]
    started_at: datetime


def _iter_tree_packets(nodes: Any) -> Iterator[Any]:
    """Depth-first walk over a PacketTree's nodes, descending into Blocks."""
    from hslog import packets as hslog_packets

    for node in nodes:
        yield node
        if isinstance(node, hslog_packets.Block):
            yield from _iter_tree_packets(getattr(node, "packets", []) or [])


def _game_is_complete(tree: Any) -> bool:
    """True once a parsed game tree carries a terminal PLAYSTATE TagChange.

    Matches the signal the engine uses to publish ``COMPLETE`` (a player's
    PLAYSTATE going WON/LOST/TIED/CONCEDED), so the recorder selects the same
    game the tracker just reported finished.
    """
    from hslog import packets as hslog_packets

    for node in _iter_tree_packets(getattr(tree, "packets", []) or []):
        if (
            isinstance(node, hslog_packets.TagChange)
            and node.tag == GameTag.PLAYSTATE
            and _safe_int(node.value) in _TERMINAL_PLAYSTATES
        ):
            return True
    return False


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ReplayRecorder:
    """Buffer live Power.log lines and auto-save each completed game as HSReplay.

    Construct with a :class:`ReplayStore`; subscribe ``on_state`` to the tracker
    and route the watcher's ``on_lines`` / ``on_reset`` callbacks to the
    matching methods here.
    """

    def __init__(
        self,
        store: ReplayStore,
        *,
        now: Callable[[], datetime] = _default_now,
        build_provider: Optional[Callable[[], Optional[int]]] = None,
    ) -> None:
        self._store = store
        self._now = now
        self._build_provider = build_provider
        self._segments: List[_Segment] = []

    # ------------------------------------------------------------- Watcher hooks

    def on_lines(self, lines: List[str]) -> None:
        """Append raw lines, opening a timestamped segment at each game marker."""
        for line in lines:
            if _GAME_CREATE_MARKER in line:
                self._segments.append(_Segment(self._now(), [line]))
                continue
            if not self._segments:
                self._segments.append(_Segment(None, []))
            self._segments[-1].lines.append(line)

    def on_reset(self) -> None:
        """Watcher detected a file rotation / disappearance — drop everything."""
        self._segments.clear()

    # ------------------------------------------------------------- Tracker hook

    def on_state(self, prev: Optional[GameState], curr: GameState) -> None:
        """Flush on the transition into COMPLETE, drop on ABANDONED, else buffer.

        - COMPLETE (only when prev was NOT already COMPLETE): build XML from the
          buffer and persist; trim the buffer after.
        - ABANDONED: clear the buffer and save nothing.
        - anything else (RUNNING, prev is None, etc.): keep accumulating; the
          new game's CREATE_GAME lines are already in the buffer via on_lines.

        A finished game can publish SEVERAL COMPLETE snapshots — trailing packets
        after the terminal PLAYSTATE (e.g. BLOCK_END) still mutate other fields
        while game_state stays COMPLETE. Re-flushing on those would, when the
        next game's CREATE_GAME is already buffered, serialise that partial next
        game and drop its preserved head. The first COMPLETE already saved the
        finished game, so flush ONLY on the RUNNING/None -> COMPLETE transition.
        """
        game_state = getattr(curr, "game_state", "")
        if game_state == "ABANDONED":
            self._segments.clear()
            return
        if game_state == "COMPLETE" and getattr(prev, "game_state", "") != "COMPLETE":
            self._flush_complete(curr)

    # ------------------------------------------------------------- Internals

    def _flush_complete(self, curr: GameState) -> None:
        """Parse segments, save the just-completed game, then drop it.

        The whole body is failure-isolated: any state-corrupting parse, XML, or
        store error is logged and swallowed so auto-save never propagates out of
        ``on_state``. In ``finally`` every segment through the completed (or
        failing) one is removed even on failure, preventing endless retries;
        segments that started later remain intact for their own completion.

        The LAST tree may be a partial next game whose CREATE_GAME arrived in
        the same watcher tick as this game's finish. Segments are processed in
        order, so the FIRST terminal tree is the COMPLETE transition being
        handled. If none looks terminal, the last segment with a tree is used as
        a defensive fallback: the engine only reports COMPLETE from a terminal
        PLAYSTATE, which should already be present in these raw lines.
        """
        completed_index = -1
        parsed: List[_ParsedSegment] = []
        try:
            for index, segment in enumerate(self._segments):
                if not segment.lines:
                    continue
                # If parsing this segment fatally fails, it is the broken game
                # this COMPLETE flush must drop; later segments stay buffered.
                completed_index = index
                tree, game_meta, started_at = self._parse_segment(segment)
                if tree is None:
                    continue
                parsed.append(
                    _ParsedSegment(index, segment, tree, game_meta, started_at)
                )
                if _game_is_complete(tree):
                    # This COMPLETE dispatch belongs to the first terminal
                    # segment. Do not let corruption in an already-buffered
                    # later game's head suppress this valid save or discard
                    # that later segment before its own completion attempt.
                    break

            if not parsed:
                return  # nothing parseable — save nothing, no raise
            selected = next(
                (candidate for candidate in parsed if _game_is_complete(candidate.tree)),
                parsed[-1],
            )
            completed_index = selected.index
            build = self._read_build()
            document = self._enriched_document(
                selected.tree, selected.game_meta, build
            )
            xml = document.to_xml()
            self._store.save_xml(
                xml,
                source="live_auto",
                friendly_class=getattr(curr.player_hero, "hero_class", "") or "",
                opponent_class=getattr(curr.opponent_hero, "hero_class", "") or "",
                result=self._derive_result(curr),
                turns=curr.turn,
                game_type=curr.game_type,
                format_type=curr.format_type,
                played_at=selected.started_at.isoformat(),
                duration_seconds=None,
                raw_log="\n".join(selected.segment.lines) + "\n",
            )
        except Exception:
            logger.exception("live replay auto-save failed; dropping game")
        finally:
            if completed_index >= 0:
                self._segments = self._segments[completed_index + 1 :]

    def _parse_segment(
        self, segment: _Segment
    ) -> tuple[Any | None, dict[str, Any], datetime]:
        """Parse one segment with a fresh hslog parser and at most one tree.

        Power.log timestamps contain time-of-day only, so ``_current_date`` must
        be the date when this segment's CREATE_GAME arrived. Using save time
        misdates games spanning midnight and makes re-parsing identical source
        lines on different days produce different XML, defeating checksum
        dedupe. A markerless defensive segment falls back to the current clock.

        There are deliberately two failure classes. ``ParsingError`` and its
        subclasses describe per-line format drift after a Hearthstone patch;
        those lines are safe to count and skip, matching the live parser.
        Anything else propagates. In particular ``MissingPlayerData`` is a
        ``RuntimeError``, not a ``ParsingError``: continuing after it would use
        broken player state and silently save a truncated replay.
        """
        # Local imports keep hslog at the file-parsing edge, mirroring the
        # loader: importing this service alone performs no parser setup.
        from hslog import LogParser
        from hslog.exceptions import ParsingError

        parser = LogParser()
        started_at = segment.start_time or self._now()
        parser._current_date = started_at
        skipped = 0
        for line in segment.lines:
            try:
                parser.read_line(line)
            except ParsingError:
                skipped += 1
        if skipped:
            logger.warning(
                "recorder: skipped %d unparseable log line(s) while saving replay",
                skipped,
            )
        tree = parser.games[0] if parser.games else None
        return tree, dict(parser.game_meta), started_at

    def _read_build(self) -> Optional[int]:
        """Call the injected build provider once, isolating discovery failures."""
        if self._build_provider is None:
            return None
        try:
            return self._build_provider()
        except Exception:
            logger.warning(
                "recorder: Hearthstone build discovery failed; omitting build",
                exc_info=True,
            )
            return None

    @staticmethod
    def _enriched_document(
        tree: Any, game_meta: dict[str, Any], build: Optional[int]
    ) -> HSReplayDocument:
        """Build an enriched document, falling back whole on enrichment errors.

        Build, game attributes, and player names are compatibility metadata,
        not prerequisites for preserving the Replay. The plain document is
        created first; if any enrichment assumption drifts in hsreplay/hslog,
        that document remains serializable and the game is still saved.
        """
        plain = HSReplayDocument.from_packet_tree([tree])
        try:
            from hslog import packets as hslog_packets
            from hsreplay.utils import set_game_meta_on_game

            from stonereader.services._hslog_translator import (
                player_entity_id,
                player_name,
            )

            document = HSReplayDocument.from_packet_tree([tree], build=build)
            game = document.games[0]
            replay_meta: dict[str, int] = {}
            for source_key, target_key in (
                ("GameType", "hs_game_type"),
                ("FormatType", "format"),
                ("ScenarioID", "scenario_id"),
            ):
                value = _safe_int(game_meta.get(source_key))
                if value is not None:
                    replay_meta[target_key] = value
            set_game_meta_on_game(replay_meta, game)

            create_game = next(
                (
                    packet
                    for packet in _iter_tree_packets(getattr(tree, "packets", []) or [])
                    if isinstance(packet, hslog_packets.CreateGame)
                ),
                None,
            )
            names = {
                player_entity_id(player): player_name(player)
                for player in getattr(create_game, "players", []) or []
                if player_name(player)
            }
            for player in game.players:
                entity_id = _safe_int(getattr(player, "id", None))
                name = names.get(entity_id) if entity_id is not None else None
                if name:
                    player.name = name
            return document
        except Exception:
            logger.warning(
                "recorder: replay XML enrichment failed; saving plain document",
                exc_info=True,
            )
            return plain

    @staticmethod
    def _derive_result(curr: GameState) -> str:
        """Result for a live auto-save — MUST NOT be 'UNKNOWN' on COMPLETE.

        ``player_playstate`` is authoritative (WON / LOST / TIED). On the
        unexpected path where it is empty at COMPLETE, fall back to inverting
        the opponent's playstate, then to 'TIED' — never 'UNKNOWN'.
        """
        playstate = (curr.player_playstate or "").upper()
        if playstate in ("WON", "LOST", "TIED"):
            return playstate
        opponent = (curr.opponent_playstate or "").upper()
        if opponent == "WON":
            return "LOST"
        if opponent == "LOST":
            return "WON"
        return "TIED"
