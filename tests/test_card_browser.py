"""Tests for CardBrowserPresenter."""

from __future__ import annotations

from tests.conftest import MockSpeechService
from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.card_browser import CardBrowserPresenter


def make_card(
    name: str = "Test Card",
    cost: int = 1,
    attack: int | None = None,
    health: int | None = None,
    text: str = "",
    card_type: str = "MINION",
    card_class: str = "NEUTRAL",
    rarity: str = "COMMON",
    card_set: str = "CORE",
) -> Card:
    return Card(
        id=f"TEST_{name.upper().replace(' ', '_')}",
        dbf_id=0,
        name=name,
        cost=cost,
        attack=attack,
        health=health,
        text=text,
        rarity=rarity,
        card_class=card_class,
        card_type=card_type,
        card_set=card_set,
        collectible=True,
    )


def make_card_db(cards: list[Card]) -> CardDatabase:
    db = CardDatabase()
    for card in cards:
        db.cards_by_id[card.id] = card
        db.cards_by_dbf_id[card.dbf_id] = card
        db.cards_by_name[card.name.lower()] = card
        db.cards_by_class.setdefault(card.card_class, []).append(card)
        db.cards_by_type.setdefault(card.card_type, []).append(card)
        db.cards_by_set.setdefault(card.card_set, []).append(card)
        db.cards_by_cost.setdefault(card.cost, []).append(card)
        if card.collectible:
            db.collectible_cards.append(card)
    return db


FIREBALL = make_card(name="Fireball", cost=4, text="Deal 6 damage.", card_class="MAGE")
FROSTBOLT = make_card(name="Frostbolt", cost=2, text="Deal 3 damage. Freeze.", card_class="MAGE")
ARCANE = make_card(name="Arcane Intellect", cost=3, text="Draw 2 cards.", card_class="MAGE")
WOLFRIDER = make_card(name="Wolfrider", cost=3, attack=3, health=1, text="Charge")

ALL_CARDS = [FIREBALL, FROSTBOLT, ARCANE, WOLFRIDER]


def test_search_with_query_announces_result_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("fire")

    assert "1 result" in speech.last_speech


def test_search_multiple_results_announces_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("damage")

    assert "2 results" in speech.last_speech


def test_search_no_results_announces_no_results():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("xyz_no_match")

    assert "No results" in speech.last_speech


def test_search_resets_cursor_to_first():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("damage")
    presenter.move_in_zone(1)  # move to second result
    presenter.search("damage")  # search again

    # Cursor should be back at 0
    assert presenter._zone_cursors["results"] == 0


def test_initial_results_are_all_collectible_cards():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    items = presenter.get_zone_items("results")

    assert len(items) == 4
    # Sorted by name
    assert items[0].name == "Arcane Intellect"
    assert items[1].name == "Fireball"
