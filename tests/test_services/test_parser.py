"""Tests for stonereader.services._parser."""
from __future__ import annotations

import logging

import pytest
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
    for line in [
        "D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     GameEntity EntityID=1",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     Player EntityID=3 PlayerID=2 GameAccountId=[hi=2 lo=2]",
    ]:
        emitted.extend(parser.feed_line(line))
    assert any(isinstance(p, CreateGamePacket) for p in emitted), (
        f"Expected CreateGamePacket in {[type(p).__name__ for p in emitted]}"
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
            raise NoSuchEnum("UNKNOWN_TAG")
        return original_read(line)

    monkeypatch.setattr(parser._hslog, "read_line", fake_read)
    with caplog.at_level(logging.WARNING):
        packets = parser.feed_line(
            "D 13:00:00.0000000 GameState.DebugPrintPower() - bogus"
        )
    assert packets == []
    assert any("NoSuchEnum" in rec.message for rec in caplog.records)


def test_no_such_enum_logged_only_once(monkeypatch, caplog):
    """The same NoSuchEnum must be logged only once (log-once cache per Pitfall 6)."""
    from stonereader.services._parser import Parser

    parser = Parser()

    def fake_read(line):
        raise NoSuchEnum("UNKNOWN_TAG")

    monkeypatch.setattr(parser._hslog, "read_line", fake_read)
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            parser.feed_line("D 13:00:00.0000000 x")
    warn_count = sum(1 for r in caplog.records if "NoSuchEnum" in r.message)
    assert warn_count == 1, (
        f"Expected log-once-per-unique-value, got {warn_count} logs"
    )
