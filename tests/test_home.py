"""Tests for HomePresenter."""

from __future__ import annotations

from tests.conftest import MockSpeechService
from stonereader.presenters.home import HomePresenter


def test_initial_zone_is_menu():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    assert presenter._current_zone == "menu"


def test_menu_items_are_feature_names():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    items = presenter.get_zone_items("menu")
    assert list(items) == [
        "Card Library",
        "Deck Manager",
        "Import Deck",
        "Live Game",
    ]


def test_menu_items_includes_live_game() -> None:
    """Regression-lock the new MENU_ITEMS shape (plan 03-06)."""
    from stonereader.presenters.home import MENU_ITEMS

    assert MENU_ITEMS == [
        "Card Library",
        "Deck Manager",
        "Import Deck",
        "Live Game",
    ]


def test_move_down_announces_next_item():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    presenter.move_in_zone(1)
    assert "Deck Manager" in speech.last_speech
    assert "2 of 4" in speech.last_speech


def test_move_up_at_start_stays_at_first():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    presenter.move_in_zone(-1)
    assert "Card Library" in speech.last_speech
    assert "1 of 4" in speech.last_speech


def test_select_current_fires_callback():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    selected = []
    presenter.set_on_select(lambda name: selected.append(name))
    presenter.select_current()
    assert selected == ["Card Library"]


def test_select_after_move_fires_correct_item():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    selected = []
    presenter.set_on_select(lambda name: selected.append(name))
    presenter.move_in_zone(1)  # Move to "Deck Manager"
    presenter.select_current()
    assert selected == ["Deck Manager"]


def test_key_map_has_navigation_and_enter():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    key_map = presenter.get_key_map()
    assert "up" in key_map
    assert "down" in key_map
    assert "left" in key_map
    assert "right" in key_map
    assert "enter" in key_map
    assert "home" in key_map
    assert "end" in key_map


def test_home_jumps_to_first():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    presenter.move_in_zone(1)  # Move to index 1
    presenter.jump_to_first()
    assert "Card Library" in speech.last_speech
    assert "1 of 4" in speech.last_speech


def test_end_jumps_to_last():
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    presenter.jump_to_last()
    assert "Live Game" in speech.last_speech
    assert "4 of 4" in speech.last_speech


def test_key_map_does_not_have_feature_switching_hotkeys():
    """Per D-03: no feature-switching hotkeys. Users navigate through home screen only."""
    speech = MockSpeechService()
    presenter = HomePresenter(speech)
    key_map = presenter.get_key_map()
    assert "tab" not in key_map
    assert "f1" not in key_map
    assert "f2" not in key_map
