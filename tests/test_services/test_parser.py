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


@pytest.mark.parametrize(
    "fixture_name",
    [
        "game_end.log",
        "reveals_and_new_cards.log",
        "sub_spell_reveal_then_game_end.log",
    ],
)
def test_live_stream_packet_order_matches_whole_tree(power_log_fixture, fixture_name):
    """The live incremental Parser must emit packets in the SAME order as the
    shared whole-tree translator over the same log.

    A deferred child entity packet must not let a later sibling — or a block's
    own BlockEnd — jump ahead of it, which would process packets outside their
    block context and diverge from replay loading (codex review round 7). The
    walk halts in tree order at the first not-ready packet instead, and must
    resume once that packet's container closes.
    """
    from datetime import datetime, timezone

    from hslog import LogParser as HslogLogParser

    from stonereader.services._hslog_translator import translate_packet_tree
    from stonereader.services._packets import GameMetaPacket
    from stonereader.services._parser import Parser

    lines = power_log_fixture(fixture_name).read_text(encoding="utf-8").splitlines()

    parser = Parser()
    live: list = []
    for line in lines:
        live.extend(parser.feed_line(line))
    # Game meta comes from DebugPrintGame() lines, outside the packet tree.
    live = [p for p in live if not isinstance(p, GameMetaPacket)]

    hp = HslogLogParser()
    hp._current_date = datetime.now(timezone.utc)
    for line in lines:
        hp.read_line(line)
    whole: list = []
    for tree in hp.games:
        whole.extend(translate_packet_tree(tree))

    assert [type(p).__name__ for p in live] == [type(p).__name__ for p in whole]


def test_a_reveal_ending_a_sub_spell_does_not_silence_the_rest_of_the_game(
    power_log_fixture,
):
    """Power.log lines through the tracker and narrator, wired as the app wires
    them.

    sub_spell_reveal_then_game_end.log: a hero power draws Novice Engineer
    inside a SubSpell whose last line is the reveal. Only tag changes follow:
    turn 2, lethal damage, and PLAYSTATE LOST. hslog never clears its entity
    packet pointer, so the reveal must be released when its SubSpell closes,
    or every later packet waits for an entity line that never comes.
    """
    from stonereader.models.card import Card, CardDatabase
    from stonereader.services._narrator import Narrator
    from stonereader.services._tracker import GameTracker

    engineer = Card(
        "EX1_015", 284, "Novice Engineer", 2, 1, 1, "", "COMMON", "NEUTRAL", "MINION"
    )
    card_db = CardDatabase(cards_by_id={engineer.id: engineer})
    tracker = GameTracker(card_db=card_db)
    spoken: list[str] = []

    class _Narrations:
        def narrate(self, text: str) -> None:
            spoken.append(text)

    narrator = Narrator(_Narrations(), lambda: "key_moments", card_db)  # type: ignore[arg-type]
    tracker.subscribe(narrator.on_state)

    log = power_log_fixture("sub_spell_reveal_then_game_end.log")
    tracker._on_lines(log.read_text(encoding="utf-8").splitlines())

    state = tracker.current_state
    assert state is not None
    assert (state.turn, state.game_state) == (2, "COMPLETE")
    assert [entity.name for entity in state.player_hand] == ["Novice Engineer"]
    assert spoken == ["Game over, lost"]


def test_a_reveal_ending_a_block_is_emitted_on_the_block_end_line():
    """The same hold-back outside a SubSpell: a reveal that is a block's last
    line is released by that BLOCK_END, with its tag rows, rather than waiting
    for the next entity line.
    """
    from stonereader.services._packets import BlockEndPacket, ShowEntityPacket
    from stonereader.services._parser import Parser

    prefix = "D 13:00:00.0000000 GameState.DebugPrintPower() - "
    parser = Parser()
    for line in [
        prefix + "CREATE_GAME",
        prefix + "    GameEntity EntityID=1",
        prefix + "    Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]",
        prefix + "    Player EntityID=3 PlayerID=2 GameAccountId=[hi=2 lo=2]",
        prefix
        + "BLOCK_START BlockType=POWER Entity=10 EffectCardId=System.Collections"
        + ".Generic.List`1[System.String] EffectIndex=0 Target=0 SubOption=-1",
        prefix + "    SHOW_ENTITY - Updating Entity=4 CardID=EX1_015",
        prefix + "        tag=CONTROLLER value=1",
        prefix + "        tag=ZONE value=HAND",
    ]:
        parser.feed_line(line)

    closed = parser.feed_line(prefix + "BLOCK_END")

    assert [type(p).__name__ for p in closed] == ["ShowEntityPacket", "BlockEndPacket"]
    reveal, block_end = closed
    assert isinstance(reveal, ShowEntityPacket)
    assert (reveal.entity_id, reveal.card_id, reveal.tags) == (
        4,
        "EX1_015",
        {"CONTROLLER": 1, "ZONE": 3},
    )
    assert isinstance(block_end, BlockEndPacket)
    assert (block_end.block_type, block_end.entity_id) == ("POWER", 10)


def test_game_type_and_format_lines_emit_game_meta_every_game():
    """hslog keeps game type and format outside the packet tree and never
    clears them between games, so each line emits a packet even when the value
    repeats the previous game's: the engine resets both at CREATE_GAME.
    """
    from stonereader.services._packets import GameMetaPacket
    from stonereader.services._parser import Parser

    def create_game(ts: str) -> list[str]:
        prefix = f"D {ts} GameState.DebugPrintPower() - "
        return [
            prefix + "CREATE_GAME",
            prefix + "    GameEntity EntityID=1",
            prefix + "    Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]",
            prefix + "    Player EntityID=3 PlayerID=2 GameAccountId=[hi=2 lo=2]",
        ]

    parser = Parser()
    lines = [
        *create_game("13:00:00.0000000"),
        "D 13:00:00.0000000 GameState.DebugPrintGame() - BuildNumber=1",
        "D 13:00:00.0000000 GameState.DebugPrintGame() - GameType=GT_RANKED",
        "D 13:00:00.0000000 GameState.DebugPrintGame() - FormatType=FT_WILD",
        "D 13:00:00.0000000 GameState.DebugPrintGame() - ScenarioID=2",
        *create_game("13:10:00.0000000"),
        "D 13:10:00.0000000 GameState.DebugPrintGame() - GameType=GT_RANKED",
    ]
    emitted = [p for line in lines for p in parser.feed_line(line)]

    assert [
        (p.game_type, p.format_type) for p in emitted if isinstance(p, GameMetaPacket)
    ] == [(7, None), (None, 1), (7, None)]


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
