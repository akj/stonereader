"""End-to-end replay path (PRD #7).

Crosses every slice in one flow that the per-slice tests deliberately stub at
their boundaries:

    raw Power.log lines
      -> ReplayRecorder.on_lines / on_state(COMPLETE)   (#12)
      -> ReplayStore writes a .hsreplay file + metadata  (#11)
      -> load_replay(that exact file) -> ReplayState      (#13)
      -> replay turn views group it for the Surface       (#15)

This is the real recorder-writes / loader-reads seam: the loader must be able
to read back the XML the recorder actually wrote (not a separately-generated
fixture), and the viewer must navigate the reconstructed states.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from stonereader.db import get_connection, init_db
from stonereader.models.card import CardDatabase
from stonereader.models.game_state import GameState, Hero
from stonereader.services._engine import GameEngine
from stonereader.services._events import (
    CardDrawn,
    CardPlayed,
    GameEnded,
    GameStarted,
    TurnChanged,
)
from stonereader.services._parser import Parser
from stonereader.services._replay_loader import load_replay
from stonereader.services._replay_recorder import ReplayRecorder
from stonereader.services._replay_store import ReplayStore

from stonereader.surfaces._replay_turns import turns

FIXTURE = Path(__file__).parent / "fixtures" / "log" / "game_end.log"
# A synthetic ranked Wild game: the local player is the server's Player 2 and
# goes first, and each player entity logs its own TURN counter beside the
# game's, as live Hearthstone logs do.
PLAYER_TWO_FIXTURE = (
    Path(__file__).parent / "fixtures" / "log" / "player_two_ranked.log"
)


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
    recorder = ReplayRecorder(store, now=_now, build_provider=lambda: 99999)

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
    xml = Path(meta.file_path).read_text(encoding="utf-8")
    assert 'build="99999"' in xml
    assert 'name="Player1"' in xml

    # 2) Load that exact written file back into a ReplayState.
    replay = load_replay(Path(meta.file_path))
    assert replay.states, "loader must reconstruct a non-empty state sequence"

    # 3) The viewer's pure helper groups the reconstructed snapshots. Opening
    # and mulligan snapshots are turn 1's prelude, never a separate turn 0.
    replay_turns = turns(replay)
    assert replay_turns
    assert replay_turns[0].number == 1
    assert isinstance(replay_turns[0].events, tuple)

    conn.close()


def test_player_two_game_records_and_replays_from_the_friendly_side(tmp_path):
    """A live-recorded game where the local player was Player 2 replayed as
    "Game started, Unknown versus Unknown", with the sides mirrored, turns
    numbered by a player's own TURN counter, and an "Unknown, Unknown" row.
    The row, the turns, and every event's side must match the recorded game.
    """
    card_db = CardDatabase.load()
    conn = get_connection(str(tmp_path / "e2e.db"))
    init_db(conn)
    store = ReplayStore(conn, tmp_path / "replays")
    recorder = ReplayRecorder(store, now=_now)
    parser = Parser()
    engine = GameEngine(card_db=card_db)

    # 1) The live pipeline, wired as the tracker wires it: the recorder holds
    # each raw line before the engine publishes the state it produces.
    previous = None
    for line in PLAYER_TWO_FIXTURE.read_text(encoding="utf-8").splitlines():
        recorder.on_lines([line])
        for packet in parser.feed_line(line):
            engine.apply(packet)
            current = engine.current_state
            if current is not None and current is not previous:
                recorder.on_state(previous, current)
                previous = current

    [meta] = store.all_replays()
    assert (meta.friendly_class, meta.opponent_class, meta.result) == (
        "DEATHKNIGHT",
        "ROGUE",
        "LOST",
    )
    assert meta.turns == 4
    assert (meta.game_type, meta.format_type) == ("RANKED", "WILD")

    # 2) The saved file, replayed.
    replay = load_replay(Path(meta.file_path), card_db)
    assert replay.friendly_player_id == 2
    replay_turns = turns(replay)
    assert [(turn.number, turn.is_friendly) for turn in replay_turns] == [
        (1, True),
        (2, False),
        (3, True),
        (4, False),
    ]
    events = [
        (turn.number, item.event) for turn in replay_turns for item in turn.events
    ]

    started = events[0][1]
    assert isinstance(started, GameStarted)
    assert (
        started.player_class,
        started.opponent_class,
        started.game_type,
        started.format_type,
    ) == ("DEATHKNIGHT", "ROGUE", "RANKED", "WILD")
    assert [
        (number, event.controller, event.name)
        for number, event in events
        if isinstance(event, CardDrawn)
    ] == [
        (1, 2, ""),
        (1, 1, "Chillwind Yeti"),
        (1, 1, "Plague Strike"),
        (2, 2, ""),
        (3, 1, "Chillwind Yeti"),
    ]
    assert [
        (number, event.controller, event.name)
        for number, event in events
        if isinstance(event, CardPlayed)
    ] == [(1, 1, "Chillwind Yeti")]
    assert [
        (number, event.turn, event.active_player_id)
        for number, event in events
        if isinstance(event, TurnChanged)
    ] == [(2, 2, 2), (3, 3, 1), (4, 4, 2)]
    assert [
        (number, event.player_playstate)
        for number, event in events
        if isinstance(event, GameEnded)
    ] == [(4, "LOST")]

    conn.close()
