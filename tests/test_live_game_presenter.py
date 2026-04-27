"""Stub tests for Phase 3 LiveGamePresenter (Wave 0 scaffolding).

Each stub names a behavior locked by 03-VALIDATION.md per-requirement test
map, plus additional behaviors required by 03-REVIEWS.md (LIVE-03 cards-
drawn zone, drawn-turn-unknown speech wording, opponent-hand-count baseline).
Production code lands in plans 03-05 and 03-06; tests flip from xfail to
passing as those plans complete.
"""

from __future__ import annotations

import pytest

from tests.conftest import MockGameTracker, MockSpeechService  # noqa: F401

pytestmark = pytest.mark.xfail(
    strict=False,
    reason="Wave 0 stub - implementation lands in plans 03-05 / 03-06",
)


def test_lifecycle_silence() -> None:
    """LIVE-01 + D-09: Panel state resets on GameStarted, preserves on
    GameEnded; lifecycle events never call speech.
    Implementation target: plan 03-05 (LiveGamePresenter).
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_remaining_deck_speech_format() -> None:
    """LIVE-02 (D-13): Remaining-deck zone reads "<count>x <name>" per row.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_remaining_deck_sort_order() -> None:
    """LIVE-02 (D-13/D-20): Remaining deck list is sorted by cost ascending,
    then name ascending; ties stable.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_drawn_to_zero_visible() -> None:
    """LIVE-02 (D-13 drawn-to-zero rule): Cards drawn down to count==0 stay
    visible in the remaining-deck zone (struck-through / "(drawn)" marker)
    rather than disappearing.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_cards_drawn_zone() -> None:
    """LIVE-03 (NEW per 03-REVIEWS.md HIGH #1): Fourth zone listing cards
    drawn this game in chronological order with turn drawn.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_opponent_hand_speech_format() -> None:
    """LIVE-04 lineage variant (D-04/D-14): Opponent-hand zone reads
    "<lineage>, drawn turn <N>" for cards with creation lineage.
    NOTE: NO LONGER claimed for LIVE-03 — that is the cards_drawn zone.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_drawn_turn_unknown_speech() -> None:
    """LIVE-04 (NEW per 03-REVIEWS.md MEDIUM #5): When `drawn_turn == -1`,
    speech says "drawn turn unknown" not "drawn turn -1".
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_opponent_played_speech_format() -> None:
    """LIVE-04 (D-15 opponent_played): Opponent-played zone reads each card
    in play order with turn played.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_opponent_hand_count() -> None:
    """LIVE-05 (panel zone count): Opponent hand zone reports the correct
    count of cards held even when individual cards are unknown.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_announce_opponent_hand_count() -> None:
    """LIVE-05 (NEW per 03-REVIEWS.md HIGH #3): Public presenter method
    that the speak-only hotkey calls instead of reading `_current_state`.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_announce_deck_counts() -> None:
    """LIVE-06 (D-16): Public method announces remaining-deck count for
    both players via the speak-only hotkey.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_mana_query() -> None:
    """LIVE-07 (panel-only per Open Q2): Mana totals available via panel
    zone navigation (NO global hotkey for mana per Open Q2).
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_auto_deck_detection() -> None:
    """LIVE-08 (D-11 0/1/2+ matches): Auto-detect saved deck from initial
    deck list — speak the matched deck name when exactly one matches; speak
    "no saved deck matched" on 0; speak "multiple decks matched" on 2+.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_detection_resets_per_game() -> None:
    """LIVE-08 (Pitfall 6): Auto-deck detection resets between games — a
    second game starts with no detected deck until its own initial deck
    list is observed.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_silent_during_event() -> None:
    """D-07: `_on_game_event` callback never calls speech — engine events
    update internal state silently; speech happens only in response to
    user-initiated key/hotkey calls.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_cursor_preserves_across_render() -> None:
    """D-07 + Pitfall 3: Zone cursors persist when state is replaced by a
    new frozen snapshot — the cursor index stays valid (clamped to new
    length) across renders.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_no_game_baseline() -> None:
    """D-08: Before any game starts, hotkey-driven announcements speak
    "No game in progress" rather than crashing or staying silent.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_public_accessors_no_private_access() -> None:
    """D-07/D-08 (NEW per 03-REVIEWS.md HIGH #3): Public accessors
    `current_title()`, `cursor_for_zone(name)`, `detected_deck_name()`,
    `current_state_snapshot()` exist and return correct values — view
    layer never reads `_current_state` directly.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")


def test_number_key_zone_switching() -> None:
    """D-07 (NEW per 03-CHECKER blocker #1): Number keys 1/2/3/4 in
    `get_key_map()` switch among the four zones (remaining_deck /
    opponent_played / opponent_hand / cards_drawn); total key count is 10.
    Implementation target: plan 03-05.
    """
    pytest.xfail("not implemented yet — plan 03-05")
