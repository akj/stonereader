"""Tests for ReplaysPresenter — newest-first replay history screen (Slice #14).

Run against MockSpeechService + a REAL ReplayStore over tmp_path seeded with
several saved replays. Never instantiates the wx view (headless).
"""

from __future__ import annotations

from pathlib import Path

from stonereader.db import get_connection, init_db
from stonereader.presenters.replays import ReplaysPresenter
from stonereader.services._replay_store import ReplayMeta, ReplayStore
from tests.conftest import MockSpeechService


def _make_store(tmp_path: Path) -> ReplayStore:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    return ReplayStore(conn, tmp_path / "replays")


def _seed(store: ReplayStore) -> None:
    """Seed 3 replays with distinct played_at / classes / results."""
    store.save_xml(
        "<replay>oldest</replay>",
        source="test",
        friendly_class="HUNTER",
        opponent_class="PRIEST",
        result="LOST",
        turns=8,
        played_at="2026-06-18T10:00:00",
    )
    store.save_xml(
        "<replay>middle</replay>",
        source="test",
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="WON",
        turns=12,
        played_at="2026-06-19T14:30:00",
    )
    store.save_xml(
        "<replay>newest</replay>",
        source="test",
        friendly_class="DRUID",
        opponent_class="ROGUE",
        result="WON",
        turns=15,
        played_at="2026-06-20T09:15:00",
    )


def test_lists_newest_played_at_first(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    presenter = ReplaysPresenter(MockSpeechService(), store)

    items = presenter.get_zone_items("replays")

    assert [m.played_at[:10] for m in items] == [
        "2026-06-20",
        "2026-06-19",
        "2026-06-18",
    ]


def test_row_announces_matchup_result_turns_date(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    key_map = presenter.get_key_map()
    key_map["right"]()  # move to second row (newest is index 0)
    text = speech.last_speech

    # Second-newest row: Mage vs Warrior, Won, 12 turns, 2026-06-19.
    assert "Mage vs Warrior" in text
    assert "Won" in text
    assert "12 turns" in text
    assert "2026-06-19" in text
    assert "2 of 3" in text


def test_first_row_title_cases_class_and_result(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    presenter.announce_entry()
    key_map = presenter.get_key_map()
    key_map["home"]()
    text = speech.last_speech

    # Newest row: Druid vs Rogue, Won, 15 turns, 2026-06-20.
    assert "Druid vs Rogue" in text
    assert "WON" not in text
    assert "Won" in text
    assert "15 turns" in text
    assert "2026-06-20" in text
    assert "1 of 3" in text


def test_open_current_invokes_callback_with_selected_meta(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    presenter = ReplaysPresenter(MockSpeechService(), store)

    opened: list[ReplayMeta] = []
    presenter.set_on_open(opened.append)

    key_map = presenter.get_key_map()
    key_map["right"]()  # select index 1 (the Mage replay)
    key_map["enter"]()

    assert len(opened) == 1
    assert opened[0].friendly_class == "MAGE"
    assert opened[0].opponent_class == "WARRIOR"


def test_open_current_no_op_when_empty(tmp_path) -> None:
    store = _make_store(tmp_path)
    presenter = ReplaysPresenter(MockSpeechService(), store)

    opened: list[ReplayMeta] = []
    presenter.set_on_open(opened.append)

    presenter.open_current()

    assert opened == []


def test_first_delete_requests_confirmation_without_removing_replay(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    key_map = presenter.get_key_map()
    key_map["delete"]()

    assert len(store.all_replays()) == 3
    assert speech.last_speech == (
        "Press Delete again to delete "
        "Druid vs Rogue, Won, 15 turns, 2026-06-20"
    )


def test_second_delete_removes_replay_and_reannounces(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    key_map = presenter.get_key_map()
    key_map["delete"]()
    key_map["delete"]()

    # Store row count drops.
    assert len(store.all_replays()) == 2
    # Presenter zone reflects deletion.
    items = presenter.get_zone_items("replays")
    assert len(items) == 2
    # Deleted one (Druid/Rogue, newest) is gone.
    assert all(m.friendly_class != "DRUID" for m in items)
    # Re-announces with the new count.
    assert "2" in speech.last_speech


def test_delete_to_empty_announces_no_replays(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.save_xml(
        "<replay>only</replay>",
        source="test",
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="WON",
        turns=10,
        played_at="2026-06-20T09:00:00",
    )
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    key_map = presenter.get_key_map()
    key_map["delete"]()
    key_map["delete"]()

    assert len(store.all_replays()) == 0
    assert presenter.get_zone_items("replays") == []
    assert "No replays" in speech.last_speech


def test_move_between_delete_presses_requires_fresh_confirmation(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    key_map = presenter.get_key_map()
    key_map["delete"]()  # arm newest row
    key_map["right"]()  # any other action disarms
    key_map["delete"]()  # arm second row instead of deleting it

    assert len(store.all_replays()) == 3
    assert speech.last_speech == (
        "Press Delete again to delete "
        "Mage vs Warrior, Won, 12 turns, 2026-06-19"
    )


def test_empty_state_announces_no_replays(tmp_path) -> None:
    store = _make_store(tmp_path)
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    presenter.announce_entry()

    assert "No replays" in speech.last_speech


def test_announce_entry_includes_count(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    speech = MockSpeechService()
    presenter = ReplaysPresenter(speech, store)

    presenter.announce_entry()

    assert "3" in speech.last_speech


def test_cursor_move_notifies_view(tmp_path) -> None:
    """left/right/home/end must fire on_changed so the view's selected row
    tracks the presenter cursor (not just refresh/delete)."""
    store = _make_store(tmp_path)
    _seed(store)  # 3 replays, cursor starts at 0
    presenter = ReplaysPresenter(MockSpeechService(), store)

    seen: list[int] = []
    presenter.set_on_changed(lambda: seen.append(presenter.cursor_for_zone("replays")))

    key_map = presenter.get_key_map()
    key_map["right"]()  # -> 1
    key_map["end"]()  # -> 2 (last)
    key_map["left"]()  # -> 1
    key_map["home"]()  # -> 0

    # Every cursor move notified the view with the new cursor position.
    assert seen == [1, 2, 1, 0]


def test_refresh_rereads_store(tmp_path) -> None:
    store = _make_store(tmp_path)
    _seed(store)
    presenter = ReplaysPresenter(MockSpeechService(), store)

    assert len(presenter.get_zone_items("replays")) == 3

    # Delete directly via store, then refresh.
    newest = store.all_replays()[0]
    store.delete(newest.id)
    presenter.refresh()

    assert len(presenter.get_zone_items("replays")) == 2
