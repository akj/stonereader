"""Integration tests for the Replay loader (Slice #13).

These tests exercise the whole loader path end-to-end: generate a real
``.hsreplay`` XML file from a committed Power.log fixture (the VALIDATED
HSREPLAY recipe), write it to ``tmp_path``, then ``load_replay`` it and assert
the resulting :class:`ReplayState` spans the recorded game.

The loader reuses the SAME translation + engine pipeline the live tracker uses,
so the produced ``GameState`` sequence must round-trip back into the same
``GameEvent`` stream via :func:`stonereader.services._diff.diff` — in
particular a ``GameStarted`` near the front and a ``GameEnded`` near the end.

Pure service/model-level: no wx, no real speech, no clock. The only I/O is
reading the committed fixture text and writing a temp ``.hsreplay`` file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hslog import LogParser
from hslog.export import FriendlyPlayerExporter
from hsreplay.document import HSReplayDocument

from stonereader.services._diff import diff
from stonereader.services._engine import GameEngine
from stonereader.services._events import GameEnded, GameStarted
from stonereader.services._parser import Parser
from stonereader.services._replay_loader import ReplayLoadError, load_replay

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "log"
SOURCE_LOG = "game_end.log"


def _live_states(log_name: str = SOURCE_LOG):
    """Drive the LIVE pipeline (Parser -> GameEngine) over a fixture."""
    path = FIXTURE_DIR / log_name
    parser = Parser()
    engine = GameEngine()
    states = []
    last = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            for pkt in parser.feed_line(line.rstrip("\n")):
                engine.apply(pkt)
                cur = engine.current_state
                if cur is not None and cur is not last:
                    states.append(cur)
                    last = cur
    return states


def _event_type_counts(states):
    counts: dict[str, int] = {}
    prev = None
    for s in states:
        for ev in diff(prev, s):
            counts[type(ev).__name__] = counts.get(type(ev).__name__, 0) + 1
        prev = s
    return counts


def _source_tree():
    """Parse the committed game_end.log into a complete hslog PacketTree.

    Uses a tz-aware ``_current_date`` per the validated recipe so the emitted
    HSReplay timestamps are real datetimes (not time-only).
    """
    path = FIXTURE_DIR / SOURCE_LOG
    if not path.exists():
        pytest.skip(f"fixture not yet captured: {SOURCE_LOG}")
    parser = LogParser()
    parser._current_date = datetime(2026, 6, 20, tzinfo=timezone.utc)
    with open(path, encoding="utf-8") as f:
        parser.read(f)
    assert parser.games, f"no games parsed from {SOURCE_LOG}"
    return parser.games[0]


def _write_hsreplay(tmp_path: Path) -> Path:
    """Generate a .hsreplay file from the source fixture into tmp_path."""
    tree = _source_tree()
    xml = HSReplayDocument.from_packet_tree([tree]).to_xml()
    out = tmp_path / "game_end.hsreplay"
    out.write_text(xml, encoding="utf-8")
    return out


def test_load_replay_returns_non_empty_states(tmp_path: Path) -> None:
    """A generated .hsreplay loads into a ReplayState with a non-empty timeline."""
    path = _write_hsreplay(tmp_path)
    replay = load_replay(path)
    assert replay.states, "ReplayState.states must be non-empty"
    assert len(replay.states) > 1


def test_friendly_player_matches_exporter(tmp_path: Path) -> None:
    """ReplayState.friendly_player_id matches FriendlyPlayerExporter on the source."""
    expected = FriendlyPlayerExporter(_source_tree()).export()
    path = _write_hsreplay(tmp_path)
    replay = load_replay(path)
    assert replay.friendly_player_id == expected


def test_sequence_spans_game_start_to_end(tmp_path: Path) -> None:
    """diff() across the loaded sequence yields GameStarted near the front
    and GameEnded near the end — proving the timeline spans the whole game.
    """
    path = _write_hsreplay(tmp_path)
    states = load_replay(path).states
    assert len(states) >= 2

    # Cold start: diff(None, states[0]) should announce the game.
    cold = list(diff(None, states[0]))
    started_indices = [
        i
        for i, e in enumerate(
            [cold]
            + [list(diff(states[j], states[j + 1])) for j in range(len(states) - 1)]
        )
        if any(isinstance(ev, GameStarted) for ev in e)
    ]
    ended_indices = [
        j
        for j in range(len(states) - 1)
        if any(isinstance(ev, GameEnded) for ev in diff(states[j], states[j + 1]))
    ]

    assert started_indices, "expected at least one GameStarted across the sequence"
    assert ended_indices, "expected at least one GameEnded across the sequence"
    # GameStarted is near the front (cold start or very first transitions).
    assert min(started_indices) <= 2
    # GameEnded is near the end (in the final third of the transitions).
    last_transition = len(states) - 2
    assert max(ended_indices) >= last_transition - max(1, len(states) // 3)


def test_early_empty_then_later_progress(tmp_path: Path) -> None:
    """An early state has empty boards; a later state reflects game progress
    (a non-empty board OR a terminal game_state appears).
    """
    path = _write_hsreplay(tmp_path)
    states = load_replay(path).states

    early = states[0]
    assert not early.player_board
    assert not early.opponent_board

    def _progress(s) -> bool:
        return (
            bool(s.player_board)
            or bool(s.opponent_board)
            or bool(s.opponent_hand)
            or s.game_state in ("COMPLETE", "ABANDONED")
        )

    assert any(_progress(s) for s in states[1:]), (
        "a later state should reflect progress (board or terminal game_state)"
    )
    # The recorded game reaches a terminal game_state by the end.
    assert states[-1].game_state in ("COMPLETE", "ABANDONED")


def test_states_dedupe_consecutive_duplicates(tmp_path: Path) -> None:
    """No two adjacent captured states are identical (consecutive dedupe)."""
    path = _write_hsreplay(tmp_path)
    states = load_replay(path).states
    for a, b in zip(states, states[1:]):
        assert a != b, "consecutive identical states must be collapsed"


def test_invalid_xml_raises_replay_load_error(tmp_path: Path) -> None:
    """Garbage that is not valid HSReplay XML raises a controlled ReplayLoadError."""
    bad = tmp_path / "garbage.hsreplay"
    bad.write_text("this is not xml <<<>>> not a replay", encoding="utf-8")
    with pytest.raises(ReplayLoadError):
        load_replay(bad)


def test_empty_packet_tree_raises_replay_load_error(tmp_path: Path) -> None:
    """Well-formed XML that yields no usable packet tree raises ReplayLoadError."""
    # Minimal well-formed XML with no <Game> -> no packet trees on load.
    empty = tmp_path / "empty.hsreplay"
    empty.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<HSReplay version="1.7" build="1"></HSReplay>\n',
        encoding="utf-8",
    )
    with pytest.raises(ReplayLoadError):
        load_replay(empty)


# --- Round-trip fidelity regressions (codex review findings) ------------------


def test_block_types_resolved_to_names_not_ints(tmp_path: Path) -> None:
    """Finding: HSReplay XML round-trips Block.type as ints, so block_stack held
    numeric strings ('7') instead of names ('PLAY'). The diff seam's
    block_stack[-1] == 'PLAY' / 'POWER' / 'ATTACK' checks then never matched and
    replay event drilldown silently dropped card-play / attack / damage events.
    The loader must re-resolve Block.type to enum names.
    """
    states = load_replay(_write_hsreplay(tmp_path)).states
    seen = {b for s in states for b in s.block_stack}
    assert seen, "fixture should open at least one block"
    # No raw numeric block-type strings survive.
    assert not any(b.isdigit() for b in seen), f"unresolved int block types: {seen}"
    # Real block-type names appear (this fixture opens PLAY and POWER blocks).
    assert "PLAY" in seen


def test_replay_event_stream_matches_live(tmp_path: Path) -> None:
    """The PRD contract: a replayed game produces the SAME diff-derived GameEvent
    stream it did live. Regression guard for the round-trip enum-resolution: any
    divergence (e.g. int block types, int GameTags) shows up as a mismatch here.
    """
    replay_counts = _event_type_counts(load_replay(_write_hsreplay(tmp_path)).states)
    live_counts = _event_type_counts(_live_states())
    assert replay_counts == live_counts


def test_active_player_id_normalized_to_friendly_contract(tmp_path: Path) -> None:
    """Finding: active_player_id is recorded as a player ENTITY id (2/3), but the
    documented contract (services/_events.py) and the viewer expect 1=friendly /
    2=opponent. The loader normalizes it so consumers can rely on the contract.
    """
    replay = load_replay(_write_hsreplay(tmp_path))
    values = {s.active_player_id for s in replay.states}
    assert values, "expected some states"
    # Only contract values remain (1 friendly, 2 opponent); no raw entity ids (3+).
    assert values <= {1, 2}, f"unnormalized active_player_id values: {values}"
    # At least one turn is attributed to each side for a full two-player game.
    assert 2 in values, "a full game should have at least one opponent turn"
