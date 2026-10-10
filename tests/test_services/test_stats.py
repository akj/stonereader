from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from stonereader.db import (
    delete_deck,
    get_connection,
    init_db,
    insert_replay,
    save_deck,
)
from stonereader.services._stats import Record, compute_records


@pytest.fixture
def conn() -> Generator[sqlite3.Connection, None, None]:
    connection = get_connection(":memory:")
    init_db(connection)
    yield connection
    connection.close()


def _replay(
    conn: sqlite3.Connection,
    checksum: str,
    *,
    result: str = "WON",
    game_type: str = "RANKED",
    in_stats: bool = True,
    deck_id: int | None = None,
    deck_name: str | None = None,
    opponent_class: str = "WARRIOR",
    played_at: str = "2026-08-16T12:00:00",
) -> int:
    return insert_replay(
        conn,
        file_path=f"{checksum}.hsreplay",
        checksum=checksum,
        source="live_auto",
        friendly_class="MAGE",
        opponent_class=opponent_class,
        result=result,
        turns=8,
        game_type=game_type,
        format_type="STANDARD",
        deck_id=deck_id,
        deck_name=deck_name,
        played_at=played_at,
        in_stats=in_stats,
    )


def _ids(record: Record) -> list[int]:
    return [game.id for game in record.games]


def test_corpus_splits_into_saved_decks_plus_other_games(
    conn: sqlite3.Connection,
) -> None:
    saved_id = save_deck(conn, "Saved", "MAGE", "Standard", "a")
    unused_id = save_deck(conn, "Unused", "MAGE", "Standard", "b")
    deleted_id = save_deck(conn, "Deleted", "MAGE", "Standard", "c")
    delete_deck(conn, deleted_id)

    saved_new = _replay(
        conn, "saved-new", deck_id=saved_id, played_at="2026-08-16T12:00:00"
    )
    deleted = _replay(
        conn,
        "deleted",
        result="TIED",
        deck_id=deleted_id,
        deck_name="Deleted",
        played_at="2026-08-16T11:00:00",
    )
    unattributed = _replay(
        conn,
        "unattributed",
        result="UNKNOWN",
        game_type="",
        played_at="2026-08-16T10:00:00",
    )
    arena = _replay(
        conn,
        "arena",
        game_type="ARENA",
        deck_id=saved_id,
        played_at="2026-08-16T09:00:00",
    )
    battlegrounds = _replay(
        conn, "bg", game_type="BATTLEGROUNDS", played_at="2026-08-16T08:00:00"
    )
    saved_old = _replay(
        conn,
        "saved-old",
        result="LOST",
        deck_id=saved_id,
        played_at="2026-08-16T07:00:00",
    )
    _replay(conn, "not-member", deck_id=saved_id, in_stats=False)

    records = compute_records(conn)

    assert _ids(records.all_decks) == [
        saved_new,
        deleted,
        unattributed,
        arena,
        battlegrounds,
        saved_old,
    ]
    assert _ids(records.deck(saved_id)) == [saved_new, saved_old]
    assert _ids(records.deck(unused_id)) == []
    assert _ids(records.deck(deleted_id)) == []
    assert _ids(records.other_games) == [deleted, unattributed, arena, battlegrounds]
    assert sorted(_ids(records.all_decks)) == sorted(
        _ids(records.deck(saved_id))
        + _ids(records.deck(unused_id))
        + _ids(records.other_games)
    )


def test_summary_counts_rate_and_opponent_order(conn: sqlite3.Connection) -> None:
    deck_id = save_deck(conn, "Rate deck", "MAGE", "Standard", "a")
    games = [
        ("WON", "WARRIOR"),
        ("LOST", "WARRIOR"),
        ("TIED", "WARRIOR"),
        ("UNKNOWN", "WARRIOR"),
        ("LOST", "DRUID"),
        ("LOST", "DRUID"),
        ("LOST", "DRUID"),
        ("LOST", "MAGE"),
        ("LOST", "MAGE"),
        ("LOST", "MAGE"),
    ]
    for index, (result, opponent_class) in enumerate(games):
        _replay(
            conn,
            f"game-{index}",
            result=result,
            deck_id=deck_id,
            opponent_class=opponent_class,
            played_at=f"2026-08-16T{index:02d}:00:00",
        )

    record = compute_records(conn).deck(deck_id)

    assert (record.wins, record.losses, record.ties) == (1, 7, 1)
    assert len(record.games) == 10
    assert record.win_rate_percent == 13
    assert [
        (opponent, versus.wins, versus.losses, len(versus.games))
        for opponent, versus in record.by_opponent()
    ] == [
        ("WARRIOR", 1, 1, 4),
        ("DRUID", 0, 3, 3),
        ("MAGE", 0, 3, 3),
    ]
    assert record.versus("DRUID").games == record.by_opponent()[1][1].games


def test_recent_is_the_newest_twenty_games(conn: sqlite3.Connection) -> None:
    deck_id = save_deck(conn, "Long history", "MAGE", "Standard", "a")
    results = ["WON"] * 10 + ["LOST"] * 8 + ["TIED", "UNKNOWN", "LOST"]
    ids = [
        _replay(
            conn,
            f"game-{index}",
            result=result,
            deck_id=deck_id,
            played_at=f"2026-08-{31 - index:02d}T12:00:00",
        )
        for index, result in enumerate(results)
    ]

    record = compute_records(conn).deck(deck_id)
    recent = record.recent()

    assert _ids(recent) == ids[:20]
    assert (recent.wins, recent.losses, recent.ties) == (10, 8, 1)
    assert (record.wins, record.losses, record.ties) == (10, 9, 1)


def test_empty_corpus_has_empty_records_and_no_rate(conn: sqlite3.Connection) -> None:
    deck_id = save_deck(conn, "Unused", "MAGE", "Standard", "a")

    records = compute_records(conn)

    assert records.all_decks == Record()
    assert records.other_games == Record()
    assert records.deck(deck_id) == Record()
    assert records.all_decks.win_rate_percent is None
    assert records.all_decks.by_opponent() == []
