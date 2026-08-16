from __future__ import annotations

import sqlite3

import pytest

from stonereader.db import (
    delete_deck,
    get_connection,
    init_db,
    insert_replay,
    save_deck,
)
from stonereader.services._stats import compute_stats


@pytest.fixture
def conn() -> sqlite3.Connection:
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
) -> None:
    insert_replay(
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


def test_corpus_attribution_zero_decks_and_row_order(
    conn: sqlite3.Connection,
) -> None:
    current_id = save_deck(conn, "Current saved name", "MAGE", "Standard", "a")
    save_deck(conn, "Zulu Zero", "MAGE", "Standard", "b")
    save_deck(conn, "Alpha Zero", "MAGE", "Standard", "c")
    deleted_id = save_deck(conn, "Deleted saved name", "MAGE", "Standard", "d")
    delete_deck(conn, deleted_id)

    _replay(
        conn,
        "deleted-new",
        deck_id=deleted_id,
        deck_name="Renamed snapshot",
        played_at="2026-08-16T12:00:00",
    )
    _replay(
        conn,
        "current",
        result="LOST",
        deck_id=current_id,
        deck_name="Current snapshot",
        played_at="2026-08-16T11:00:00",
    )
    _replay(
        conn,
        "other",
        result="UNKNOWN",
        game_type="",
        played_at="2026-08-16T10:00:00",
    )
    _replay(
        conn,
        "deleted-old",
        result="TIED",
        deck_id=deleted_id,
        deck_name="Old snapshot",
        played_at="2026-08-16T09:00:00",
    )
    _replay(conn, "not-member", in_stats=False)
    _replay(conn, "arena", game_type="ARENA")
    _replay(conn, "battlegrounds", game_type="BATTLEGROUNDS")

    rows = compute_stats(conn)

    assert [row.name for row in rows] == [
        "All decks",
        "Renamed snapshot",
        "Current snapshot",
        "Alpha Zero",
        "Zulu Zero",
        "Other games",
    ]
    assert (rows[0].wins, rows[0].losses, rows[0].ties, rows[0].unknowns) == (
        1,
        1,
        1,
        1,
    )
    assert rows[0].total_games == 4
    assert rows[1].total_games == 2
    assert rows[3].total_games == 0
    assert rows[-1].unknowns == 1


def test_unknowns_rate_rounding_and_per_class_order(
    conn: sqlite3.Connection,
) -> None:
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
            deck_name="Rate deck",
            opponent_class=opponent_class,
            played_at=f"2026-08-16T{index:02d}:00:00",
        )

    deck = compute_stats(conn)[1]

    assert (deck.wins, deck.losses, deck.ties, deck.unknowns) == (1, 7, 1, 1)
    assert deck.win_rate_percent == 13
    assert deck.per_class == [
        ("WARRIOR", 1, 1),
        ("DRUID", 0, 3),
        ("MAGE", 0, 3),
    ]
    assert deck.last20 is None


def test_last20_uses_recent_games_and_starts_above_threshold(
    conn: sqlite3.Connection,
) -> None:
    long_id = save_deck(conn, "Long history", "MAGE", "Standard", "a")
    recent_results = ["WON"] * 10 + ["LOST"] * 8 + ["TIED", "UNKNOWN"]
    for index, result in enumerate(recent_results):
        _replay(
            conn,
            f"recent-{index}",
            result=result,
            deck_id=long_id,
            deck_name="Long history",
            played_at=f"2026-08-{31 - index:02d}T12:00:00",
        )
    _replay(
        conn,
        "oldest",
        result="LOST",
        deck_id=long_id,
        deck_name="Long history",
        played_at="2026-08-01T12:00:00",
    )

    threshold_id = save_deck(conn, "Exactly twenty", "MAGE", "Standard", "b")
    for index in range(20):
        _replay(
            conn,
            f"threshold-{index}",
            deck_id=threshold_id,
            deck_name="Exactly twenty",
            played_at=f"2026-07-{20 - index:02d}T12:00:00",
        )

    rows = {row.name: row for row in compute_stats(conn)}

    assert rows["Long history"].last20 == (10, 8)
    assert rows["Long history"].total_games == 21
    assert rows["Exactly twenty"].last20 is None


def test_empty_corpus_has_only_overall_and_saved_decks(
    conn: sqlite3.Connection,
) -> None:
    save_deck(conn, "Unused", "MAGE", "Standard", "a")

    rows = compute_stats(conn)

    assert [row.name for row in rows] == ["All decks", "Unused"]
    assert all(row.total_games == 0 for row in rows)
    assert all(row.win_rate_percent is None for row in rows)
