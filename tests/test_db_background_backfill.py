import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from hslog import LogParser
from hsreplay.document import HSReplayDocument
from hsreplay.utils import set_game_meta_on_game

from stonereader.db import (
    _SCHEMA_V1_LEGACY,
    _SCHEMA_V2,
    _SCHEMA_V4_FRESH,
    _wait_for_replay_backfills,
    get_connection,
    get_schema_version,
    init_db,
    save_deck,
)
from stonereader.models.card import CardDatabase
from stonereader.services import _deck_detect, _replay_loader

PLAYER_TWO_FIXTURE = (
    Path(__file__).parent / "fixtures" / "log" / "player_two_ranked.log"
)


def test_legacy_backfill_runs_after_schema_migration_returns(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    conn.executescript(_SCHEMA_V1_LEGACY)
    conn.executescript(_SCHEMA_V2)
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (2)")
    deck_id = save_deck(conn, "Legacy Deck", "MAGE", "Standard", "deck-code")
    conn.execute(
        """INSERT INTO replays
        (file_path, checksum, source, friendly_class, opponent_class,
         result, turns, played_at)
        VALUES ('legacy.hsreplay', 'legacy', 'live_auto', 'MAGE', 'WARRIOR',
                'WON', 8, '2026-08-16T09:30:00')"""
    )
    conn.commit()

    entered = threading.Event()
    release = threading.Event()

    def load_card_database(cls):
        entered.set()
        assert release.wait(timeout=2)
        return object()

    monkeypatch.setattr(CardDatabase, "load", classmethod(load_card_database))
    monkeypatch.setattr(
        _replay_loader,
        "load_replay",
        lambda path, card_db: SimpleNamespace(states=(object(),)),
    )
    monkeypatch.setattr(
        _deck_detect,
        "detect_deck",
        lambda state, decks, card_db: (deck_id, "Legacy Deck"),
    )

    init_db(conn)

    assert entered.wait(timeout=2)
    assert get_schema_version(conn) == 3
    assert (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='games'"
        ).fetchone()
        is None
    )
    assert (
        conn.execute(
            "SELECT deck_id FROM replays WHERE checksum = 'legacy'"
        ).fetchone()[0]
        is None
    )

    conn.execute("UPDATE replays SET result = 'LOST' WHERE checksum = 'legacy'")
    conn.commit()
    release.set()

    assert _wait_for_replay_backfills(timeout=2)
    row = conn.execute(
        "SELECT deck_id, deck_name, result FROM replays WHERE checksum = 'legacy'"
    ).fetchone()
    assert tuple(row) == (deck_id, "Legacy Deck", "LOST")
    conn.close()


def test_init_db_resumes_interrupted_backfill_at_current_schema(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    deck_id = save_deck(conn, "Legacy Deck", "MAGE", "Standard", "deck-code")
    conn.execute(
        """INSERT INTO replays
        (file_path, checksum, source, friendly_class, opponent_class,
         result, turns, played_at)
        VALUES ('legacy.hsreplay', 'legacy', 'live_auto', 'MAGE', 'WARRIOR',
                'WON', 8, '2026-08-16T09:30:00')"""
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(CardDatabase, "load", classmethod(lambda cls: object()))
    monkeypatch.setattr(
        _replay_loader,
        "load_replay",
        lambda path, card_db: SimpleNamespace(states=(object(),)),
    )
    monkeypatch.setattr(
        _deck_detect,
        "detect_deck",
        lambda state, decks, card_db: (deck_id, "Legacy Deck"),
    )

    conn = get_connection(str(db_path))
    assert get_schema_version(conn) == 4
    init_db(conn)

    assert _wait_for_replay_backfills(timeout=2)
    row = conn.execute(
        "SELECT deck_id, deck_name FROM replays WHERE checksum = 'legacy'"
    ).fetchone()
    assert tuple(row) == (deck_id, "Legacy Deck")
    conn.close()


def _player_two_replay(path: Path) -> Path:
    """Write the synthetic Player 2 fixture as the recorder would save it."""
    parser = LogParser()
    parser._current_date = datetime(2026, 6, 20, tzinfo=timezone.utc)
    with open(PLAYER_TWO_FIXTURE, encoding="utf-8") as f:
        parser.read(f)
    document = HSReplayDocument.from_packet_tree(parser.games)
    set_game_meta_on_game({"hs_game_type": 7, "format": 1}, document.games[0])
    path.write_text(document.to_xml(), encoding="utf-8")
    return path


def test_v3_to_v4_rederives_replay_metadata_and_converges(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    conn.executescript(_SCHEMA_V4_FRESH)
    conn.execute("INSERT INTO schema_version (version) VALUES (3)")
    deck_id = save_deck(conn, "Plague DK", "DEATHKNIGHT", "Wild", "deck-code")
    stored = _player_two_replay(tmp_path / "player_two.hsreplay")
    # What v3 saved for this game: a player's own turn count, no type or format.
    for checksum, file_path in (
        ("stale", str(stored)),
        ("missing", str(tmp_path / "missing.hsreplay")),
    ):
        conn.execute(
            """INSERT INTO replays
            (file_path, checksum, source, friendly_class, opponent_class,
             result, turns, game_type, format_type, deck_name, deck_id,
             played_at, in_stats)
            VALUES (?, ?, 'live_auto', 'DEATHKNIGHT', 'ROGUE', 'LOST', 2,
                    'UNKNOWN', 'UNKNOWN', 'Plague DK', ?,
                    '2026-08-16T19:31:26+00:00', 1)""",
            (file_path, checksum, deck_id),
        )
    conn.commit()

    def rows() -> list[tuple]:
        return [
            tuple(row)
            for row in conn.execute(
                """SELECT checksum, source, friendly_class, opponent_class,
                result, turns, game_type, format_type, deck_name, deck_id,
                in_stats FROM replays ORDER BY checksum"""
            )
        ]

    unchanged = (
        "missing",
        "live_auto",
        "DEATHKNIGHT",
        "ROGUE",
        "LOST",
        2,
        "UNKNOWN",
        "UNKNOWN",
        "Plague DK",
        deck_id,
        1,
    )
    repaired = (
        "stale",
        "live_auto",
        "DEATHKNIGHT",
        "ROGUE",
        "LOST",
        4,
        "RANKED",
        "WILD",
        "Plague DK",
        deck_id,
        1,
    )

    init_db(conn)
    assert _wait_for_replay_backfills(timeout=10)
    assert rows() == [unchanged, repaired]
    assert get_schema_version(conn) == 4

    # A pass that died before its commit leaves v3; repeating it converges.
    conn.execute("UPDATE schema_version SET version = 3")
    conn.commit()
    init_db(conn)
    assert _wait_for_replay_backfills(timeout=10)
    assert rows() == [unchanged, repaired]
    assert get_schema_version(conn) == 4
    conn.close()
