from __future__ import annotations

import sqlite3

import pytest
from hearthstone.deckstrings import write_deckstring
from hearthstone.enums import FormatType

from stonereader.db import get_connection, init_db
from stonereader.models.card import Card, CardDatabase


@pytest.fixture
def db_conn() -> sqlite3.Connection:
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()


def make_card(
    dbf_id: int,
    name: str,
    *,
    card_class: str = "NEUTRAL",
    card_type: str = "MINION",
    cost: int = 1,
    attack: int | None = None,
    health: int | None = None,
    text: str = "",
    durability: int | None = None,
) -> Card:
    return Card(
        id=f"CARD_{dbf_id}",
        dbf_id=dbf_id,
        name=name,
        cost=cost,
        attack=attack,
        health=health,
        text=text,
        rarity="COMMON",
        card_class=card_class,
        card_type=card_type,
        card_set="TEST",
        durability=durability,
    )


def make_card_db(*cards: Card) -> CardDatabase:
    card_db = CardDatabase()
    for card in cards:
        card_db.cards_by_id[card.id] = card
        card_db.cards_by_dbf_id[card.dbf_id] = card
    return card_db


def make_deckstring(
    cards: list[tuple[int, int]],
    *,
    hero: int = 274,
) -> str:
    return write_deckstring(
        cards=cards,
        heroes=[hero],
        format=FormatType.FT_STANDARD,
    )
