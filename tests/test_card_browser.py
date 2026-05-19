"""Tests for CardBrowserPresenter."""

from __future__ import annotations

from tests.conftest import MockSpeechService
from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.card_browser import CardBrowserPresenter


_next_dbf_id = 0


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
    global _next_dbf_id
    _next_dbf_id += 1
    return Card(
        id=f"TEST_{name.upper().replace(' ', '_')}",
        dbf_id=_next_dbf_id,
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
FROSTBOLT = make_card(
    name="Frostbolt", cost=2, text="Deal 3 damage. Freeze.", card_class="MAGE"
)
ARCANE = make_card(
    name="Arcane Intellect", cost=3, text="Draw 2 cards.", card_class="MAGE"
)
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


def test_key_map_has_hsa_keys():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()

    assert "tab" in key_map
    assert "shift+tab" in key_map
    assert "pagedown" in key_map
    assert "pageup" in key_map
    for digit in range(10):
        assert str(digit) in key_map


def test_tab_key_cycles_class():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))
    presenter.get_key_map()["tab"]()

    assert statuses and "Demon Hunter" in statuses[-1]


def test_digit_key_applies_mana_filter():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.get_key_map()["3"]()

    items = presenter.get_zone_items("results")
    assert sorted(c.name for c in items) == ["Arcane Intellect", "Wolfrider"]


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

    # No prior navigation announced the name, so first detail line is name
    assert "Arcane Intellect" in speech.last_speech


def test_down_arrow_twice_reads_cost():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()
    key_map["down"]()

    assert "3 mana" in speech.last_speech


def test_down_after_navigate_skips_name():
    """After left/right announces the name, down reads cost (not name again)."""
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["right"]()  # announces "Fireball, 2 of 4"
    key_map["down"]()  # should skip name, read cost

    assert "4 mana" in speech.last_speech


def test_up_arrow_moves_back_through_details():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()  # name
    key_map["down"]()  # cost
    key_map["up"]()  # back to name

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


def test_view_callback_fires_on_home():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.move_in_zone(1)  # move to index 1
    received: list[tuple[int, int]] = []

    def on_state_changed(results: list[Card], cursor: int) -> None:
        received.append((len(results), cursor))

    presenter.set_on_state_changed(on_state_changed)
    presenter.jump_to_first()

    assert received == [(4, 0)]


def test_view_callback_fires_on_end():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    received: list[tuple[int, int]] = []

    def on_state_changed(results: list[Card], cursor: int) -> None:
        received.append((len(results), cursor))

    presenter.set_on_state_changed(on_state_changed)
    presenter.jump_to_last()

    assert received == [(4, 3)]


def test_status_callback_fires_on_search():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))
    presenter.search("fire")

    assert statuses == ["1 result"]


def test_status_callback_no_results():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))
    presenter.search("xyz_no_match")

    assert statuses == ["No results"]


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


def test_card_class_filter_limits_results():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db, "Mage", card_class_filter="MAGE")

    items = presenter.get_zone_items("results")

    assert len(items) == 3  # Fireball, Frostbolt, Arcane Intellect
    assert all(c.card_class == "MAGE" for c in items)


def test_search_within_filtered_category():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db, "Mage", card_class_filter="MAGE")

    presenter.search("fire")

    assert "1 result" in speech.last_speech
    items = presenter.get_zone_items("results")
    assert len(items) == 1
    assert items[0].name == "Fireball"


def test_empty_search_restores_full_category():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db, "Mage", card_class_filter="MAGE")

    presenter.search("fire")
    presenter.search("")  # empty search restores all

    items = presenter.get_zone_items("results")
    assert len(items) == 3


def test_announce_entry_speaks_category_and_first_card():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db, "Mage", card_class_filter="MAGE")

    presenter.announce_entry()

    assert "Mage" in speech.last_speech
    assert "Arcane Intellect" in speech.last_speech
    assert "1 of 3" in speech.last_speech


def test_announce_entry_empty_category():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(
        speech, card_db, "Paladin", card_class_filter="PALADIN"
    )

    presenter.announce_entry()

    assert "Paladin: no cards" in speech.last_speech


def test_open_search_calls_callback_and_searches():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.set_on_request_search(lambda: "fire")
    presenter.open_search()

    assert "1 result" in speech.last_speech


def test_open_search_none_does_not_search():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.set_on_request_search(lambda: None)
    presenter.open_search()

    # No search performed, so no speech about results
    assert len(speech.spoken) == 0


# --- Class cycle (Tab / Shift+Tab) ---------------------------------------


def test_cycle_class_advances_from_all_cards_to_demon_hunter():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.cycle_class(1)

    items = presenter.get_zone_items("results")
    # CATEGORY_TO_FILTER order: All Cards -> Demon Hunter -> ...
    # ALL_CARDS has no DEMONHUNTER cards, so results are empty.
    assert items == []


def test_cycle_class_wraps_after_last_entry():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(
        speech, card_db, "Warrior", card_class_filter="WARRIOR"
    )

    presenter.cycle_class(1)

    # Wraps back to All Cards -- full collectible list.
    items = presenter.get_zone_items("results")
    assert len(items) == len(ALL_CARDS)


def test_cycle_class_backward_from_all_cards_wraps_to_warrior():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))
    presenter.cycle_class(-1)

    # Should be on Warrior (last entry in CATEGORY_TO_FILTER).
    assert statuses and "Warrior" in statuses[-1]


def test_cycle_class_resets_cursor_to_first_card():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.move_in_zone(2)  # advance cursor away from 0
    assert presenter._zone_cursors["results"] == 2

    # Cycle to Mage (5 steps from All Cards).
    for _ in range(5):
        presenter.cycle_class(1)

    assert presenter._zone_cursors["results"] == 0


