"""Shared deck and record data for the Decks family of Surfaces."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol, TypeAlias

from stonereader.db import get_all_decks
from stonereader.models.card import CardDatabase
from stonereader.models.deck import Deck, DeckSummary
from stonereader.services._stats import LAST_GAMES, CorpusRecords, Record
from stonereader.surfaces._spoken import class_name, count
from stonereader.ui.announcer import Announcer


class OfferSubjectSink(Protocol):
    def mark_offer_subject_seen(self, subject: str) -> None: ...


@dataclass(frozen=True)
class DeckRow:
    """A saved deck with the resolved data its Surfaces need."""

    summary: DeckSummary
    deck: Deck

    @property
    def card_count(self) -> int:
        return self.deck.total_cards()


class GamePool(Enum):
    """The Deck pages that are not one saved deck (ADR-0017)."""

    ALL_DECKS = "All decks"
    OTHER_GAMES = "Other games"


DeckSubject: TypeAlias = DeckSummary | GamePool

# On Games, these stand in for a saved deck's name (ADR-0017).
_POOL_GAMES = {GamePool.ALL_DECKS: "All games", GamePool.OTHER_GAMES: "Other games"}


def subject_name(subject: DeckSubject) -> str:
    """Return the Deck page's context label and window title."""
    return subject.value if isinstance(subject, GamePool) else subject.name


def subject_record(records: CorpusRecords, subject: DeckSubject) -> Record:
    if subject is GamePool.ALL_DECKS:
        return records.all_decks
    if subject is GamePool.OTHER_GAMES:
        return records.other_games
    return records.deck(subject.deck_id)


@dataclass(frozen=True)
class Versus:
    opponent_class: str


GamesFilter: TypeAlias = Literal["all", "last"] | Versus


@dataclass(frozen=True)
class GamesSelection:
    """The games behind one Deck page record row."""

    subject: DeckSubject
    games: GamesFilter

    def record(self, records: CorpusRecords) -> Record:
        record = subject_record(records, self.subject)
        match self.games:
            case "all":
                return record
            case "last":
                return record.recent(LAST_GAMES)
            case Versus(opponent_class):
                return record.versus(opponent_class)

    def label(self) -> str:
        """Name the selection: "Odd Hunter games", "All games versus Mage"."""
        if isinstance(self.subject, GamePool):
            name = _POOL_GAMES[self.subject]
        else:
            name = self.subject.name
        match self.games:
            case "all":
                return name if isinstance(self.subject, GamePool) else f"{name} games"
            case "last":
                return f"{name}, last {LAST_GAMES} games"
            case Versus(opponent_class):
                return f"{name} versus {class_name(opponent_class)}"

    @property
    def one_deck(self) -> bool:
        """Whether every game in the selection was played with one saved deck."""
        return isinstance(self.subject, DeckSummary)


class _Current[T]:
    """An app-owned selection seam; every set is a fresh open."""

    def __init__(self, noun: str) -> None:
        self._noun = noun
        self._value: T | None = None
        self._subscribers: list[Callable[[], None]] = []

    def set(self, value: T) -> None:
        self._value = value
        for subscriber in tuple(self._subscribers):
            subscriber()

    def get(self) -> T:
        if self._value is None:
            raise RuntimeError(f"No current {self._noun} has been selected")
        return self._value

    def subscribe(self, on_set: Callable[[], None]) -> None:
        self._subscribers.append(on_set)


class CurrentDeck(_Current[DeckSubject]):
    """The Deck page's subject, shared with Decks, Replays, and Deck detail."""

    def __init__(self) -> None:
        super().__init__("deck")

    def saved(self) -> DeckSummary:
        subject = self.get()
        if isinstance(subject, GamePool):
            raise RuntimeError(f"{subject.value} is not a saved deck")
        return subject


class CurrentGames(_Current[GamesSelection]):
    """The Games Surface's selection, set by a Deck page record row."""

    def __init__(self) -> None:
        super().__init__("games")


class DeckData:
    """Read deck rows from SQLite while caching deckstring resolution."""

    def __init__(self, conn: sqlite3.Connection, card_db: CardDatabase) -> None:
        self._conn = conn
        self._card_db = card_db
        self._decks_by_deckstring: dict[str, Deck] = {}

    def all(self) -> list[DeckRow]:
        """Return current DB contents; providers call this on every access."""
        return [self._row(summary) for summary in get_all_decks(self._conn)]

    def saved(self, deck_id: int | None) -> DeckSummary | None:
        """Return the saved deck with this id, if it still exists."""
        return next(
            (
                summary
                for summary in get_all_decks(self._conn)
                if summary.deck_id == deck_id
            ),
            None,
        )

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
        return DeckRow(summary, deck)


def spoken_record(record: Record) -> str:
    """Say a record: "1 win, 2 losses", ties only when nonzero (ADR-0017)."""
    if not record.games:
        return "no games yet"
    spoken = f"{count(record.wins, 'win')}, {count(record.losses, 'loss', 'losses')}"
    if record.ties:
        spoken += f", {count(record.ties, 'tie')}"
    return spoken


def copy_deck_code(
    summary: DeckSummary,
    announcer: Announcer,
    copy_to_clipboard: Callable[[str], None],
    sink: OfferSubjectSink,
) -> None:
    """Copy a deck code; StoneReader's own copy never comes back as an Offer."""
    copy_to_clipboard(summary.deckstring)
    announcer.confirmation("Deck code copied")
    sink.mark_offer_subject_seen(summary.deckstring)


def unique_import_name(conn: sqlite3.Connection, hero_class: str) -> str:
    """Derive the Import Deck name required by the spec's two-option form."""
    # The form deliberately has no name field, so imported names are derived.
    base = f"{class_name(hero_class)} deck"
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
