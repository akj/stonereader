"""Statistics computed directly from the replay store (ADR-0012)."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from stonereader.db import get_all_decks


_NON_CONSTRUCTED_GAME_TYPES = {"ARENA", "BATTLEGROUNDS"}


@dataclass(frozen=True)
class StatsRow:
    """One rendered statistics identity and its computed facts."""

    name: str
    wins: int
    losses: int
    ties: int
    unknowns: int
    win_rate_percent: int | None
    last20: tuple[int, int] | None
    per_class: list[tuple[str, int, int]]
    total_games: int


@dataclass(frozen=True)
class _Game:
    deck_id: int | None
    deck_name: str | None
    result: str
    opponent_class: str
    played_at: str


def compute_stats(conn: sqlite3.Connection) -> list[StatsRow]:
    """Compute every Statistics row from current DB contents.

    The constructed-game exclusion applies to the whole surface, including
    All decks and Other games. Arena and Battlegrounds games do not use saved
    decks, and Statistics lives under Decks as a constructed-games view.
    """
    games = [
        _Game(
            deck_id=row["deck_id"],
            deck_name=row["deck_name"],
            result=str(row["result"]).upper(),
            opponent_class=str(row["opponent_class"] or "UNKNOWN").upper(),
            played_at=str(row["played_at"]),
        )
        for row in conn.execute(
            "SELECT deck_id, deck_name, result, opponent_class, played_at "
            "FROM replays WHERE in_stats = 1 "
            "AND UPPER(game_type) NOT IN (?, ?) "
            "ORDER BY played_at DESC, id DESC",
            tuple(sorted(_NON_CONSTRUCTED_GAME_TYPES)),
        ).fetchall()
    ]

    saved_decks = {deck.deck_id: deck for deck in get_all_decks(conn)}
    attributed: dict[int, list[_Game]] = {}
    other_games: list[_Game] = []
    for game in games:
        if game.deck_id is None:
            other_games.append(game)
        else:
            attributed.setdefault(game.deck_id, []).append(game)

    rows = [_summarize("All decks", games)]
    for deck_id, deck_games in attributed.items():
        # Games are newest first, so the first snapshot is the identity's
        # current display name while deleted decks retain their last snapshot.
        snapshot_name = next(
            (game.deck_name for game in deck_games if game.deck_name),
            None,
        )
        saved_name = (
            saved_decks[deck_id].name if deck_id in saved_decks else None
        )
        rows.append(
            _summarize(snapshot_name or saved_name or "Unknown deck", deck_games)
        )

    zero_game_decks = sorted(
        (
            deck
            for deck_id, deck in saved_decks.items()
            if deck_id not in attributed
        ),
        key=lambda deck: (deck.name, deck.deck_id),
    )
    rows.extend(_summarize(deck.name, []) for deck in zero_game_decks)

    if other_games:
        rows.append(_summarize("Other games", other_games))
    return rows


def _summarize(name: str, games: list[_Game]) -> StatsRow:
    wins = sum(game.result == "WON" for game in games)
    losses = sum(game.result == "LOST" for game in games)
    ties = sum(game.result == "TIED" for game in games)
    unknowns = sum(game.result == "UNKNOWN" for game in games)
    decided = wins + losses
    win_rate = (
        (wins * 100 + decided // 2) // decided if decided else None
    )

    # UNKNOWN results are omitted from the title and rate, while ties are
    # omitted from the rate but exposed for the conditional title suffix.
    # Both remain in the corpus and occupy places in the last-20 window.
    last20: tuple[int, int] | None = None
    if len(games) > 20:
        recent = games[:20]
        last20 = (
            sum(game.result == "WON" for game in recent),
            sum(game.result == "LOST" for game in recent),
        )

    class_games: dict[str, list[_Game]] = defaultdict(list)
    for game in games:
        class_games[game.opponent_class].append(game)
    per_class = [
        (
            opponent_class,
            sum(game.result == "WON" for game in grouped_games),
            sum(game.result == "LOST" for game in grouped_games),
        )
        for opponent_class, grouped_games in sorted(
            class_games.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
    ]

    return StatsRow(
        name=name,
        wins=wins,
        losses=losses,
        ties=ties,
        unknowns=unknowns,
        win_rate_percent=win_rate,
        last20=last20,
        per_class=per_class,
        total_games=len(games),
    )