def test_cycle_class_announces_label_and_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))

    # Cycle to Mage (5 steps from All Cards).
    for _ in range(5):
        presenter.cycle_class(1)

    assert statuses[-1] == "Mage, 3 cards"


# --- Mana filter (0-9) ---------------------------------------------------


def test_mana_filter_narrows_results_to_cost():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.apply_mana_filter(3)

    items = presenter.get_zone_items("results")
    names = sorted(c.name for c in items)
    # ARCANE (cost 3) and WOLFRIDER (cost 3).
    assert names == ["Arcane Intellect", "Wolfrider"]


def test_repeat_mana_digit_clears_filter():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.apply_mana_filter(3)
    presenter.apply_mana_filter(3)

    items = presenter.get_zone_items("results")
    assert len(items) == len(ALL_CARDS)


def test_different_mana_digit_replaces_filter():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.apply_mana_filter(3)
    presenter.apply_mana_filter(4)

    items = presenter.get_zone_items("results")
    names = [c.name for c in items]
    # Only FIREBALL (cost 4) matches; not Arcane/Wolfrider (cost 3).
    assert names == ["Fireball"]


def test_mana_nine_matches_nine_or_greater():
    big1 = make_card(name="Big Spell", cost=9, text="Boom.")
    big2 = make_card(name="Bigger Spell", cost=12, text="Bigger boom.")
    cards = ALL_CARDS + [big1, big2]
    card_db = make_card_db(cards)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.apply_mana_filter(9)

    items = presenter.get_zone_items("results")
    names = sorted(c.name for c in items)
    assert names == ["Big Spell", "Bigger Spell"]


def test_mana_zero_matches_cost_zero():
    coin = make_card(name="The Coin", cost=0, text="Gain 1 Mana Crystal this turn.")
    cards = ALL_CARDS + [coin]
    card_db = make_card_db(cards)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.apply_mana_filter(0)

    items = presenter.get_zone_items("results")
    names = [c.name for c in items]
    assert names == ["The Coin"]


def test_mana_filter_announces_active_filter():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))
    presenter.apply_mana_filter(3)

    # "All Cards, 3 mana, 2 cards" -- includes the active mana label.
    assert statuses == ["All Cards, 3 mana, 2 cards"]


def test_mana_filter_nine_announces_plus():
    big = make_card(name="Big Spell", cost=10)
    card_db = make_card_db(ALL_CARDS + [big])
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))
    presenter.apply_mana_filter(9)

    assert statuses == ["All Cards, 9+ mana, 1 card"]


def test_mana_filter_cleared_announces_class_only():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    statuses: list[str] = []
    presenter.set_on_status_changed(lambda text: statuses.append(text))
    presenter.apply_mana_filter(3)
    presenter.apply_mana_filter(3)  # toggle off

    # After clear: class label and full count, no mana fragment.
    assert statuses[-1] == f"All Cards, {len(ALL_CARDS)} cards"


# --- Paging (Page Down / Page Up) ---------------------------------------


def _make_many_cards(count: int) -> list[Card]:
    return [make_card(name=f"Card {i:02d}", cost=1) for i in range(count)]


def test_page_advance_moves_cursor_by_chunk():
    cards = _make_many_cards(25)
    card_db = make_card_db(cards)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.page(1)

    assert presenter._zone_cursors["results"] == 10


def test_page_advance_clamps_at_last():
    cards = _make_many_cards(25)
    card_db = make_card_db(cards)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.page(1)
    presenter.page(1)
    presenter.page(1)  # would go past end

    assert presenter._zone_cursors["results"] == 24


def test_page_retreat_moves_back_by_chunk():
    cards = _make_many_cards(25)
    card_db = make_card_db(cards)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.jump_to_last()
    cursor_before = presenter._zone_cursors["results"]
    presenter.page(-1)

    assert presenter._zone_cursors["results"] == cursor_before - 10


def test_page_retreat_clamps_at_first():
    cards = _make_many_cards(25)
    card_db = make_card_db(cards)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.page(-1)  # would go below 0

    assert presenter._zone_cursors["results"] == 0


def test_mana_filter_persists_across_class_switch():
    # Two MAGE cards with cost 4 (FIREBALL is one). Add a second cost-4 card
    # on a different class so cycling away leaves matching cards in the filter.
    extra_mage = make_card(
        name="Polymorph", cost=4, text="Transform.", card_class="MAGE"
    )
    paladin4 = make_card(
        name="Truesilver Champion",
        cost=4,
        attack=4,
        health=2,
        text="Heal.",
        card_class="PALADIN",
        card_type="WEAPON",
    )
    cards = ALL_CARDS + [extra_mage, paladin4]
    card_db = make_card_db(cards)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(
        speech, card_db, "Mage", card_class_filter="MAGE"
    )

    presenter.apply_mana_filter(4)
    items_before = sorted(c.name for c in presenter.get_zone_items("results"))
    assert items_before == ["Fireball", "Polymorph"]

    # Cycle from Mage -> Neutral (one step forward).
    presenter.cycle_class(1)
    items_neutral = [c.name for c in presenter.get_zone_items("results")]
    # No NEUTRAL cards at cost 4 in our fixture -- still mana-filtered.
    assert items_neutral == []

    # Cycle to Paladin (one more step past Neutral).
    presenter.cycle_class(1)
    items_paladin = [c.name for c in presenter.get_zone_items("results")]
    # Mana filter persisted: Paladin + cost 4 == Truesilver only.
    assert items_paladin == ["Truesilver Champion"]
