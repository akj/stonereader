"""Tests for Deck.from_deckstring graceful-degrade and diagnostic behavior."""

from __future__ import annotations

import pytest

from stonereader.models.card import Card, CardDatabase
from stonereader.models.deck import (
    Deck,
    MissingCardsError,
    count_unknown_cards,
)


# A real deckstring with 1 hero and 0 card slots.
# AAECAZICAAAAAA== = format=Standard, hero DBF=274 (Malfurion), no cards.
_HERO_ONLY_DECKSTRING = "AAECAZICAAAAAA=="


def _make_card(dbf_id: int, name: str = "Real Card") -> Card:
    return Card(
        id=f"REAL_{dbf_id}",
        dbf_id=dbf_id,
        name=name,
        cost=1,
        attack=None,
        health=None,
        text="",
        rarity="COMMON",
        card_class="NEUTRAL",
        card_type="MINION",
        card_set="CORE",
        collectible=True,
    )


def _card_db_with(*cards: Card) -> CardDatabase:
    db = CardDatabase()
    for c in cards:
        db.cards_by_id[c.id] = c
        db.cards_by_dbf_id[c.dbf_id] = c
    return db


def test_missing_cards_error_is_value_error_subclass():
    """Existing `except ValueError` handlers must still catch the new error."""
    err = MissingCardsError((1, 2, 3))
    assert isinstance(err, ValueError)
    assert err.missing_dbf_ids == (1, 2, 3)
    assert "1, 2, 3" in str(err) or "[1, 2, 3]" in str(err)


def test_strict_mode_default_raises_missing_cards_error():
    """Default allow_unknown=False raises MissingCardsError with DBF IDs populated."""
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    deckstring = write_deckstring(
        cards=[(99999, 2)],
        heroes=[274],
        format=FormatType.FT_STANDARD,
    )

    db = _card_db_with(_make_card(274, "Malfurion"))
    with pytest.raises(MissingCardsError) as exc_info:
        Deck.from_deckstring(deckstring, db, "Test")
    assert 99999 in exc_info.value.missing_dbf_ids
    assert "99999" in str(exc_info.value)


def test_from_deckstring_allow_unknown_creates_placeholders():
    """allow_unknown=True returns Deck with placeholder Card entries for unknown DBF IDs."""
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    deckstring = write_deckstring(
        cards=[(99999, 2)],
        heroes=[274],
        format=FormatType.FT_STANDARD,
    )

    db = _card_db_with(_make_card(274, "Malfurion"))
    deck = Deck.from_deckstring(deckstring, db, "Partial", allow_unknown=True)
    assert deck.total_cards() == 2
    assert len(deck.cards) == 1
    placeholder, count = deck.cards[0]
    assert placeholder.dbf_id == 99999
    assert placeholder.name == "Unknown card #99999"
    assert placeholder.id == "UNKNOWN_99999"
    assert placeholder.collectible is False
    assert count == 2


def test_placeholder_to_speech_text_returns_name():
    """Card.to_speech_text contract preserved: returns name only."""
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    deckstring = write_deckstring(
        cards=[(99999, 1)],
        heroes=[274],
        format=FormatType.FT_STANDARD,
    )

    db = _card_db_with(_make_card(274))
    deck = Deck.from_deckstring(deckstring, db, "X", allow_unknown=True)
    placeholder = deck.cards[0][0]
    assert placeholder.to_speech_text() == "Unknown card #99999"


def test_partial_resolution_keeps_known_cards():
    """allow_unknown=True: known cards remain real; only unknowns are placeholders."""
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    deckstring = write_deckstring(
        cards=[(1000, 2), (99999, 1), (2000, 1)],
        heroes=[274],
        format=FormatType.FT_STANDARD,
    )

    db = _card_db_with(
        _make_card(274, "Malfurion"),
        _make_card(1000, "Real A"),
        _make_card(2000, "Real B"),
    )
    deck = Deck.from_deckstring(deckstring, db, "Mixed", allow_unknown=True)
    assert deck.total_cards() == 4
    names = sorted(c.name for c, _ in deck.cards)
    assert "Real A" in names
    assert "Real B" in names
    assert "Unknown card #99999" in names


def test_count_unknown_cards_helper():
    """count_unknown_cards returns the total count across placeholder entries."""
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    deckstring = write_deckstring(
        cards=[(99999, 2), (88888, 1)],
        heroes=[274],
        format=FormatType.FT_STANDARD,
    )

    db = _card_db_with(_make_card(274))
    deck = Deck.from_deckstring(deckstring, db, "Y", allow_unknown=True)
    assert count_unknown_cards(deck) == 3


def test_default_keyword_only_allow_unknown():
    """allow_unknown is keyword-only; positional calls don't accidentally pass it."""
    db = _card_db_with(_make_card(274))
    # Three positional args (deckstring, card_db, name) is the established API.
    deck = Deck.from_deckstring(_HERO_ONLY_DECKSTRING, db, "Hero Only")
    assert deck.name == "Hero Only"


def test_from_deckstring_unchanged_default_behavior_still_raises():
    """No allow_unknown argument => behaves exactly as pre-fix (raises on missing)."""
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    deckstring = write_deckstring(
        cards=[(99999, 1)],
        heroes=[274],
        format=FormatType.FT_STANDARD,
    )

    db = _card_db_with(_make_card(274))
    with pytest.raises(ValueError):
        Deck.from_deckstring(deckstring, db, "Strict")
