from __future__ import annotations

from pathlib import Path

from stonereader.db import get_connection, init_db
from stonereader.services._replay_store import ReplayStore
from stonereader.surfaces.replays import build_replays
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.surface import SurfaceSpec, WidgetType

from tests.test_ui.conftest import FakeSpeech


class LandingEngine:
    def on_landing(self, queued: bool = False) -> None:
        pass


def _placeholder(name: str) -> ActiveSurface:
    return ActiveSurface(
        SurfaceSpec(name, WidgetType.VERTICAL_MENU, options=lambda: []),
        LandingEngine(),
        CommandRegistry(),
    )


def _harness(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    store = ReplayStore(conn, tmp_path / "replays")
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    nav.register("Import Replays", lambda: _placeholder("Import Replays"))
    surface = build_replays(announcer, [], nav, store)
    sink.set_active(surface.registry)
    return conn, store, surface, sink, speech, nav


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
    conn, store, surface, _sink, _speech, _nav = _harness(tmp_path)
    _save(
        store,
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
        store,
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
    assert isinstance(surface.engine, HorizontalListEngine)

    assert surface.engine.items_snapshot() == (
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
    surface.engine.jump_to_position(2)
    assert surface.engine.items_snapshot()[2] == [
        "2026-08-15, 21:05",
        "Played Control Mage",
        "Ranked, Standard",
        "Not counted",
        "Imported",
    ]
    surface.engine.jump_to_position(3)
    assert surface.engine.items_snapshot()[2] == []
    conn.close()


def test_all_result_titles_are_spoken_in_title_case(tmp_path):
    conn, store, surface, _sink, _speech, _nav = _harness(tmp_path)
    for index, result in enumerate(("WON", "LOST", "TIED", "UNKNOWN")):
        _save(
            store,
            f"<{result}/>",
            result=result,
            played_at=f"2026-08-{12 + index:02d}T09:30:00",
        )

    assert surface.engine.items_snapshot()[0] == [
        "Unknown versus Warrior, 8 turns",
        "Tied versus Warrior, 8 turns",
        "Lost versus Warrior, 8 turns",
        "Won versus Warrior, 8 turns",
        "Import replays…",
    ]
    conn.close()


def test_space_toggles_cursor_neutrally_and_action_row_is_noop(tmp_path):
    conn, store, surface, sink, speech, _nav = _harness(tmp_path)
    replay = _save(store, "<one/>", in_stats=False)

    sink.handle_chord(Chord("space"))
    assert store.all_replays()[0].in_stats is True
    assert surface.engine.items_snapshot()[1] == 0
    assert speech.calls == [("Included in stats", True)]

    sink.handle_chord(Chord("space"))
    assert store.all_replays()[0].in_stats is False
    assert speech.calls[-1] == ("Excluded from stats", True)
    assert len(speech.calls) == 2

    surface.engine.jump_to_position(2)
    sink.handle_chord(Chord("space"))
    assert speech.calls[-1] == ("Nothing to count here", True)
    assert Path(replay.file_path).exists()
    conn.close()


def test_armed_delete_lifecycle_and_shift_delete_queue_reentry(tmp_path):
    conn, store, surface, sink, speech, _nav = _harness(tmp_path)
    first = _save(store, "<first/>", played_at="2026-08-16T09:30:00")
    second = _save(store, "<second/>", played_at="2026-08-15T09:30:00")

    sink.handle_chord(Chord("delete"))
    sink.handle_chord(Chord("right"))
    sink.handle_chord(Chord("left"))
    sink.handle_chord(Chord("delete"))
    sink.handle_chord(Chord("delete"))

    assert [meta.id for meta in store.all_replays()] == [second.id]
    assert not Path(first.file_path).exists()
    assert speech.calls[-2:] == [
        ("Replay deleted", True),
        ("Replays, Won versus Warrior, 8 turns, 1 of 2", False),
    ]

    sink.handle_chord(Chord("delete", shift=True))
    assert store.all_replays() == []
    assert speech.calls[-2:] == [
        ("Replay deleted", True),
        ("Replays, Import replays…, 1 of 1", False),
    ]

    sink.handle_chord(Chord("delete"))
    assert speech.calls[-1] == ("Nothing to delete here", True)
    conn.close()


def test_enter_dispatches_by_row_kind_and_search_has_exact_noop(tmp_path):
    conn, store, surface, sink, speech, nav = _harness(tmp_path)
    _save(store, "<one/>")

    sink.handle_chord(Chord("enter"))
    assert speech.calls[-1] == ("Replay Viewer: not yet migrated", True)

    surface.engine.jump_to_position(2)
    sink.handle_chord(Chord("enter"))
    assert nav.stack == ("Home", "Import Replays")

    sink.set_active(surface.registry)
    sink.handle_chord(Chord("f", ctrl=True))
    assert speech.calls[-1] == ("No search on this screen", True)
    conn.close()
