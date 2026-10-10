"""Spoken-phrase helpers shared by Surfaces and services (ADR-0007, ADR-0017)."""

from __future__ import annotations

from stonereader.models.card import CARD_CLASS_NAMES, Card


def count(n: int, singular: str, plural: str | None = None) -> str:
    """Return a count whose noun agrees with it: "1 win", "2 losses"."""
    noun = singular if n == 1 else (plural if plural is not None else f"{singular}s")
    return f"{n} {noun}"


def card_label(name: str, card_id: str = "", card: Card | None = None) -> str:
    """Return a card's spoken name, never its internal card id.

    A nameless card with an id but no card data is one StoneReader's card data
    does not include yet: "Unrecognized card". Any other nameless card is one
    the game kept hidden: "Unknown card".
    """
    if name:
        return name
    if card_id and card is None:
        return "Unrecognized card"
    return "Unknown card"


def class_name(value: str | None) -> str:
    """Return a Hearthstone class key as spoken: DEATHKNIGHT is "Death Knight"."""
    key = (value or "").upper() or "UNKNOWN"
    return CARD_CLASS_NAMES.get(key, key.replace("_", " ").title())
