"""Live replay recorder — auto-save completed live games as HSReplay XML (Slice #12).

The recorder sits between the live pipeline's raw Power.log lines and the
:class:`~stonereader.services._replay_store.ReplayStore`. It buffers EVERY line
the watcher delivers and, when the tracker publishes a ``COMPLETE``
``GameState``, re-parses that buffer into an hslog ``PacketTree``, serialises
the just-completed game to HSReplay XML, derives metadata from the completed
state, and persists it with ``source='live_auto'``.

Design — buffer-everything, segment on parse
--------------------------------------------
Rather than trying to track game boundaries from interleaved line/state
ordering, the recorder simply accumulates all lines and lets hslog do the
segmentation: a single :class:`hslog.LogParser` fed the whole buffer yields one
``PacketTree`` per ``CREATE_GAME`` it sees. This is robust against the real
pipeline's ordering (the COMPLETE ``GameState`` is published as the watcher's
lines flow through the parser, so the game's lines are already buffered by the
time ``on_state`` sees ``COMPLETE``).

Selecting the right tree
------------------------
The LAST parsed tree is NOT necessarily the just-completed game: a single
watcher tick can carry the finishing game's terminal lines *and* the next
game's ``CREATE_GAME`` (the raw listener buffers the whole batch before the
parser dispatches the first ``COMPLETE``). Taking ``games[-1]`` would then
serialise the next, partial game under the completed game's metadata. So on
``COMPLETE`` the recorder selects the FIRST tree that reached a terminal
``PLAYSTATE`` and, when a later game has already started, preserves that game's
buffered head (from its ``GameState`` ``CREATE_GAME`` line) instead of dropping
it on the buffer clear.

Lifecycle hooks (wired in app.py, NOT here):
  - ``on_lines``  : called by the watcher's ``on_lines`` — ALWAYS accumulates.
  - ``on_reset``  : called by the watcher's ``on_reset`` — drops the buffer.
  - ``on_state``  : subscribed to the tracker — flushes on COMPLETE, drops on
    ABANDONED.

Failure isolation
-----------------
The entire COMPLETE handler is wrapped so a parse / XML / store failure is
logged and SWALLOWED — auto-save must never crash the live tracker. The buffer
is cleared in a ``finally`` regardless of success: a broken game is dropped
rather than re-attempted on the next state, which would otherwise retry the
same failing save forever.

UI-free: no wx, no clock beyond the injected ``now`` (tz-aware for HSReplay
timestamp round-tripping).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, List, Optional

from hearthstone.enums import GameTag, PlayState
from hsreplay.document import HSReplayDocument

from stonereader.models.game_state import GameState
from stonereader.services._replay_store import ReplayStore

logger = logging.getLogger(__name__)

# A new game in the Power.log opens with this exact GameState marker, and hslog
# segments PacketTrees on it (the indented ``PowerTaskList`` CREATE_GAME does
# NOT start a new tree). Used to find where an already-buffered next game begins
# so its head survives the post-save buffer clear.
_GAME_CREATE_MARKER = "GameState.DebugPrintPower() - CREATE_GAME"

# PLAYSTATE values that mark a finished game (mirrors GameEngine._handle_playstate:
# CONCEDED counts as finished — that side simply lost).
_TERMINAL_PLAYSTATES = frozenset(
    int(s) for s in (PlayState.WON, PlayState.LOST, PlayState.TIED, PlayState.CONCEDED)
)


def _default_now() -> datetime:
    """Production clock: tz-aware UTC now (HSReplay timestamps must round-trip)."""
    return datetime.now(timezone.utc)


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
    ) -> None:
        self._store = store
        self._now = now
        self._buffer: List[str] = []

    # ------------------------------------------------------------- Watcher hooks

    def on_lines(self, lines: List[str]) -> None:
        """Accumulate raw lines. NEVER clears — segmentation happens on parse."""
        self._buffer.extend(lines)

    def on_reset(self) -> None:
        """Watcher detected a file rotation / disappearance — drop everything."""
        self._buffer.clear()

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
            self._buffer.clear()
            return
        if game_state == "COMPLETE" and getattr(prev, "game_state", "") != "COMPLETE":
            self._flush_complete(curr)

    # ------------------------------------------------------------- Internals

    def _flush_complete(self, curr: GameState) -> None:
        """Parse the buffer, save the just-completed game, then trim the buffer.

        The whole body is failure-isolated: any parse / XML / store error is
        logged and swallowed so auto-save never propagates out of ``on_state``.
        In ``finally`` the buffer is replaced with only the lines of a game that
        started AFTER the one we saved (usually none) — a broken or completed
        game is dropped rather than re-saved on the next state, but a next
        game's already-buffered head is preserved so it can still be saved when
        IT completes.
        """
        keep_tail: List[str] = []
        try:
            games = self._parse_games()
            if not games:
                return  # nothing parseable — save nothing, no raise
            index = self._completed_game_index(games)
            # Compute what to retain BEFORE saving so a save failure still
            # preserves the next game's head (and still drops the saved one).
            keep_tail = self._trailing_lines(index, len(games))
            xml = HSReplayDocument.from_packet_tree([games[index]]).to_xml()
            self._store.save_xml(
                xml,
                source="live_auto",
                friendly_class=getattr(curr.player_hero, "hero_class", "") or "",
                opponent_class=getattr(curr.opponent_hero, "hero_class", "") or "",
                result=self._derive_result(curr),
                turns=curr.turn,
                game_type=curr.game_type,
                format_type=curr.format_type,
                played_at=self._now().isoformat(),
                duration_seconds=None,
            )
        except Exception:
            logger.exception("live replay auto-save failed; dropping game")
        finally:
            self._buffer = keep_tail

    def _parse_games(self) -> List[Any]:
        """Parse the buffered lines into hslog ``PacketTree`` games.

        A tz-aware ``_current_date`` is required so the emitted HSReplay
        timestamps are real datetimes that round-trip.
        """
        # Local import keeps hslog as a file-parsing-edge dependency, mirroring
        # the loader: the recorder module imports it only when it parses.
        from hslog import LogParser

        parser = LogParser()
        parser._current_date = self._now()
        for line in self._buffer:
            parser.read_line(line)
        return list(parser.games)

    @staticmethod
    def _completed_game_index(games: List[Any]) -> int:
        """Index of the just-completed game among the parsed trees.

        The LAST tree may be a partial next game whose ``CREATE_GAME`` arrived in
        the same watcher tick as this game's finish. Finished games are flushed
        and trimmed out of the buffer in order, so the EARLIEST still-buffered
        complete game is the one whose ``COMPLETE`` just fired. Falls back to the
        last tree if none looks complete (defensive: the engine only reports
        COMPLETE off a terminal PLAYSTATE, which is by then in the buffer).
        """
        for i, game in enumerate(games):
            if _game_is_complete(game):
                return i
        return len(games) - 1

    def _trailing_lines(self, index: int, num_games: int) -> List[str]:
        """Buffer lines for a game that started after the one being saved.

        Empty in the common case (the saved game is the last parsed tree — the
        next game has not started yet). When a later game exists, retain from its
        ``GameState`` ``CREATE_GAME`` line so its already-buffered head is not
        lost when the buffer is replaced.
        """
        if index >= num_games - 1:
            return []
        create_idxs = [
            i for i, line in enumerate(self._buffer) if _GAME_CREATE_MARKER in line
        ]
        if index + 1 < len(create_idxs):
            return self._buffer[create_idxs[index + 1] :]
        return []

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
