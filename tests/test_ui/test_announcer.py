from __future__ import annotations

import pytest

from stonereader.ui.announcer import SLOT_NOOP_PHRASES, Announcer
from stonereader.ui.registry import Slot

from tests.support import FakeSpeech


def test_every_template_and_lane() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.context_entry("Cards", "Fireball", 1, 12)
    announcer.context_entry_menu("Home", "Cards")
    announcer.context_empty("Replays")
    announcer.moved("Fireball")
    announcer.boundary("Fireball")
    announcer.confirmation("Fireball copied")
    announcer.clipboard_deck_offer()
    announcer.query("Your deck", "23 cards")
    announcer.noop("No search on this screen")
    announcer.slot_noop(Slot.LISTEN)
    announcer.empty_zone("Opponent hand")
    announcer.already_home("Home")
    announcer.game_logging_enabled()
    announcer.hotkeys_unavailable(["Ctrl+Shift+H", "Ctrl+Shift+C"])
    announcer.narrate("Opponent played Fireball")
    announcer.context_entry("Cards", "Frostbolt", 2, 12, continues=True)
    announcer.context_empty("Cards", continues=True)
    announcer.context_entry_menu("Home", "Cards", continues=True)

    assert speech.calls == [
        ("Cards, Fireball, 1 of 12", True),
        ("Home, Cards", True),
        ("Replays: empty", True),
        ("Fireball", True),
        ("Fireball", True),
        ("Fireball copied", True),
        ("Deck code on clipboard — press Control Enter to import", True),
        ("Your deck, 23 cards", True),
        ("No search on this screen", True),
        ("No card focused", True),
        ("No Opponent hand on this screen", True),
        ("Home — already at the top", True),
        ("Hearthstone logging enabled", True),
        ("Could not register hotkeys: Ctrl+Shift+H, Ctrl+Shift+C.", True),
        ("Opponent played Fireball", False),
        ("Cards, Frostbolt, 2 of 12", False),
        ("Cards: empty", False),
        ("Home, Cards", False),
    ]


@pytest.mark.parametrize("slot", list(Slot))
def test_every_slot_has_a_default_noop_phrase(slot: Slot) -> None:
    assert SLOT_NOOP_PHRASES[slot]


def test_narration_queues_in_order_among_itself() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.narrate("Your turn")
    announcer.narrate("Opponent played Fireball")
    announcer.narrate("Your minion died")

    # Lane 2 only ever queues, so it can never cut Lane 1 or reorder itself.
    assert speech.calls == [
        ("Your turn", False),
        ("Opponent played Fireball", False),
        ("Your minion died", False),
    ]
    assert speech.silences == 0


def test_lane_one_utterance_drops_the_pending_narration_queue() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.narrate("Your turn")
    announcer.narrate("Opponent played Fireball")
    announcer.moved("Frostbolt")

    # The interrupting Lane-1 utterance is itself the drop: it cuts what is
    # speaking and discards everything queued behind it.
    assert speech.calls[-1] == ("Frostbolt", True)
    announcer.drop_narration()
    assert speech.silences == 0


def test_silent_lane_one_keypress_drops_narration_once() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.narrate("Your turn")
    announcer.drop_narration()
    announcer.drop_narration()

    assert speech.silences == 1
    assert speech.calls == [("Your turn", False)]


def test_drop_is_a_noop_with_nothing_narrating() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.drop_narration()
    announcer.moved("Fireball")
    announcer.drop_narration()

    assert speech.silences == 0


def test_multi_line_read_stays_on_lane_one() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.narrate("Your turn")
    announcer.read_lines(["Fireball", "4 mana", "Deals 6 damage"])

    # The first line interrupts (dropping narration with it); the rest follow
    # it on Lane 1 rather than cutting each other.
    assert speech.calls[1:] == [
        ("Fireball", True),
        ("4 mana", False),
        ("Deals 6 damage", False),
    ]
    announcer.drop_narration()
    assert speech.silences == 0


def test_narration_after_user_speech_starts_a_fresh_queue() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.narrate("Your turn")
    announcer.moved("Frostbolt")
    announcer.narrate("Opponent played Fireball")
    announcer.drop_narration()

    assert speech.silences == 1


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((2, 0, 0), "2 imported"),
        ((0, 2, 0), "2 already in Replays"),
        ((0, 0, 2), "2 failed"),
        ((1, 1, 1), "1 imported, 1 already in Replays, 1 failed"),
        ((0, 0, 0), "Nothing imported"),
    ],
)
def test_import_replays_result_speaks_only_nonzero_parts(counts, expected) -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.import_replays_result(*counts)

    assert speech.calls == [(expected, True)]
