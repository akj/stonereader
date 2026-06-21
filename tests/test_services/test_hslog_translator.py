"""Tests for stonereader.services._hslog_translator.

The translator is the single pure place that turns an hslog ``PacketTree`` into
StoneReader internal ``_packets.*``. It is shared by the live ``Parser`` (which
feeds lines incrementally) and the future Replay loader (which parses a whole
file into a tree). These tests lock:

* a real fixture parsed into a whole-file tree translates to the expected
  internal packet sequence (CreateGame first; TagChange/FullEntity present;
  BlockStart/BlockEnd nesting balanced), and
* EQUIVALENCE — the live ``Parser`` fed the SAME fixture line-by-line produces
  the same ordered internal sequence as ``translate_packet_tree`` over the
  whole-file tree (modulo player-name resolution, see ``_normalize`` below).

These are pure service-level tests: no wx, no real speech, no filesystem beyond
reading the committed fixture text.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import List

import pytest

from hslog import LogParser

from stonereader.services._hslog_translator import translate_packet_tree
from stonereader.services._packets import (
    BlockEndPacket,
    BlockStartPacket,
    CreateGamePacket,
    FullEntityPacket,
    Packet,
    TagChangePacket,
)
from stonereader.services._parser import Parser

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "log"


def _tree_from_fixture(name: str):
    """Parse a committed Power.log fixture into a complete hslog PacketTree."""
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"fixture not yet captured: {name}")
    parser = LogParser()
    with open(path, encoding="utf-8") as f:
        parser.read(f)
    assert parser.games, f"no games parsed from {name}"
    return parser.games[0]


def _normalize(p: Packet) -> tuple:
    """Comparable (type, fields) tuple for a packet, modulo player-name resolution.

    The live Parser emits CreateGame as soon as the Player *rows* are complete,
    which is BEFORE hslog resolves the player *names* later in the log. The
    whole-file tree has seen those later lines, so its CreateGame carries the
    resolved names while the incremental one carries "". This is documented,
    expected behavior (see test_parser.test_translates_create_game_packet, where
    the incremental name is asserted to be ""), not a translation bug — so the
    EQUIVALENCE comparison blanks the CreateGame player names on both sides.
    Every other field (entity ids, player ids, hi/lo, tags, packet_id, ordering)
    must match exactly.
    """
    if isinstance(p, CreateGamePacket):
        players = tuple(
            (eid, pid, "", hi, lo) for (eid, pid, _name, hi, lo) in p.players
        )
        p = dataclasses.replace(p, players=players)
    return (type(p).__name__, dataclasses.astuple(p))


def _live_sequence(name: str) -> List[Packet]:
    """Feed a fixture line-by-line through the live Parser, accumulating packets."""
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"fixture not yet captured: {name}")
    parser = Parser()
    out: List[Packet] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        out.extend(parser.feed_line(line))
    return out


def test_module_imports_without_wx_or_filesystem() -> None:
    """The translator must be importable with no wx / I/O / clock dependency."""
    import importlib

    mod = importlib.import_module("stonereader.services._hslog_translator")
    assert hasattr(mod, "translate_packet_tree")
    # Pure: no wx, no real speech, no clock imported by the module.
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "import wx" not in src
    assert "accessible_output" not in src
    assert "time.monotonic" not in src


def test_translate_returns_non_empty_packet_list() -> None:
    """A real fixture tree translates to a non-empty ordered Packet list."""
    tree = _tree_from_fixture("match_start.log")
    packets = translate_packet_tree(tree)
    assert isinstance(packets, list)
    assert len(packets) > 0
    assert all(isinstance(p, Packet) for p in packets)


def test_first_packet_is_create_game() -> None:
    """The first translated packet for a fresh game is CreateGamePacket."""
    tree = _tree_from_fixture("match_start.log")
    packets = translate_packet_tree(tree)
    assert isinstance(packets[0], CreateGamePacket)


def test_contains_tag_change_and_full_entity() -> None:
    """The translated sequence carries the bread-and-butter packet types."""
    tree = _tree_from_fixture("match_start.log")
    packets = translate_packet_tree(tree)
    assert any(isinstance(p, TagChangePacket) for p in packets)
    assert any(isinstance(p, FullEntityPacket) for p in packets)


def test_packet_ids_are_monotonic_from_zero() -> None:
    """packet_id is assigned monotonically from 0 in emission order."""
    tree = _tree_from_fixture("match_start.log")
    packets = translate_packet_tree(tree)
    assert [p.packet_id for p in packets] == list(range(len(packets)))


def test_block_start_eventually_followed_by_matching_block_end() -> None:
    """BlockStart/BlockEnd nesting is preserved: every closed block balances.

    Each BlockStartPacket for a block that closed in the log is eventually
    followed by its matching BlockEndPacket (same block_type and entity_id),
    with strictly LIFO nesting. match_start.log's root TRIGGER blocks both
    close, so the stack must return to empty.
    """
    tree = _tree_from_fixture("match_start.log")
    packets = translate_packet_tree(tree)

    starts = [p for p in packets if isinstance(p, BlockStartPacket)]
    ends = [p for p in packets if isinstance(p, BlockEndPacket)]
    assert starts, "fixture should contain at least one block"

    stack: List[BlockStartPacket] = []
    for p in packets:
        if isinstance(p, BlockStartPacket):
            stack.append(p)
        elif isinstance(p, BlockEndPacket):
            assert stack, "BlockEnd with no open block — nesting broken"
            opened = stack.pop()
            assert opened.block_type == p.block_type
            assert opened.entity_id == p.entity_id
    # match_start's blocks all close in the captured window.
    assert not stack, "every block in match_start.log should be closed"
    assert len(ends) == len(starts)


def test_live_parser_matches_translate_packet_tree() -> None:
    """EQUIVALENCE: live line-by-line Parser == whole-file translate_packet_tree.

    Accumulate the live Parser's incremental output and compare the full
    ordered sequence (packet_id/type/fields) against translating the complete
    tree. They must be identical modulo player-name resolution (see _normalize).
    """
    name = "match_start.log"
    tree = _tree_from_fixture(name)
    whole_file = translate_packet_tree(tree)
    live = _live_sequence(name)

    assert len(live) == len(whole_file), (
        f"length mismatch: live={len(live)} whole_file={len(whole_file)}"
    )
    live_norm = [_normalize(p) for p in live]
    whole_norm = [_normalize(p) for p in whole_file]
    assert live_norm == whole_norm, (
        "live incremental sequence diverges from whole-file translation"
    )


def test_equivalence_preserves_create_game_structure() -> None:
    """The normalized equivalence still pins everything except player names.

    Guards against _normalize over-blanking: the live and whole-file CreateGame
    must agree on entity ids, player ids and hi/lo even though names differ.
    """
    name = "match_start.log"
    whole_file = translate_packet_tree(_tree_from_fixture(name))
    live = _live_sequence(name)

    live_cg = next(p for p in live if isinstance(p, CreateGamePacket))
    whole_cg = next(p for p in whole_file if isinstance(p, CreateGamePacket))

    assert live_cg.game_entity_id == whole_cg.game_entity_id
    assert live_cg.initial_tags == whole_cg.initial_tags
    # Compare player rows excluding the name (index 2).
    live_rows = [(e, pid, hi, lo) for (e, pid, _n, hi, lo) in live_cg.players]
    whole_rows = [(e, pid, hi, lo) for (e, pid, _n, hi, lo) in whole_cg.players]
    assert live_rows == whole_rows
    # And the whole-file parse DID resolve at least one real name, proving the
    # name divergence is genuine resolution (not an empty-on-both no-op).
    assert any(name_ for (_e, _p, name_, _h, _l) in whole_cg.players)
