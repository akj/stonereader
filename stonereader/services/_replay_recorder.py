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
``PacketTree`` per ``CREATE_GAME`` it sees, so the LAST tree is always the
just-completed game. This is robust against the real pipeline's ordering (the
COMPLETE ``GameState`` is published as the watcher's lines flow through the
parser, so the game's lines are already buffered by the time ``on_state`` sees
``COMPLETE``).

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
from typing import Callable, List, Optional

from hsreplay.document import HSReplayDocument

from stonereader.models.game_state import GameState
from stonereader.services._replay_store import ReplayStore

logger = logging.getLogger(__name__)


def _default_now() -> datetime:
    """Production clock: tz-aware UTC now (HSReplay timestamps must round-trip)."""
    return datetime.now(timezone.utc)


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
        """Flush on COMPLETE, drop on ABANDONED, otherwise keep buffering.

        - COMPLETE: build XML from the buffer and persist; clear buffer after.
        - ABANDONED: clear the buffer and save nothing.
        - anything else (RUNNING, prev is None, etc.): keep accumulating; the
          new game's CREATE_GAME lines are already in the buffer via on_lines.
        """
        game_state = getattr(curr, "game_state", "")
        if game_state == "ABANDONED":
            self._buffer.clear()
            return
        if game_state == "COMPLETE":
            self._flush_complete(curr)

    # ------------------------------------------------------------- Internals

    def _flush_complete(self, curr: GameState) -> None:
        """Parse the buffer, save the just-completed game, then clear the buffer.

        The whole body is failure-isolated: any parse / XML / store error is
        logged and swallowed so auto-save never propagates out of ``on_state``.
        The buffer is cleared in ``finally`` either way — a broken game is
        dropped rather than re-saved on the next state.
        """
        try:
            xml = self._build_xml()
            if xml is None:
                return  # nothing parseable — save nothing, no raise
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
            self._buffer.clear()

    def _build_xml(self) -> Optional[str]:
        """Parse the buffered lines into HSReplay XML for the last game.

        Returns ``None`` (rather than raising) when the buffer contains no
        parseable game. A tz-aware ``_current_date`` is required so the emitted
        HSReplay timestamps are real datetimes that round-trip.
        """
        # Local import keeps hslog as a file-parsing-edge dependency, mirroring
        # the loader: the recorder module imports it only when it parses.
        from hslog import LogParser

        parser = LogParser()
        parser._current_date = self._now()
        for line in self._buffer:
            parser.read_line(line)
        if not parser.games:
            return None
        tree = parser.games[-1]  # the just-completed game (hslog segments games)
        return HSReplayDocument.from_packet_tree([tree]).to_xml()

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
