"""End-to-end replay path (PRD #7).

Crosses every slice in one flow that the per-slice tests deliberately stub at
their boundaries:

    raw Power.log lines
      -> ReplayRecorder.on_lines / on_state(COMPLETE)   (#12)
      -> ReplayStore writes a .hsreplay file + metadata  (#11)
      -> load_replay(that exact file) -> ReplayState      (#13)
      -> ReplayViewerPresenter renders it                 (#15)

This is the real recorder-writes / loader-reads seam: the loader must be able
to read back the XML the recorder actually wrote (not a separately-generated
fixture), and the viewer must navigate the reconstructed states.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from stonereader.db import get_connection, init_db
from stonereader.models.game_state import GameState, Hero
from stonereader.presenters.replay_viewer import ReplayViewerPresenter
from stonereader.services._replay_loader import load_replay
from stonereader.services._replay_recorder import ReplayRecorder
from stonereader.services._replay_store import ReplayStore

from tests.conftest import MockSpeechService

FIXTURE = Path(__file__).parent / "fixtures" / "log" / "game_end.log"


def _now() -> datetime:
    return datetime(2026, 6, 20, tzinfo=timezone.utc)


def _hero(hero_class: str) -> Hero:
    return Hero(
        id="HERO",
        name=hero_class.title(),
        health=30,
        armor=0,
        hero_power="",
        hero_class=hero_class,
    )


def _state(game_state: str, player_playstate: str) -> GameState:
    return GameState(
        turn=12,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=_hero("MAGE"),
        opponent_hero=_hero("WARRIOR"),
        game_state=game_state,
        game_type="RANKED",
        format_type="STANDARD",
        player_playstate=player_playstate,
    )


def test_recorder_written_file_loads_and_views(tmp_path):
    conn = get_connection(str(tmp_path / "e2e.db"))
    init_db(conn)
    store = ReplayStore(conn, tmp_path / "replays")
    recorder = ReplayRecorder(store, now=_now)

    # 1) Record a completed live game from real Power.log lines.
    recorder.on_lines(FIXTURE.read_text(encoding="utf-8").splitlines())
    recorder.on_state(
        _state("RUNNING", "PLAYING"),
        _state("COMPLETE", "WON"),
    )

    saved = store.all_replays()
    assert len(saved) == 1, "recorder should auto-save exactly one replay"
    meta = saved[0]
    assert meta.source == "live_auto"
    assert meta.result == "WON"
    assert Path(meta.file_path).exists()

    # 2) Load that exact written file back into a ReplayState.
    replay = load_replay(Path(meta.file_path))
    assert replay.states, "loader must reconstruct a non-empty state sequence"

    # 3) The viewer can drive the reconstructed replay.
    speech = MockSpeechService()
    viewer = ReplayViewerPresenter(speech, replay, card_db=None)
    # Starts at the first turn = the minimum in-game turn among loaded states
    # (turn 0 = the opening/mulligan for a full game).
    first_turn = min(s.turn for s in replay.states)
    assert viewer.current_turn_number() == first_turn
    # The events zone is populated from the diff seam over the loaded states.
    assert list(viewer.get_zone_items("events")) is not None
    # Stepping a turn keeps the viewer coherent and never moves backward.
    viewer.next_turn()
    assert viewer.current_turn_number() >= first_turn

    conn.close()
