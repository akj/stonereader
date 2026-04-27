"""Shared row-text formatting helpers for the LiveGamePanel zones.

Used by:
    stonereader/views/live_game.py — OnGetItemText for each ListCtrl.

The PRESENTER produces speech strings (per D-13/D-14/D-15) which are
similar but not identical (speech adds N-of-M suffix; visual text uses
parentheses for compactness). Centralizing the visual text here prevents
drift across the 4 OnGetItemText overrides (per 03-REVIEWS.md MEDIUM 03-06 #1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from stonereader.models.card import Card
    from stonereader.models.game_state import PlayedCard
    from stonereader.presenters.live_game import OpponentHandRow


def format_remaining_deck_row(row: Tuple["Card", int]) -> str:
    """Visual row text for the Remaining Deck zone."""
    card, count = row
    return f"{card.name} ({card.cost} mana) — {count}"


def format_opponent_hand_row(row: "OpponentHandRow") -> str:
    """Visual row text for the Opponent Hand zone.

    drawn_turn==-1 displays as '?' (matches presenter's 'unknown' speech
    per 03-REVIEWS.md MEDIUM #5).
    """
    identity = row.identity.name if row.identity else "?"
    turn_str = "?" if row.drawn_turn == -1 else str(row.drawn_turn)
    lineage = f" (gen: {row.lineage})" if row.lineage else ""
    return f"Pos {row.position}: {identity}{lineage} — drawn turn {turn_str}"


def format_opponent_played_row(pc: "PlayedCard") -> str:
    """Visual row text for the Opponent Played zone."""
    return f"Turn {pc.turn} — {pc.name}"


def format_cards_drawn_row(pc: "PlayedCard") -> str:
    """Visual row text for the Cards Drawn zone (LIVE-03)."""
    return f"Turn {pc.turn} — {pc.name} (drawn)"
