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
        dbf_id=hash(name) & 0xFFFF,
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


def test_key_map_has_navigation_keys():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()

    assert "left" in key_map
    assert "right" in key_map
    assert "up" in key_map
    assert "down" in key_map
    assert "home" in key_map
    assert "end" in key_map


def test_right_arrow_announces_next_card():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["right"]()

    # Initial cursor is 0 (Arcane Intellect), right goes to 1 (Fireball)
    assert "Fireball" in speech.last_speech
    assert "2 of 4" in speech.last_speech


def test_left_arrow_at_start_stays_at_first():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["left"]()

    assert "Arcane Intellect" in speech.last_speech
    assert "1 of 4" in speech.last_speech


def test_down_arrow_reads_first_detail_line():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()

    # First detail line is the card name
    assert "Arcane Intellect" in speech.last_speech


def test_down_arrow_twice_reads_cost():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()
    key_map["down"]()

    assert "3 mana" in speech.last_speech


def test_up_arrow_moves_back_through_details():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()  # name
    key_map["down"]()  # cost
    key_map["up"]()    # back to name

    assert "Arcane Intellect" in speech.last_speech


def test_home_jumps_to_first():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["right"]()
    key_map["right"]()
    key_map["home"]()

    assert "Arcane Intellect" in speech.last_speech
    assert "1 of 4" in speech.last_speech


def test_end_jumps_to_last():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["end"]()

    assert "Wolfrider" in speech.last_speech
    assert "4 of 4" in speech.last_speech


def test_view_callback_fires_on_search():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    received: list[tuple[int, int]] = []

    def on_state_changed(results: list[Card], cursor: int) -> None:
        received.append((len(results), cursor))

    presenter.set_on_state_changed(on_state_changed)
    presenter.search("fire")

    assert received == [(1, 0)]


def test_view_callback_fires_on_navigation():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    received: list[tuple[int, int]] = []

    def on_state_changed(results: list[Card], cursor: int) -> None:
        received.append((len(results), cursor))

    presenter.set_on_state_changed(on_state_changed)
    presenter.move_in_zone(1)  # right

    assert received == [(4, 1)]


def test_copy_current_card_name_returns_name():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    name = presenter.copy_current_card_name()

    assert name == "Arcane Intellect"
    assert "Copied Arcane Intellect" in speech.last_speech


def test_copy_with_no_results_returns_none():
    card_db = make_card_db([])
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    name = presenter.copy_current_card_name()

    assert name is None
