"""Tests for stonereader.services._parser."""

from __future__ import annotations

import logging

from hslog.exceptions import NoSuchEnum


def test_powertasklist_dropped_by_hslog():
    """PowerTaskList lines must produce zero packets — hslog filters them."""
    from stonereader.services._parser import Parser

    parser = Parser()
    line = "D 13:00:00.0000000 PowerTaskList.DebugPrintPower() - CREATE_GAME"
    packets = parser.feed_line(line)
    assert packets == []


def test_translates_create_game_packet():
    """A minimal CREATE_GAME sequence should emit at least one CreateGamePacket."""
    from stonereader.services._packets import CreateGamePacket
    from stonereader.services._parser import Parser

    parser = Parser()
    emitted: list = []
    # The trailing TAG_CHANGE forces hslog to move past the CREATE_GAME's
    # Player block; without it our parser keeps deferring CreateGame emission
    # because it cannot prove the Player rows are complete (D-09/WR-02).
    for line in [
        "D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     GameEntity EntityID=1",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     Player EntityID=3 PlayerID=2 GameAccountId=[hi=2 lo=2]",
        "D 13:00:00.0000000 GameState.DebugPrintPower() - TAG_CHANGE Entity=GameEntity tag=NEXT_STEP value=BEGIN_MULLIGAN",
    ]:
        emitted.extend(parser.feed_line(line))
    assert any(isinstance(p, CreateGamePacket) for p in emitted), (
        f"Expected CreateGamePacket in {[type(p).__name__ for p in emitted]}"
    )
    create_game = next(p for p in emitted if isinstance(p, CreateGamePacket))
    # name is "" because the test fixture omits PlayerName lines; hslog only
    # populates Player.name / PlayerReference.name when the log contains the
    # name string, so the empty-string fallback is the correct expected value.
    assert create_game.players[0] == (2, 1, "", 1, 1), (
        f"Expected (entity_id=2, player_id=1, name='', hi=1, lo=1), got {create_game.players[0]}"
    )
    assert create_game.players[1] == (3, 2, "", 2, 2), (
        f"Expected (entity_id=3, player_id=2, name='', hi=2, lo=2), got {create_game.players[1]}"
    )


def test_no_such_enum_logged_and_skipped(monkeypatch, caplog):
    """NoSuchEnum from hslog must be caught, logged at WARNING, and return []."""
    from stonereader.services._parser import Parser

    parser = Parser()
    # Patch the underlying hslog to raise NoSuchEnum on first feed
    original_read = parser._hslog.read_line
    call_count = {"n": 0}

    def fake_read(line):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise NoSuchEnum("GameTag", "UNKNOWN_TAG")
        return original_read(line)

    monkeypatch.setattr(parser._hslog, "read_line", fake_read)
    with caplog.at_level(logging.WARNING):
        packets = parser.feed_line(
            "D 13:00:00.0000000 GameState.DebugPrintPower() - bogus"
        )
    assert packets == []
    assert any("NoSuchEnum" in rec.message for rec in caplog.records)


def test_live_stream_packet_order_matches_whole_tree(power_log_fixture):
    """The live incremental Parser must emit packets in the SAME order as the
    shared whole-tree translator over the same log.

    A deferred child entity packet must not let a later sibling — or a block's
    own BlockEnd — jump ahead of it, which would process packets outside their
    block context and diverge from replay loading (codex review round 7). The
    walk halts in tree order at the first not-ready packet instead.
    """
    from datetime import datetime, timezone

    from hslog import LogParser as HslogLogParser

    from stonereader.services._hslog_translator import translate_packet_tree
    from stonereader.services._parser import Parser

    lines = power_log_fixture("game_end.log").read_text(encoding="utf-8").splitlines()

    parser = Parser()
    live: list = []
    for line in lines:
        live.extend(parser.feed_line(line))

    hp = HslogLogParser()
    hp._current_date = datetime.now(timezone.utc)
    for line in lines:
        hp.read_line(line)
    whole: list = []
    for tree in hp.games:
        whole.extend(translate_packet_tree(tree))

    assert [type(p).__name__ for p in live] == [type(p).__name__ for p in whole]


def test_no_such_enum_logged_only_once(monkeypatch, caplog):
    """The same NoSuchEnum must be logged only once (log-once cache per Pitfall 6)."""
    from stonereader.services._parser import Parser

    parser = Parser()

    def fake_read(line):
        raise NoSuchEnum("GameTag", "UNKNOWN_TAG")

    monkeypatch.setattr(parser._hslog, "read_line", fake_read)
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            parser.feed_line("D 13:00:00.0000000 x")
    warn_count = sum(1 for r in caplog.records if "NoSuchEnum" in r.message)
    assert warn_count == 1, f"Expected log-once-per-unique-value, got {warn_count} logs"
