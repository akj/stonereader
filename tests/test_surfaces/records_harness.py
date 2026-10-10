"""The records family of Surfaces wired as the app wires them (ADR-0017)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from itertools import count
from pathlib import Path

from stonereader.db import save_deck
from stonereader.services._replay_store import ReplayMeta, ReplayStore
from stonereader.surfaces._deck_data import CurrentDeck, CurrentGames, DeckData
from stonereader.surfaces.deck_detail import build_deck_detail
from stonereader.surfaces.deck_page import build_deck_page
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.games import build_games
from stonereader.surfaces.replay_viewer import CurrentReplay
from stonereader.surfaces.replays import build_replays

from .conftest import (
    Harness,
    make_card,
    make_card_db,
    make_deckstring,
    make_harness,
    placeholder_surface,
)

# Sunday 16 August 2026, 6 PM local wall-clock time.
NOW = datetime(2026, 8, 16, 18, 0)


@dataclass
class RecordsContext:
    conn: sqlite3.Connection
    store: ReplayStore
    current_deck: CurrentDeck
    current_games: CurrentGames
    current_replay: CurrentReplay
    copied: list[str]


def make_records_harness(
    conn: sqlite3.Connection,
    replay_dir: Path,
) -> Harness[RecordsContext]:
    """Register Decks, Deck, Deck detail, Games, and Replays for real."""
    card_db = make_card_db(
        make_card(1000, "Arcane Shot", card_class="HUNTER", cost=1),
    )
    store = ReplayStore(conn, replay_dir)
    data = DeckData(conn, card_db)
    current_deck = CurrentDeck()
    current_games = CurrentGames()
    current_replay = CurrentReplay()
    copied: list[str] = []
    harness = make_harness(
        RecordsContext(
            conn, store, current_deck, current_games, current_replay, copied
        )
    )
    nav = harness.nav
    announcer = harness.announcer
    nav.register(
        "Decks",
        lambda: build_decks(
            announcer, [], nav, conn, data, current_deck, harness.sink, copied.append
        ),
    )
    nav.register(
        "Deck",
        lambda: build_deck_page(
            announcer,
            [],
            nav,
            conn,
            data,
            current_deck,
            current_games,
            harness.sink,
            copied.append,
        ),
    )
    nav.register(
        "Deck detail",
        lambda: build_deck_detail(announcer, [], nav, data, current_deck),
    )
    nav.register(
        "Games",
        lambda: build_games(
            announcer,
            [],
            nav,
            conn,
            store,
            card_db,
            current_games,
            current_replay,
            now=lambda: NOW,
        ),
    )
    nav.register(
        "Replays",
        lambda: build_replays(
            announcer,
            [],
            nav,
            store,
            card_db,
            current_replay,
            data,
            current_deck,
            now=lambda: NOW,
        ),
    )
    for name in ("Import Deck", "Import Replays", "Replay Viewer"):
        nav.register(name, lambda name=name: placeholder_surface(name))
    return harness


def save_full_deck(
    conn: sqlite3.Connection,
    name: str,
    hero_class: str,
    *,
    format_name: str = "Standard",
    cards: int = 30,
) -> int:
    return save_deck(
        conn, name, hero_class, format_name, make_deckstring([(1000, cards)])
    )


_unique = count()


def save_game(
    store: ReplayStore,
    *,
    result: str = "WON",
    opponent_class: str = "MAGE",
    turns: int = 8,
    deck_id: int | None = None,
    deck_name: str | None = None,
    game_type: str = "RANKED",
    format_type: str = "STANDARD",
    source: str = "live_auto",
    in_stats: bool = True,
    played_at: str = "2026-08-16T15:36:00",
) -> ReplayMeta:
    """Store one game through the real store, with its file on disk."""
    return store.save_xml(
        f"<game n='{next(_unique)}'/>",
        source=source,
        friendly_class="HUNTER",
        opponent_class=opponent_class,
        result=result,
        turns=turns,
        game_type=game_type,
        format_type=format_type,
        deck_name=deck_name,
        deck_id=deck_id,
        in_stats=in_stats,
        played_at=played_at,
    ).meta


def option_titles(harness: Harness[RecordsContext], name: str) -> list[str]:
    return harness.menu(name).options_snapshot()[0]


def last_spoken(harness: Harness[RecordsContext], n: int = 1) -> list[str]:
    return [text for text, _interrupt in harness.speech.calls[-n:]]
