from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from stonereader.db import get_connection, init_db
from stonereader.services._replay_store import ReplayStore
from stonereader.surfaces.replay_viewer import CurrentReplay
from stonereader.surfaces.replays import build_replays
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine

from .conftest import Harness, make_card_db, make_harness, placeholder_surface


@dataclass
class ReplaysContext:
    conn: sqlite3.Connection
    store: ReplayStore
    current_replay: CurrentReplay


def _harness(tmp_path: Path) -> Harness[ReplaysContext]:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    store = ReplayStore(conn, tmp_path / "replays")
    current_replay = CurrentReplay()
    harness = make_harness(ReplaysContext(conn, store, current_replay))
    harness.nav.register(
        "Import Replays", lambda: placeholder_surface("Import Replays")
    )
    harness.nav.register(
        "Replay Viewer", lambda: placeholder_surface("Replay Viewer")
    )
    harness.set_surface(
        build_replays(
            harness.announcer,
            [],
            harness.nav,
            store,
            make_card_db(),
            current_replay,
        )
    )
    return harness


def _save(store: ReplayStore, xml: str, **overrides):
    values = {
        "source": "live_auto",
        "friendly_class": "MAGE",
        "opponent_class": "WARRIOR",
        "result": "WON",
        "turns": 8,
        "game_type": "RANKED",
        "format_type": "STANDARD",
        "played_at": "2026-08-16T09:30:00",
        "in_stats": True,
    }
    values.update(overrides)
    return store.save_xml(xml, **values).meta


def test_rows_are_newest_first_then_action_with_every_detail_variant(tmp_path):
    harness = _harness(tmp_path)
    _save(
        harness.context.store,
        "<old/>",
        source="manual_import",
        result="LOST",
        opponent_class="DEATHKNIGHT",
        turns=12,
        deck_id=9,
        deck_name="Control Mage",
        in_stats=False,
        played_at="2026-08-15T21:05:00",
    )
    _save(
        harness.context.store,
        "<new/>",
        result="UNKNOWN",
        opponent_class="MAGE",
        turns=3,
        game_type="",
        format_type="",
        deck_id=None,
        deck_name=None,
        played_at="2026-08-16T09:30:00",
    )
    assert harness.horizontal.items_snapshot() == (
        [
            "Unknown versus Mage, 3 turns",
            "Lost versus Death Knight, 12 turns",
            "Import replays…",
        ],
        0,
        [
            "2026-08-16, 09:30",
            "Deck not detected",
            "Unknown, Unknown",
            "Counted in stats",
            "Live recorded",
        ],
    )
    harness.horizontal.jump_to_position(2)
    assert harness.horizontal.items_snapshot()[2] == [
        "2026-08-15, 21:05",
        "Played Control Mage",
        "Ranked, Standard",
        "Not counted",
        "Imported",
    ]
    harness.horizontal.jump_to_position(3)
    assert harness.horizontal.items_snapshot()[2] == []
    harness.context.conn.close()


def test_all_result_titles_are_spoken_in_title_case(tmp_path):
    harness = _harness(tmp_path)
    for index, result in enumerate(("WON", "LOST", "TIED", "UNKNOWN")):
        _save(
            harness.context.store,
            f"<{result}/>",
            result=result,
            played_at=f"2026-08-{12 + index:02d}T09:30:00",
        )

    assert harness.horizontal.items_snapshot()[0] == [
        "Unknown versus Warrior, 8 turns",
        "Tied versus Warrior, 8 turns",
        "Lost versus Warrior, 8 turns",
        "Won versus Warrior, 8 turns",
        "Import replays…",
    ]
    harness.context.conn.close()


def test_space_toggles_cursor_neutrally_and_action_row_is_noop(tmp_path):
    harness = _harness(tmp_path)
    replay = _save(harness.context.store, "<one/>", in_stats=False)

    harness.press(Chord("space"))
    assert harness.context.store.all_replays()[0].in_stats is True
    assert harness.horizontal.items_snapshot()[1] == 0
    assert harness.speech.calls == [("Included in stats", True)]

    harness.press(Chord("space"))
    assert harness.context.store.all_replays()[0].in_stats is False
    assert harness.speech.calls[-1] == ("Excluded from stats", True)
    assert len(harness.speech.calls) == 2

    harness.horizontal.jump_to_position(2)
    harness.press(Chord("space"))
    assert harness.speech.calls[-1] == ("Nothing to count here", True)
    assert Path(replay.file_path).exists()
    harness.context.conn.close()


def test_armed_delete_lifecycle_and_shift_delete_queue_reentry(tmp_path):
    harness = _harness(tmp_path)
    first = _save(harness.context.store, "<first/>", played_at="2026-08-16T09:30:00")
    second = _save(harness.context.store, "<second/>", played_at="2026-08-15T09:30:00")

    harness.press(Chord("delete"))
    harness.press(Chord("right"))
    harness.press(Chord("left"))
    harness.press(Chord("delete"))
    harness.press(Chord("delete"))

    assert [meta.id for meta in harness.context.store.all_replays()] == [second.id]
    assert not Path(first.file_path).exists()
    assert harness.speech.calls[-2:] == [
        ("Replay deleted", True),
        ("Replays, Won versus Warrior, 8 turns, 1 of 2", False),
    ]

    harness.press(Chord("delete", shift=True))
    assert harness.context.store.all_replays() == []
    assert harness.speech.calls[-2:] == [
        ("Replay deleted", True),
        ("Replays, Import replays…, 1 of 1", False),
    ]

    harness.press(Chord("delete"))
    assert harness.speech.calls[-1] == ("Nothing to delete here", True)
    harness.context.conn.close()


def test_enter_loads_replay_drills_down_and_search_has_exact_noop(
    tmp_path, monkeypatch
):
    harness = _harness(tmp_path)
    _save(harness.context.store, "<one/>")
    loaded = object()
    monkeypatch.setattr(
        "stonereader.surfaces.replays.load_replay",
        lambda _path, _card_db: loaded,
    )

    harness.press(Chord("enter"))
    assert harness.context.current_replay.get() is loaded
    assert harness.nav.stack == ("Home", "Replay Viewer")

    replays = harness.surface
    assert replays is not None
    assert isinstance(replays.engine, HorizontalListEngine)
    harness.sink.set_active(replays.registry)
    replays.engine.jump_to_position(2)
    harness.press(Chord("enter"))
    assert harness.nav.stack == ("Home", "Replay Viewer", "Import Replays")

    harness.sink.set_active(replays.registry)
    harness.press(Chord("f", ctrl=True))
    assert harness.speech.calls[-1] == ("No search on this screen", True)
    harness.context.conn.close()


def test_invalid_replay_is_announced_without_navigation(tmp_path, monkeypatch):
    from stonereader.services._replay_loader import ReplayLoadError

    harness = _harness(tmp_path)
    _save(harness.context.store, "<bad/>")

    def fail(_path, _card_db):
        raise ReplayLoadError("bad replay")

    monkeypatch.setattr("stonereader.surfaces.replays.load_replay", fail)
    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home",)
    assert harness.speech.calls[-1] == (
        "Could not open replay; the file may be invalid",
        True,
    )
    harness.context.conn.close()
