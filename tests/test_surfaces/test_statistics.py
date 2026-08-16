from __future__ import annotations

import sqlite3

from stonereader.services._stats import StatsRow
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.statistics import build_statistics
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController

from tests.test_ui.conftest import FakeSpeech

from .conftest import make_card_db


def _row(
    name: str,
    wins: int,
    losses: int,
    *,
    ties: int = 0,
    unknowns: int = 0,
    rate: int | None = None,
    last20: tuple[int, int] | None = None,
    per_class: list[tuple[str, int, int]] | None = None,
    total: int | None = None,
) -> StatsRow:
    return StatsRow(
        name,
        wins,
        losses,
        ties,
        unknowns,
        rate,
        last20,
        per_class or [],
        wins + losses + ties + unknowns if total is None else total,
    )


def _harness(
    conn: sqlite3.Connection,
) -> tuple[
    ActiveSurface,
    _SinkCore,
    FakeSpeech,
    NavigationController,
    list[str],
]:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    titles: list[str] = []
    nav = NavigationController(
        titles.append,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    surface = build_statistics(announcer, [], nav, conn)
    sink.set_active(surface.registry)
    return surface, sink, speech, nav, titles


def test_rows_titles_and_details_are_verbatim(
    db_conn: sqlite3.Connection,
    monkeypatch,
) -> None:
    rows = [
        _row(
            "All decks",
            2,
            1,
            ties=1,
            rate=67,
            per_class=[("DEATHKNIGHT", 2, 0), ("MAGE", 0, 1)],
        ),
        _row("Empty deck", 0, 0),
        _row(
            "Recent deck",
            11,
            10,
            rate=52,
            last20=(10, 10),
            total=21,
        ),
    ]
    monkeypatch.setattr(
        "stonereader.surfaces.statistics.compute_stats",
        lambda _conn: rows,
    )
    surface, _sink, _speech, _nav, _titles = _harness(db_conn)
    assert isinstance(surface.engine, HorizontalListEngine)

    assert surface.engine.items_snapshot() == (
        [
            "All decks, 2 wins, 1 losses, 1 ties",
            "Empty deck, no games yet",
            "Recent deck, 11 wins, 10 losses",
        ],
        0,
        [
            "Win rate, 67 percent",
            "Versus Death Knight, 2 wins, 0 losses",
            "Versus Mage, 0 wins, 1 losses",
        ],
    )
    surface.engine.jump_to_position(2)
    assert surface.engine.items_snapshot()[2] == []
    surface.engine.jump_to_position(3)
    assert surface.engine.items_snapshot()[2] == [
        "Win rate, 52 percent",
        "Last 20 games, 10 wins, 10 losses",
    ]


def test_entry_title_and_provider_recompute_on_entry_and_movement(
    db_conn: sqlite3.Connection,
    monkeypatch,
) -> None:
    calls = 0
    rows = [_row("All decks", 1, 0, rate=100), _row("Mage", 1, 0, rate=100)]

    def compute(_conn: sqlite3.Connection) -> list[StatsRow]:
        nonlocal calls
        calls += 1
        return rows

    monkeypatch.setattr("stonereader.surfaces.statistics.compute_stats", compute)
    surface, sink, speech, nav, titles = _harness(db_conn)
    nav.register("Statistics", lambda: surface)

    nav.jump("Statistics")
    after_entry = calls
    sink.handle_chord(Chord("right"))

    assert after_entry >= 1
    assert calls > after_entry
    assert titles == ["Statistics — StoneReader"]
    assert speech.calls[:2] == [
        ("Statistics, All decks, 1 wins, 0 losses, 1 of 2", True),
        ("Mage, 1 wins, 0 losses", True),
    ]


def test_enter_and_unfilled_slots_announce_defaults_but_delete_space_are_silent(
    db_conn: sqlite3.Connection,
) -> None:
    _surface, sink, speech, _nav, _titles = _harness(db_conn)

    for chord in (
        Chord("enter"),
        Chord("pageup"),
        Chord("pagedown"),
        Chord("tab"),
        Chord("tab", shift=True),
        Chord("f", ctrl=True),
        Chord("l"),
    ):
        assert sink.handle_chord(chord) is True
    before_silent = list(speech.calls)

    assert sink.handle_chord(Chord("delete")) is False
    assert sink.handle_chord(Chord("space")) is False
    assert speech.calls == before_silent
    assert speech.calls == [
        ("Nothing to do here", True),
        ("No pages on this screen", True),
        ("No pages on this screen", True),
        ("No groups on this screen", True),
        ("No groups on this screen", True),
        ("No search on this screen", True),
        ("No card focused", True),
    ]


def test_decks_statistics_action_drills_down_and_back_returns_to_decks(
    db_conn: sqlite3.Connection,
) -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    titles: list[str] = []
    nav = NavigationController(
        titles.append,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    nav.register(
        "Decks",
        lambda: build_decks(
            announcer,
            [],
            nav,
            db_conn,
            DeckData(db_conn, make_card_db()),
            CurrentDeck(),
            sink,
            lambda _text: None,
        ),
    )
    nav.register("Import Deck", lambda: build_statistics(announcer, [], nav, db_conn))
    nav.register("Statistics", lambda: build_statistics(announcer, [], nav, db_conn))

    nav.jump("Decks")
    sink.handle_chord(Chord("right"))
    sink.handle_chord(Chord("enter"))

    assert nav.stack == ("Home", "Decks", "Statistics")
    assert titles[-1] == "Statistics — StoneReader"
    assert speech.calls[-1] == (
        "Statistics, All decks, no games yet, 1 of 1",
        True,
    )

    sink.handle_chord(Chord("escape"))
    assert nav.stack == ("Home", "Decks")
    assert titles[-1] == "Decks — StoneReader"
    assert speech.calls[-1] == ("Decks, Statistics…, 2 of 2", True)
