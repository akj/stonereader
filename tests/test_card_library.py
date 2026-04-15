"""Tests for CardLibraryPresenter -- category menu navigation."""

from __future__ import annotations

from tests.conftest import MockSpeechService
from stonereader.presenters.card_library import CATEGORY_ITEMS, CardLibraryPresenter


def test_category_menu_has_all_items():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    items = presenter.get_zone_items("menu")

    assert len(items) == len(CATEGORY_ITEMS)
    assert items[0] == "All Cards"


def test_arrow_down_navigates_categories():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    key_map = presenter.get_key_map()
    key_map["down"]()

    assert "Demon Hunter" in speech.last_speech
    assert "2 of" in speech.last_speech


def test_arrow_up_at_start_stays_at_first():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    key_map = presenter.get_key_map()
    key_map["up"]()

    assert "All Cards" in speech.last_speech
    assert "1 of" in speech.last_speech


def test_enter_invokes_select_callback():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    selected: list[str] = []
    presenter.set_on_select(lambda name: selected.append(name))

    key_map = presenter.get_key_map()
    key_map["enter"]()

    assert selected == ["All Cards"]


def test_navigate_to_second_then_enter():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    selected: list[str] = []
    presenter.set_on_select(lambda name: selected.append(name))

    key_map = presenter.get_key_map()
    key_map["down"]()
    key_map["enter"]()

    assert selected == ["Demon Hunter"]


def test_home_jumps_to_first():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    key_map = presenter.get_key_map()
    key_map["down"]()
    key_map["down"]()
    key_map["home"]()

    assert "All Cards" in speech.last_speech
    assert "1 of" in speech.last_speech


def test_end_jumps_to_last():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    key_map = presenter.get_key_map()
    key_map["end"]()

    assert "Warrior" in speech.last_speech
    assert f"{len(CATEGORY_ITEMS)} of {len(CATEGORY_ITEMS)}" in speech.last_speech


def test_announce_entry():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    presenter.announce_entry()

    assert "Card Library" in speech.last_speech
    assert "All Cards" in speech.last_speech
    assert "1 of" in speech.last_speech


def test_left_right_also_navigate():
    speech = MockSpeechService()
    presenter = CardLibraryPresenter(speech)

    key_map = presenter.get_key_map()
    key_map["right"]()

    assert "Demon Hunter" in speech.last_speech

    key_map["left"]()

    assert "All Cards" in speech.last_speech
