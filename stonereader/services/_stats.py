"""Records computed directly from the replay store (ADR-0012, ADR-0017)."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from stonereader.db import get_all_decks
from stonereader.services._replay_store import ReplayMeta


LAST_GAMES = 20
_NON_CONSTRUCTED_GAME_TYPES = {"ARENA", "BATTLEGROUNDS"}


@dataclass(frozen=True)
class Record:
    """A set of Stats corpus games, newest first, and what they add up to.

    Ties and unknown results count as games but stay out of the win rate.
    """

    games: tuple[ReplayMeta, ...] = ()

    @property
    def wins(self) -> int:
        return self._results("WON")

    @property
    def losses(self) -> int:
        return self._results("LOST")

    @property
    def ties(self) -> int:
        return self._results("TIED")

    @property
    def win_rate_percent(self) -> int | None:
        """Wins over decided games, rounded half up; None when none decided."""
        decided = self.wins + self.losses
        return (self.wins * 100 + decided // 2) // decided if decided else None

    def recent(self, limit: int = LAST_GAMES) -> Record:
        return Record(self.games[:limit])

    def versus(self, opponent_class: str) -> Record:
        return Record(
            tuple(
                game
                for game in self.games
                if _opponent_class(game) == opponent_class
            )
        )

    def by_opponent(self) -> list[tuple[str, Record]]:
        """Split by opponent class key, most games first, then by key."""
        grouped: dict[str, list[ReplayMeta]] = defaultdict(list)
        for game in self.games:
            grouped[_opponent_class(game)].append(game)
        return [
            (opponent_class, Record(tuple(games)))
            for opponent_class, games in sorted(
                grouped.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        ]

    def _results(self, result: str) -> int:
        return sum(game.result.upper() == result for game in self.games)


@dataclass(frozen=True)
class CorpusRecords:
    """The Stats corpus, split into saved decks and Other games.

    Every corpus game is in exactly one saved deck's record or in Other games,
    so All decks always equals the saved decks plus Other games.
    """

    all_decks: Record
    other_games: Record
    decks: Mapping[int, Record]

    def deck(self, deck_id: int) -> Record:
        return self.decks.get(deck_id, Record())


def compute_records(conn: sqlite3.Connection) -> CorpusRecords:
    """Compute every record from current DB contents; nothing is cached.

    A game counts under a saved deck when it is constructed and attributed to
    that deck's id. Everything else in the corpus is Other games: unattributed
    games, games whose deck was deleted, and arena or Battlegrounds games.
    """
    games = tuple(
        ReplayMeta.from_row(row)
        for row in conn.execute(
            "SELECT * FROM replays WHERE in_stats = 1 "
            "ORDER BY played_at DESC, id DESC"
        ).fetchall()
    )
    by_deck: dict[int, list[ReplayMeta]] = {
        deck.deck_id: [] for deck in get_all_decks(conn)
    }
    other: list[ReplayMeta] = []
    for game in games:
        constructed = (
            (game.game_type or "").upper() not in _NON_CONSTRUCTED_GAME_TYPES
        )
        if constructed and game.deck_id in by_deck:
            by_deck[game.deck_id].append(game)
        else:
            other.append(game)
    return CorpusRecords(
        all_decks=Record(games),
        other_games=Record(tuple(other)),
        decks={
            deck_id: Record(tuple(deck_games))
            for deck_id, deck_games in by_deck.items()
        },
    )


def _opponent_class(game: ReplayMeta) -> str:
    return (game.opponent_class or "UNKNOWN").upper()
