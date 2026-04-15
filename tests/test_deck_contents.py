"""Tests for DeckContentsPresenter."""

from __future__ import annotations

from stonereader.models.card import Card
from stonereader.models.deck import Deck
from tests.conftest import MockSpeechService
from stonereader.presenters.deck_contents import DeckContentsPresenter

_next_dbf_id = 9000


def _make_card(
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


RENO = _make_card(
    name="Reno Jackson",
    cost=6,
    health=6,
    attack=4,
    text="Battlecry: If your deck has no duplicates, fully heal your hero.",
)
FIREBALL = _make_card(
    name="Fireball", cost=4, text="Deal 6 damage.", card_class="MAGE"
)
LOOT_HOARDER = _make_card(
    name="Loot Hoarder",
    cost=2,
    attack=2,
    health=1,
    text="Deathrattle: Draw a card.",
)

TEST_DECK = Deck(
    name="Reno Mage",
    format="Standard",
    cards=((RENO, 1), (FIREBALL, 2), (LOOT_HOARDER, 2)),
    hero_class="MAGE",
    deckstring="AAECAf0EAA==",
)


def test_initial_zone_is_cards():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    assert presenter._current_zone == "cards"


def test_zone_items_returns_card_tuples():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    items = presenter.get_zone_items("cards")
    assert len(items) == 3
    assert items[0] == (RENO, 1)


def test_move_right_announces_card_with_count():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    presenter.move_in_zone(1)
    assert "Fireball x2" in speech.last_speech
    assert "2 of 3" in speech.last_speech


def test_move_left_at_start_stays_at_first():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    presenter.move_in_zone(-1)
    assert "Reno Jackson x1" in speech.last_speech
    assert "1 of 3" in speech.last_speech


def test_detail_down_reads_first_detail_line():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    key_map = presenter.get_key_map()
    key_map["down"]()
    # First detail line after name is typically the cost line
    assert len(speech.spoken) > 0


def test_announce_deck_header():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    presenter.announce_deck_header()
    assert "Reno Mage" in speech.last_speech
    assert "5 cards" in speech.last_speech
    assert "MAGE" in speech.last_speech
    assert "Standard" in speech.last_speech


def test_key_map_has_navigation_keys():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    key_map = presenter.get_key_map()
    assert "left" in key_map
    assert "right" in key_map
    assert "down" in key_map
    assert "up" in key_map
    assert "home" in key_map
    assert "end" in key_map


def test_key_map_does_not_have_escape():
    """Escape/back is handled by NavigationController, not this presenter."""
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    key_map = presenter.get_key_map()
    assert "escape" not in key_map
    assert "back" not in key_map


def test_view_callback_fires_on_navigation():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    received = []
    presenter.set_on_state_changed(
        lambda cards, cursor: received.append((len(cards), cursor))
    )
    presenter.move_in_zone(1)
    assert received == [(3, 1)]


def test_home_jumps_to_first():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    presenter.move_in_zone(1)
    presenter.jump_to_first()
    assert "Reno Jackson x1" in speech.last_speech
    assert "1 of 3" in speech.last_speech


def test_end_jumps_to_last():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    presenter.jump_to_last()
    assert "Loot Hoarder x2" in speech.last_speech
    assert "3 of 3" in speech.last_speech


def test_view_callback_fires_on_jump_to_first():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    presenter.move_in_zone(1)  # Move to index 1
    received = []
    presenter.set_on_state_changed(
        lambda cards, cursor: received.append((len(cards), cursor))
    )
    presenter.jump_to_first()
    assert received == [(3, 0)]


def test_view_callback_fires_on_jump_to_last():
    speech = MockSpeechService()
    presenter = DeckContentsPresenter(speech, TEST_DECK)
    received = []
    presenter.set_on_state_changed(
        lambda cards, cursor: received.append((len(cards), cursor))
    )
    presenter.jump_to_last()
    assert received == [(3, 2)]
