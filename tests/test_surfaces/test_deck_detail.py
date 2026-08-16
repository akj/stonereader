from __future__ import annotations

import sqlite3

from stonereader.db import get_all_decks, get_connection, init_db, save_deck
from stonereader.services._audio_index import CardClip
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.deck_detail import build_deck_detail
from stonereader.surfaces.sounds_menu import SoundsMenuHolder
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import NavigationController
from stonereader.ui.builder import build_active_surface
from stonereader.ui.surface import SurfaceSpec, WidgetType

from tests.test_ui.conftest import FakeSpeech

from .conftest import make_card, make_card_db, make_deckstring


def make_detail(
    conn: sqlite3.Connection,
    audio_index=None,
    sounds: SoundsMenuHolder | None = None,
) -> tuple[HorizontalListEngine, _SinkCore, FakeSpeech, NavigationController]:
    hero = make_card(274, "Garrosh", card_class="WARRIOR", card_type="HERO")
    minion = make_card(
        1000,
        "River Crocolisk",
        cost=2,
        attack=2,
        health=3,
        text="A sturdy beast.",
    )
    weapon = make_card(
        2000,
        "Fiery War Axe",
        card_type="WEAPON",
        cost=3,
        attack=4,
        health=2,
        durability=99,
    )
    card_db = make_card_db(hero, minion, weapon)
    code = make_deckstring([(1000, 2), (2000, 1)])
    save_deck(conn, "Control Warrior", "Warrior", "Standard", code)
    current = CurrentDeck()
    current.set(get_all_decks(conn)[0])
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    titles: list[str] = []
    navigation = NavigationController(
        titles.append,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    if audio_index is not None and sounds is not None:
        navigation.register(
            "Sounds menu",
            lambda: build_active_surface(
                SurfaceSpec(
                    "Sounds menu",
                    WidgetType.VERTICAL_MENU,
                    options=lambda: [],
                ),
                announcer,
                [],
                navigation,
            ),
        )
    navigation.register(
        "Deck detail",
        lambda: build_deck_detail(
            announcer,
            [],
            navigation,
            DeckData(conn, card_db),
            current,
            audio_index=audio_index,
            sounds=sounds,
        ),
    )
    navigation.jump("Deck detail")
    surface = navigation._surfaces["Deck detail"]
    assert isinstance(surface.engine, HorizontalListEngine)
    return surface.engine, sink, speech, navigation


class FakeAudioIndex:
    def __init__(self, status: str, reason: str, clips: list[CardClip]) -> None:
        self.status = status
        self.reason = reason
        self._clips = clips

    def clips_for_card(self, _card_id: str) -> list[CardClip]:
        return list(self._clips)


def test_listen_degenerate_flows_and_ready_push(db_conn: sqlite3.Connection) -> None:
    _engine, sink, speech, nav = make_detail(
        db_conn,
        FakeAudioIndex("indexing", "Game audio is not ready yet", []),
        SoundsMenuHolder(),
    )
    sink.handle_chord(Chord("l"))
    assert nav.stack == ("Home", "Deck detail")
    assert speech.calls[-1] == ("Game audio is not ready yet", True)

    conn = get_connection(":memory:")
    init_db(conn)
    try:
        _engine, sink, speech, nav = make_detail(
            conn,
            FakeAudioIndex("ready", "", []),
            SoundsMenuHolder(),
        )
        sink.handle_chord(Chord("l"))
        assert nav.stack == ("Home", "Deck detail")
        assert speech.calls[-1] == ("River Crocolisk x2: no sounds", True)
    finally:
        conn.close()

    conn = get_connection(":memory:")
    init_db(conn)
    sounds = SoundsMenuHolder()
    try:
        _engine, sink, _speech, nav = make_detail(
            conn,
            FakeAudioIndex("ready", "", [CardClip("Play", "key")]),
            sounds,
        )
        sink.handle_chord(Chord("l"))
        assert nav.stack[-1] == "Sounds menu"
        assert sounds.get().card_name == "River Crocolisk"
    finally:
        conn.close()


def test_titles_details_weapon_durability_and_empty_text_omission(
    db_conn: sqlite3.Connection,
) -> None:
    engine, sink, _speech, _nav = make_detail(db_conn)

    assert engine.items_snapshot() == (
        ["River Crocolisk x2", "Fiery War Axe"],
        0,
        ["2 mana", "Minion", "2 attack, 3 health", "A sturdy beast."],
    )
    sink.handle_chord(Chord("right"))
    assert engine.items_snapshot()[2] == [
        "3 mana",
        "Weapon",
        "4 attack, 2 durability",
    ]


def test_entry_context_and_display_name_window_title(
    db_conn: sqlite3.Connection,
) -> None:
    _engine, _sink, speech, navigation = make_detail(db_conn)
    assert speech.calls == [("Control Warrior, River Crocolisk x2, 1 of 2", True)]
    assert navigation.stack == ("Home", "Deck detail")


def test_read_only_slots_and_unbound_delete_space(db_conn: sqlite3.Connection) -> None:
    _engine, sink, speech, _nav = make_detail(db_conn)
    speech.calls.clear()

    assert sink.handle_chord(Chord("enter")) is True
    assert sink.handle_chord(Chord("l")) is True
    assert sink.handle_chord(Chord("delete")) is False
    assert sink.handle_chord(Chord("space")) is False
    assert speech.calls == [
        ("Nothing to do here", True),
        ("Game audio is not available", True),
    ]
