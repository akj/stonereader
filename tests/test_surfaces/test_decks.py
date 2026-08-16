from __future__ import annotations

import sqlite3

from stonereader.db import get_all_decks, insert_replay, save_deck
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.decks import build_decks
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.surface import SurfaceSpec, WidgetType

from tests.test_ui.conftest import FakeSpeech

from .conftest import make_card, make_card_db, make_deckstring


class SeenSink:
    def __init__(self) -> None:
        self.subjects: list[str] = []

    def mark_offer_subject_seen(self, subject: str) -> None:
        self.subjects.append(subject)


class LandingEngine:
    def on_landing(self, queued: bool = False) -> None:
        pass


def placeholder(name: str) -> ActiveSurface:
    return ActiveSurface(
        SurfaceSpec(name, WidgetType.VERTICAL_MENU, options=lambda: []),
        LandingEngine(),
        CommandRegistry(),
    )


def make_surface(
    conn: sqlite3.Connection,
    *,
    offer_sink: SeenSink | _SinkCore | None = None,
) -> tuple[
    ActiveSurface,
    _SinkCore,
    FakeSpeech,
    NavigationController,
    CurrentDeck,
    list[str],
    SeenSink | _SinkCore,
]:
    hero = make_card(274, "Jaina", card_class="MAGE", card_type="HERO")
    card = make_card(1000, "Arcane Bolt")
    card_db = make_card_db(hero, card)
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    copied: list[str] = []
    current = CurrentDeck()
    navigation = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda active: sink.set_active(active.registry),
    )
    navigation.register("Deck detail", lambda: placeholder("Deck detail"))
    navigation.register("Import Deck", lambda: placeholder("Import Deck"))
    navigation.register("Statistics", lambda: placeholder("Statistics"))
    actual_offer_sink = offer_sink or SeenSink()
    surface = build_decks(
        announcer,
        [],
        navigation,
        conn,
        DeckData(conn, card_db),
        current,
        actual_offer_sink,
        copied.append,
    )
    sink.set_active(surface.registry)
    return surface, sink, speech, navigation, current, copied, actual_offer_sink


def seed_decks(conn: sqlite3.Connection) -> tuple[str, str, int, int]:
    code_one = make_deckstring([(1000, 1)])
    code_two = make_deckstring([(1000, 2)])
    first_id = save_deck(conn, "First", "Mage", "Standard", code_one)
    second_id = save_deck(conn, "Second", "Mage", "Standard", code_two)
    return code_one, code_two, first_id, second_id


def test_rows_are_decks_then_actions_with_every_detail_line(
    db_conn: sqlite3.Connection,
) -> None:
    _first_code, _second_code, _first_id, second_id = seed_decks(db_conn)
    insert_replay(
        db_conn,
        file_path="second.hsreplay",
        checksum="second",
        source="manual_import",
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="WON",
        turns=8,
        deck_id=second_id,
        played_at="2026-08-15T22:10:00",
    )
    surface, sink, _speech, _nav, _current, _copied, _seen = make_surface(db_conn)
    assert isinstance(surface.engine, HorizontalListEngine)

    assert surface.engine.items_snapshot() == (
        ["Second", "First", "Import deck…", "Statistics…"],
        0,
        ["Mage, Standard", "2 cards", "Last played 2026-08-15"],
    )
    sink.handle_chord(Chord("right"))
    assert surface.engine.items_snapshot()[2] == [
        "Mage, Standard",
        "1 cards",
        "Never played",
    ]
    sink.handle_chord(Chord("right"))
    assert surface.engine.items_snapshot()[2] == []


def test_armed_delete_move_disarms_then_repeat_deletes_with_queued_reentry(
    db_conn: sqlite3.Connection,
) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Aggro Shaman", "Mage", "Standard", code)
    _surface, sink, speech, _nav, _current, _copied, _seen = make_surface(db_conn)

    sink.handle_chord(Chord("delete"))
    sink.handle_chord(Chord("right"))
    sink.handle_chord(Chord("left"))
    sink.handle_chord(Chord("delete"))
    sink.handle_chord(Chord("delete"))

    assert get_all_decks(db_conn) == []
    assert speech.calls == [
        ("Press Delete again to delete Aggro Shaman", True),
        ("Import deck…", True),
        ("Aggro Shaman", True),
        ("Press Delete again to delete Aggro Shaman", True),
        ("Aggro Shaman deleted", True),
        ("Decks, Import deck…, 1 of 2", False),
    ]


def test_shift_delete_is_immediate(db_conn: sqlite3.Connection) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Tempo Mage", "Mage", "Standard", code)
    _surface, sink, speech, _nav, _current, _copied, _seen = make_surface(db_conn)

    sink.handle_chord(Chord("delete", shift=True))

    assert get_all_decks(db_conn) == []
    assert speech.calls == [
        ("Tempo Mage deleted", True),
        ("Decks, Import deck…, 1 of 2", False),
    ]


def test_copy_confirms_marks_seen_and_own_copy_never_offers(
    db_conn: sqlite3.Connection,
) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Copy Me", "Mage", "Standard", code)
    speech = FakeSpeech()
    offer_core = _SinkCore(Announcer(speech), lambda: None)
    surface, sink, surface_speech, _nav, _current, copied, _seen = make_surface(
        db_conn,
        offer_sink=offer_core,
    )
    assert surface is not None

    sink.handle_chord(Chord("c"))

    assert copied == [code]
    assert surface_speech.calls == [("Deck code copied", True)]
    assert offer_core.arm_offer(code, lambda: None) is False


def test_enter_dispatches_for_deck_import_and_statistics_rows(
    db_conn: sqlite3.Connection,
) -> None:
    code = make_deckstring([(1000, 1)])
    save_deck(db_conn, "Open Me", "Mage", "Standard", code)
    _surface, sink, _speech, nav, current, _copied, _seen = make_surface(db_conn)
    sink.handle_chord(Chord("enter"))
    assert current.get().name == "Open Me"
    assert nav.stack == ("Home", "Deck detail")

    empty_conn = sqlite3.connect(":memory:")
    empty_conn.row_factory = sqlite3.Row
    from stonereader.db import init_db

    init_db(empty_conn)
    try:
        _surface, sink, _speech, nav, _current, _copied, _seen = make_surface(
            empty_conn
        )
        sink.handle_chord(Chord("enter"))
        assert nav.stack == ("Home", "Import Deck")

        _surface, sink, _speech, nav, _current, _copied, _seen = make_surface(
            empty_conn
        )
        sink.handle_chord(Chord("right"))
        sink.handle_chord(Chord("enter"))
        assert nav.stack == ("Home", "Statistics")
    finally:
        empty_conn.close()


def test_action_rows_get_exact_delete_and_copy_noops(
    db_conn: sqlite3.Connection,
) -> None:
    _surface, sink, speech, _nav, _current, _copied, _seen = make_surface(db_conn)
    for chord in (Chord("delete"), Chord("delete", shift=True), Chord("c")):
        sink.handle_chord(chord)
    assert speech.calls == [
        ("Nothing to delete here", True),
        ("Nothing to delete here", True),
        ("Nothing to copy here", True),
    ]
