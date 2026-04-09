from typing import Any, Sequence

from tests.conftest import MockSpeechService
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin


class StubPresenter(ZoneNavigationMixin, BasePresenter):
    """Minimal presenter for testing zone navigation."""

    def __init__(self, speech: MockSpeechService) -> None:
        super().__init__(speech)
        self._items: dict[str, list[Any]] = {
            "zone_a": ["Alpha", "Bravo", "Charlie"],
            "zone_b": ["Delta", "Echo"],
        }
        self._init_navigation(["zone_a", "zone_b"])

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        return self._items.get(zone_name, [])


def test_initial_zone_is_first():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    assert p._current_zone == "zone_a"


def test_navigate_to_zone_announces_zone_and_item():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_b", "Zone B")
    assert "Zone B" in speech.last_speech
    assert "Delta" in speech.last_speech


def test_navigate_to_zone_empty():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p._items["zone_b"] = []
    p.navigate_to_zone("zone_b", "Zone B")
    assert "empty" in speech.last_speech


def test_move_right_advances_cursor():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(1)
    assert "Bravo" in speech.last_speech
    assert "2 of 3" in speech.last_speech


def test_move_left_does_not_go_below_zero():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(-1)
    assert "Alpha" in speech.last_speech
    assert "1 of 3" in speech.last_speech


def test_move_right_does_not_go_past_end():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(1)
    p.move_in_zone(1)
    p.move_in_zone(1)  # past end
    assert "Charlie" in speech.last_speech
    assert "3 of 3" in speech.last_speech


def test_zone_cursor_persists_across_switches():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(1)  # cursor on Bravo (index 1)
    p.navigate_to_zone("zone_b", "Zone B")
    p.navigate_to_zone("zone_a", "Zone A")
    assert "Bravo" in speech.last_speech


def test_detail_lines_navigates_card_details():
    from stonereader.models import Card

    speech = MockSpeechService()
    p = StubPresenter(speech)
    card = Card(
        id="TEST_001",
        dbf_id=1,
        name="Fireball",
        cost=4,
        attack=None,
        health=None,
        text="Deal 6 damage.",
        rarity="COMMON",
        card_class="CardClass.MAGE",
        card_type="SpellType.SPELL",
    )
    p._items["zone_a"] = [card]
    p._init_navigation(["zone_a"])
    p.navigate_to_zone("zone_a", "Zone A")
    # navigate_to_zone announced the name; first Down skips to cost
    p.read_detail_lines(card, direction=1)
    assert "4 mana" in speech.last_speech
    # Second Down reads card text
    p.read_detail_lines(card, direction=1)
    assert "Deal 6 damage." in speech.last_speech


def test_diminishing_orienting_messages():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.handle_inapplicable_zone("b", "Full help message", "Short help")
    assert speech.last_speech == "Full help message"
    p.handle_inapplicable_zone("b", "Full help message", "Short help")
    assert speech.last_speech == "Short help"
    p.handle_inapplicable_zone("b", "Full help message", "Short help")
    # Third press: silent (no new speech)
    assert speech.last_speech == "Short help"


def test_orienting_counts_reset_on_zone_change():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.handle_inapplicable_zone("b", "Full help", "Short")
    p.handle_inapplicable_zone("b", "Full help", "Short")
    # Switch zones resets counts
    p.navigate_to_zone("zone_b", "Zone B")
    p.handle_inapplicable_zone("b", "Full help", "Short")
    assert speech.last_speech == "Full help"


def test_jump_to_position():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.jump_to_position(3)
    assert "Charlie" in speech.last_speech
    assert "3 of 3" in speech.last_speech


def test_jump_to_first_and_last():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.jump_to_last()
    assert "Charlie" in speech.last_speech
    p.jump_to_first()
    assert "Alpha" in speech.last_speech


def test_navigate_singleton_zone():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_singleton_zone("stats", "Statistics", "Win rate: 55%")
    assert "Statistics: Win rate: 55%" in speech.last_speech
