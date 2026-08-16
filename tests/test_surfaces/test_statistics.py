from __future__ import annotations

import sqlite3

from stonereader.services._stats import StatsRow
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.statistics import build_statistics
from stonereader.ui.chords import Chord

from .conftest import Harness, make_card_db, make_harness


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
) -> Harness[None]:
    harness = make_harness(None)
    harness.set_surface(
        build_statistics(harness.announcer, [], harness.nav, conn)
    )
    return harness


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
    harness = _harness(db_conn)

    assert harness.horizontal.items_snapshot() == (
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
    harness.horizontal.jump_to_position(2)
    assert harness.horizontal.items_snapshot()[2] == []
    harness.horizontal.jump_to_position(3)
    assert harness.horizontal.items_snapshot()[2] == [
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
    harness = _harness(db_conn)
    harness.nav.register("Statistics", lambda: harness.active_surface)

    harness.nav.jump("Statistics")
    after_entry = calls
    harness.press(Chord("right"))

    assert after_entry >= 1
    assert calls > after_entry
    assert harness.titles == ["Statistics — StoneReader"]
    assert harness.speech.calls[:2] == [
        ("Statistics, All decks, 1 wins, 0 losses, 1 of 2", True),
        ("Mage, 1 wins, 0 losses", True),
    ]


def test_enter_and_unfilled_slots_announce_defaults_but_delete_space_are_silent(
    db_conn: sqlite3.Connection,
) -> None:
    harness = _harness(db_conn)

    for chord in (
        Chord("enter"),
        Chord("pageup"),
        Chord("pagedown"),
        Chord("tab"),
        Chord("tab", shift=True),
        Chord("f", ctrl=True),
        Chord("l"),
    ):
        assert harness.press(chord) is True
    before_silent = list(harness.speech.calls)

    assert harness.press(Chord("delete")) is False
    assert harness.press(Chord("space")) is False
    assert harness.speech.calls == before_silent
    assert harness.speech.calls == [
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
    harness = make_harness(None)
    harness.nav.register(
        "Decks",
        lambda: build_decks(
            harness.announcer,
            [],
            harness.nav,
            db_conn,
            DeckData(db_conn, make_card_db()),
            CurrentDeck(),
            harness.sink,
            lambda _text: None,
        ),
    )
    harness.nav.register(
        "Import Deck",
        lambda: build_statistics(harness.announcer, [], harness.nav, db_conn),
    )
    harness.nav.register(
        "Statistics",
        lambda: build_statistics(harness.announcer, [], harness.nav, db_conn),
    )

    harness.nav.jump("Decks")
    harness.press(Chord("right"))
    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home", "Decks", "Statistics")
    assert harness.titles[-1] == "Statistics — StoneReader"
    assert harness.speech.calls[-1] == (
        "Statistics, All decks, no games yet, 1 of 1",
        True,
    )

    harness.press(Chord("escape"))
    assert harness.nav.stack == ("Home", "Decks")
    assert harness.titles[-1] == "Decks — StoneReader"
    assert harness.speech.calls[-1] == ("Decks, Statistics…, 2 of 2", True)
