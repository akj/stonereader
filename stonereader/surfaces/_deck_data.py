"""Shared lazy deck-row data for the Decks family of Surfaces."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from stonereader.db import get_all_decks
from stonereader.models.card import CardDatabase
from stonereader.models.deck import Deck, DeckSummary


@dataclass(frozen=True)
class DeckRow:
    """A saved deck with the resolved data its Surface needs."""

    summary: DeckSummary
    deck: Deck
    last_played: str | None

    @property
    def card_count(self) -> int:
        return self.deck.total_cards()


class CurrentDeck:
    """App-owned selected-deck seam shared by Decks and Deck detail."""

    def __init__(self) -> None:
        self._summary: DeckSummary | None = None

    def set(self, summary: DeckSummary) -> None:
        self._summary = summary

    def get(self) -> DeckSummary:
        if self._summary is None:
            raise RuntimeError("No current deck has been selected")
        return self._summary


class DeckData:
    """Read deck rows from SQLite while caching deckstring resolution."""

    def __init__(self, conn: sqlite3.Connection, card_db: CardDatabase) -> None:
        self._conn = conn
        self._card_db = card_db
        self._decks_by_deckstring: dict[str, Deck] = {}

    def all(self) -> list[DeckRow]:
        """Return current DB contents; providers call this on every access."""
        return [self._row(summary) for summary in get_all_decks(self._conn)]

    def resolve(self, summary: DeckSummary) -> Deck:
        """Resolve a summary lazily, cached by its deckstring."""
        return self._row(summary).deck

    def _row(self, summary: DeckSummary) -> DeckRow:
        deck = self._decks_by_deckstring.get(summary.deckstring)
        if deck is None:
            deck = Deck.from_deckstring(
                summary.deckstring,
                self._card_db,
                summary.name,
                allow_unknown=True,
            )
            self._decks_by_deckstring[summary.deckstring] = deck
        elif deck.name != summary.name:
            deck = Deck(
                name=summary.name,
                format=deck.format,
                cards=deck.cards,
                hero_class=deck.hero_class,
                deckstring=deck.deckstring,
            )
        return DeckRow(summary, deck, _last_played(self._conn, summary.deck_id))

def unique_import_name(conn: sqlite3.Connection, hero_class: str) -> str:
    """Derive the Import Deck name required by the spec's two-option form."""
    # The form deliberately has no name field, so imported names are derived.
    base = f"{spoken_enum(hero_class)} deck"
    existing = {deck.name for deck in get_all_decks(conn)}
    if base not in existing:
        return base
    suffix = 2
    while f"{base} {suffix}" in existing:
        suffix += 1
    return f"{base} {suffix}"


def spoken_enum(value: str) -> str:
    """Turn Hearthstone enum-style strings into spoken title case."""
    return value.replace("_", " ").title()


def _last_played(conn: sqlite3.Connection, deck_id: int) -> str | None:
    row = conn.execute(
        "SELECT MAX(played_at) AS played_at FROM replays WHERE deck_id = ?",
        (deck_id,),
    ).fetchone()
    if row is None or row["played_at"] is None:
        return None
    played_at = str(row["played_at"])
    return played_at.split("T", 1)[0].split(" ", 1)[0]
