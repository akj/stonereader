from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from hearthstone.deckstrings import write_deckstring
from hearthstone.enums import FormatType

from stonereader.db import get_connection, init_db, save_deck
from stonereader.models.card import Card, CardDatabase
from stonereader.models.game_state import GameEntity, GameState, Hero
from stonereader.services._deck_detect import DeckDetector


class FakeTracker:
    def __init__(self) -> None:
        self.subscriber: Callable[[GameState | None, GameState], None] | None = None

    def subscribe(
        self, callback: Callable[[GameState | None, GameState], None]
    ) -> None:
        self.subscriber = callback

    def emit(self, prev: GameState | None, curr: GameState) -> None:
        assert self.subscriber is not None
        self.subscriber(prev, curr)


def _card(dbf_id: int, *, card_id: str | None = None) -> Card:
    return Card(
        id=card_id or f"CARD_{dbf_id}",
        dbf_id=dbf_id,
        name=f"Card {dbf_id}",
        cost=1,
        attack=1,
        health=1,
        text="",
        rarity="COMMON",
        card_class="MAGE",
        card_type="MINION",
        card_set="TEST",
    )


def _entity(entity_id: int, card: Card) -> GameEntity:
    return GameEntity(
        entity_id=entity_id,
        card_id=card.id,
        base_card=card,
        name=card.name,
        cost=card.cost,
        current_attack=1,
        current_health=1,
        card_type="MINION",
        zone="DECK",
        zone_position=entity_id,
        controller=1,
    )


def _state(player_deck: tuple[GameEntity, ...] = ()) -> GameState:
    hero = Hero("HERO", "Jaina", 30, 0, "", "MAGE")
    return GameState(
        turn=0,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=hero,
        opponent_hero=hero,
        player_deck=player_deck,
    )


def _deck_fixture(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    card_db = CardDatabase()
    hero = _card(274, card_id="HERO_08")
    card_db.cards_by_id[hero.id] = hero
    card_db.cards_by_dbf_id[hero.dbf_id] = hero
    cards = [_card(1000 + index) for index in range(15)]
    for card in cards:
        card_db.cards_by_id[card.id] = card
        card_db.cards_by_dbf_id[card.dbf_id] = card
    deckstring = write_deckstring(
        cards=[(card.dbf_id, 2) for card in cards],
        heroes=[hero.dbf_id],
        format=FormatType.FT_STANDARD,
    )
    entities = tuple(
        _entity(index, card)
        for index, card in enumerate(
            [card for card in cards for _copy in range(2)], start=1
        )
    )
    return conn, card_db, deckstring, entities


def test_unique_exact_match_is_detected(tmp_path):
    conn, card_db, deckstring, entities = _deck_fixture(tmp_path)
    deck_id = save_deck(conn, "Exact Mage", "MAGE", "Standard", deckstring)
    tracker = FakeTracker()
    detector = DeckDetector(tracker, conn, card_db)
    state = _state(entities)

    tracker.emit(None, state)
    tracker.emit(state, state)

    assert detector.detected() == (deck_id, "Exact Mage")
    conn.close()


def test_ambiguous_exact_match_is_not_detected(tmp_path):
    conn, card_db, deckstring, entities = _deck_fixture(tmp_path)
    save_deck(conn, "First", "MAGE", "Standard", deckstring)
    save_deck(conn, "Second", "MAGE", "Standard", deckstring)
    tracker = FakeTracker()
    detector = DeckDetector(tracker, conn, card_db)
    state = _state(entities)

    tracker.emit(None, state)
    tracker.emit(state, state)

    assert detector.detected() is None
    conn.close()


def test_detection_resets_for_the_next_game(tmp_path):
    conn, card_db, deckstring, entities = _deck_fixture(tmp_path)
    save_deck(conn, "Exact Mage", "MAGE", "Standard", deckstring)
    tracker = FakeTracker()
    detector = DeckDetector(tracker, conn, card_db)
    state = _state(entities)
    tracker.emit(None, state)
    tracker.emit(state, state)
    assert detector.detected() is not None

    tracker.emit(None, replace(state, player_deck=()))

    assert detector.detected() is None
    conn.close()
