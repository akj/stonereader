"""Integration tests for the live replay recorder (Slice #12).

The recorder buffers raw Power.log lines (via ``on_lines``) and, when the
tracker publishes a COMPLETE ``GameState`` (via ``on_state``), parses the
buffer into an HSReplay document and auto-saves it through a REAL
:class:`ReplayStore` over ``tmp_path``. ABANDONED games and watcher resets
drop the buffer without saving.

Pure service-level: no wx, no real speech, no clock. ``now`` is injected for
determinism; the only I/O is reading the committed fixture and writing into a
temp sqlite db + replay dir.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from stonereader.db import get_connection, init_db
from stonereader.models.game_state import GameState, Hero
from stonereader.services._replay_loader import load_replay
from stonereader.services._replay_recorder import ReplayRecorder
from stonereader.services._replay_store import ReplayStore

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "log"
SOURCE_LOG = "game_end.log"
NEXT_LOG = "match_start.log"

FIXED_NOW = datetime(2026, 6, 20, tzinfo=timezone.utc)


# -------------------------------- Helpers --------------------------------


def _now() -> datetime:
    return FIXED_NOW


def _hero(hero_class: str) -> Hero:
    return Hero(
        id="?",
        name="?",
        health=30,
        armor=0,
        hero_power="",
        hero_class=hero_class,
    )


def _make_state(
    *,
    game_state: str = "RUNNING",
    player_playstate: str = "",
    opponent_playstate: str = "",
    turn: int = 7,
    player_hero_class: str = "MAGE",
    opponent_hero_class: str = "WARRIOR",
    game_type: str = "RANKED",
    format_type: str = "STANDARD",
) -> GameState:
    return GameState(
        turn=turn,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=_hero(player_hero_class),
        opponent_hero=_hero(opponent_hero_class),
        game_state=game_state,
        game_type=game_type,
        format_type=format_type,
        player_playstate=player_playstate,
        opponent_playstate=opponent_playstate,
    )


def _make_store(tmp_path: Path) -> ReplayStore:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    return ReplayStore(conn, tmp_path / "replays")


def _fixture_lines() -> list[str]:
    return (FIXTURE_DIR / SOURCE_LOG).read_text(encoding="utf-8").splitlines()


def _recorder(store: ReplayStore) -> ReplayRecorder:
    return ReplayRecorder(store, now=_now)


# -------------------------------- Tests ----------------------------------


def test_complete_game_auto_saves_one_replay(tmp_path: Path) -> None:
    """A COMPLETE/WON state flushes the buffered game to exactly one replay."""
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    recorder.on_lines(_fixture_lines())
    prev = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    curr = _make_state(game_state="COMPLETE", player_playstate="WON")
    recorder.on_state(prev, curr)

    replays = store.all_replays()
    assert len(replays) == 1
    meta = replays[0]
    assert meta.source == "live_auto"
    assert meta.result == "WON"
    assert meta.result != "UNKNOWN"

    files = list((tmp_path / "replays").rglob("*.hsreplay"))
    assert len(files) == 1


def test_conceded_but_completed_saves_with_loss(tmp_path: Path) -> None:
    """A COMPLETE/LOST state still saves, recording result='LOST'."""
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    recorder.on_lines(_fixture_lines())
    prev = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    curr = _make_state(
        game_state="COMPLETE", player_playstate="LOST", opponent_playstate="WON"
    )
    recorder.on_state(prev, curr)

    replays = store.all_replays()
    assert len(replays) == 1
    assert replays[0].result == "LOST"


def test_abandoned_game_saves_nothing(tmp_path: Path) -> None:
    """An ABANDONED state drops the buffer and persists no replay."""
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    recorder.on_lines(_fixture_lines())
    prev = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    abandoned = _make_state(game_state="ABANDONED")
    recorder.on_state(prev, abandoned)

    assert store.all_replays() == []
    assert list((tmp_path / "replays").rglob("*.hsreplay")) == []


def test_watcher_reset_before_completion_saves_nothing(tmp_path: Path) -> None:
    """A reset before any COMPLETE drops the buffer; later there is nothing to save."""
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    recorder.on_lines(_fixture_lines())
    recorder.on_reset()
    # No COMPLETE state arrives; buffer is empty.

    assert store.all_replays() == []
    assert list((tmp_path / "replays").rglob("*.hsreplay")) == []


def test_save_failure_is_isolated(tmp_path: Path) -> None:
    """A store whose save_xml raises must NOT let the error escape on_state."""
    store = _make_store(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("disk full")

    store.save_xml = _boom  # type: ignore[method-assign]
    recorder = _recorder(store)

    recorder.on_lines(_fixture_lines())
    prev = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    curr = _make_state(game_state="COMPLETE", player_playstate="WON")

    # Must swallow the RuntimeError rather than propagate.
    recorder.on_state(prev, curr)


def test_unparseable_buffer_saves_nothing(tmp_path: Path) -> None:
    """A COMPLETE with no parseable game in the buffer saves nothing, no raise."""
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    recorder.on_lines(["not a real power log line", "neither is this"])
    prev = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    curr = _make_state(game_state="COMPLETE", player_playstate="WON")
    recorder.on_state(prev, curr)

    assert store.all_replays() == []


def test_next_game_in_same_batch_saves_completed_not_partial(tmp_path: Path) -> None:
    """One watcher tick carrying the finished game's tail + the next game's
    CREATE_GAME must save the COMPLETED game (not the partial new one), and keep
    the next game's already-buffered head so it can still be saved later.
    """
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    finished = _fixture_lines()  # game_end.log: friendly concedes -> LOST
    next_head = (FIXTURE_DIR / NEXT_LOG).read_text(encoding="utf-8").splitlines()[:120]
    # A single batch: the finishing game's lines AND the next game's opening.
    recorder.on_lines(finished + next_head)

    prev = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    curr = _make_state(
        game_state="COMPLETE", player_playstate="LOST", opponent_playstate="WON"
    )
    recorder.on_state(prev, curr)

    # Exactly one replay, recording the COMPLETED game's result.
    replays = store.all_replays()
    assert len(replays) == 1
    assert replays[0].result == "LOST"

    # The saved file is the COMPLETED game: loading it must reach a terminal
    # state. A partial next-game save would never reach COMPLETE.
    files = list((tmp_path / "replays").rglob("*.hsreplay"))
    assert len(files) == 1
    state = load_replay(files[0])
    assert state.states[-1].game_state == "COMPLETE"
    assert state.states[-1].player_playstate == "LOST"

    # The next game's buffered head survived the clear (so it can be saved when
    # IT completes) rather than being discarded with the finished game.
    assert recorder._buffer, "next game's buffered head must be preserved"
    assert any("CREATE_GAME" in line for line in recorder._buffer)


def test_second_complete_dispatch_does_not_clobber_preserved_next_game(
    tmp_path: Path,
) -> None:
    """A finished game can publish several COMPLETE snapshots (trailing packets
    after the terminal PLAYSTATE keep game_state=COMPLETE). Only the transition
    into COMPLETE flushes; a later COMPLETE→COMPLETE must NOT re-flush against —
    and clear — the preserved next-game head.
    """
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    finished = _fixture_lines()
    next_head = (FIXTURE_DIR / NEXT_LOG).read_text(encoding="utf-8").splitlines()[:120]
    recorder.on_lines(finished + next_head)

    running = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    complete = _make_state(
        game_state="COMPLETE", player_playstate="LOST", opponent_playstate="WON"
    )

    # Transition into COMPLETE: saves the finished game, preserves the next head.
    recorder.on_state(running, complete)
    assert len(store.all_replays()) == 1
    preserved = list(recorder._buffer)
    assert preserved, "next game's buffered head must be preserved"

    # A second COMPLETE snapshot (e.g. a trailing BLOCK_END) must be ignored.
    recorder.on_state(complete, complete)
    assert len(store.all_replays()) == 1  # no partial next-game save
    assert recorder._buffer == preserved  # preserved head intact


def test_buffer_cleared_after_save_prevents_double_save(tmp_path: Path) -> None:
    """After a COMPLETE save, a second COMPLETE with no new lines saves nothing new."""
    store = _make_store(tmp_path)
    recorder = _recorder(store)

    recorder.on_lines(_fixture_lines())
    prev = _make_state(game_state="RUNNING", player_playstate="PLAYING")
    curr = _make_state(game_state="COMPLETE", player_playstate="WON")
    recorder.on_state(prev, curr)
    recorder.on_state(prev, curr)  # buffer now empty -> no new save

    assert len(store.all_replays()) == 1
