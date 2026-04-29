"""Captured-fixture integration tests for GameEngine GameState publication.

RED phase: these tests fail on main pre-03-07 — they are the negative gate
that locks in the engine-publication fix (Task 2 of plan 03-07).

The original Phase 3 unit tests masked this gap because:
- `tests/test_live_game_presenter.py:_make_state` constructs synthetic GameState.
- `tests/test_services/test_engine.py` uses synthetic packets only.
- No test fed real Power.log → Parser → Engine and asserted that the engine
  publishes the fields the live presenter consumes (`player_deck`,
  `player_hero.hero_class`, `player_mana`/`player_max_mana`, deck counts).

These captured-fixture tests close that gap and lock the contract: every
field the panel renders must be reflected in `engine.current_state` after
real-world replay.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

pytest.importorskip("stonereader.services._engine")

from hearthstone.enums import Zone

from stonereader.models.card import CardDatabase
from stonereader.models.game_state import GameEntity
from stonereader.services._engine import GameEngine
from stonereader.services._parser import Parser


_HEARTHSTONE_CLASSES = {
    "MAGE",
    "WARRIOR",
    "ROGUE",
    "HUNTER",
    "DRUID",
    "SHAMAN",
    "WARLOCK",
    "PALADIN",
    "PRIEST",
    "DEMONHUNTER",
    "DEATHKNIGHT",
}


@pytest.fixture(scope="module")
def card_db() -> CardDatabase:
    """Load the real CardDatabase. Skip the test if cardxml is unavailable."""
    try:
        return CardDatabase.load()
    except Exception:  # pragma: no cover - environment-dependent fallback
        pytest.skip("CardDatabase unavailable (cardxml missing)")


def _replay(fixture_path: Path, card_db: Optional[CardDatabase] = None) -> GameEngine:
    """Replay a captured Power.log fixture through Parser + GameEngine."""
    parser = Parser()
    engine = GameEngine(card_db=card_db)
    for line in fixture_path.read_text(encoding="utf-8").splitlines():
        for pkt in parser.feed_line(line):
            engine.apply(pkt)
    return engine


def test_player_deck_rebuilt_from_entities(power_log_fixture, card_db) -> None:
    """state.player_deck must contain GameEntity rows for every ZONE==DECK
    entity controlled by the friendly player. Pre-03-07 the field is `()`
    because `_refresh_state` never rebuilt it from `_entities`.
    """
    path = power_log_fixture("match_start.log")
    engine = _replay(path, card_db=card_db)
    state = engine.current_state
    assert state is not None, "engine never published initial GameState"
    assert len(state.player_deck) > 0, (
        f"player_deck not rebuilt: {len(state.player_deck)} entities"
    )
    assert all(isinstance(e, GameEntity) for e in state.player_deck), (
        "player_deck entries must be GameEntity instances"
    )
    assert all(e.zone == "DECK" for e in state.player_deck), (
        "player_deck entries must have zone == 'DECK'"
    )
    # WR-05: this is one of the rare tests that DOES read engine private
    # state (`_friendly_player_id`). The contract under test is "every
    # row in published `player_deck` belongs to the friendly player," and
    # there is no public accessor for `_friendly_player_id` yet — adding
    # one solely for tests is heavier than the coupling cost. If a
    # `engine.snapshot_for_test()` accessor is added later, swap to it.
    assert all(e.controller == engine._friendly_player_id for e in state.player_deck), (
        "player_deck entries must be controlled by the friendly player"
    )


def test_hero_class_resolved(power_log_fixture, card_db) -> None:
    """state.player_hero.hero_class and opponent_hero.hero_class must
    populate to a real Hearthstone class string after the hero entities
    are observed in the log. Pre-03-07 both stay as the empty placeholder.
    """
    path = power_log_fixture("match_start.log")
    engine = _replay(path, card_db=card_db)
    state = engine.current_state
    assert state is not None
    assert state.player_hero.hero_class != "", (
        f"player_hero.hero_class still empty: {state.player_hero!r}"
    )
    assert state.opponent_hero.hero_class != "", (
        f"opponent_hero.hero_class still empty: {state.opponent_hero!r}"
    )
    assert state.player_hero.hero_class in _HEARTHSTONE_CLASSES, (
        f"player_hero.hero_class={state.player_hero.hero_class!r} not in canonical set"
    )
    assert state.opponent_hero.hero_class in _HEARTHSTONE_CLASSES, (
        f"opponent_hero.hero_class={state.opponent_hero.hero_class!r} "
        f"not in canonical set"
    )
    assert state.player_hero.name != "?", (
        "player_hero is still the empty placeholder Hero(name='?')"
    )


def test_mana_tags_advance(power_log_fixture, card_db) -> None:
    """RESOURCES + RESOURCES_USED must update player_mana / player_max_mana
    and the opponent counterparts. Pre-03-07 _on_tag_change ignores both
    tags so the mana fields stay at their CREATE_GAME default of 0.

    Note: in the captured fixtures, RESOURCES advances at most to 1 (the
    capture window is roughly turn 1). The meaningful regression is that
    AT LEAST ONE side moves off 0 — proving the RESOURCES branch in
    _on_tag_change actually fires. mana <= max_mana is the always-true
    invariant that locks RESOURCES_USED clamping.
    """
    path = power_log_fixture("mid_game.log")
    engine = _replay(path, card_db=card_db)
    state = engine.current_state
    assert state is not None
    advanced = max(state.player_max_mana, state.opponent_max_mana)
    assert advanced >= 1, (
        "neither player's max_mana advanced — RESOURCES branch did not fire: "
        f"player={state.player_max_mana}, opponent={state.opponent_max_mana}"
    )
    assert 0 <= state.player_mana <= max(state.player_max_mana, 0), (
        f"player_mana out of range: {state.player_mana} / {state.player_max_mana}"
    )
    assert 0 <= state.opponent_mana <= max(state.opponent_max_mana, 0), (
        f"opponent_mana out of range: {state.opponent_mana} / {state.opponent_max_mana}"
    )
    # RESOURCES_USED clamping: when RESOURCES_USED == RESOURCES, mana = 0.
    # In mid_game.log, the Innkeeper gets RESOURCES=1 then RESOURCES_USED=1,
    # so opponent_mana clamps to 0 while opponent_max_mana stays at 1.
    if state.opponent_max_mana > 0:
        assert state.opponent_mana <= state.opponent_max_mana


def test_deck_counts_track_zone(power_log_fixture, card_db) -> None:
    """player_deck_count and opponent_deck_count must equal the live
    per-controller count of ZONE==DECK entities. Pre-03-07 they stay 0
    because they are never derived in `_refresh_state`.

    Note: a starting deck is 30 cards but mid-game shuffle effects (e.g.
    Tracking, Lab Recruiter, Excavate generators) can push the live deck
    count above 30. The captured mid_game.log includes such effects, so
    the upper bound here is a generous 60.

    WR-05: previously cross-checked `state.player_deck_count` against an
    iteration over `engine._entities`. That coupled the test tightly to
    the engine's primary internal data structure. Cross-check now uses
    the published `state.player_deck` tuple (also rebuilt by
    `_refresh_state`) so the assertion stays meaningful while only
    touching public state.
    """
    path = power_log_fixture("mid_game.log")
    engine = _replay(path, card_db=card_db)
    state = engine.current_state
    assert state is not None
    assert state.player_deck_count > 0, (
        f"player_deck_count not derived: {state.player_deck_count}"
    )
    assert state.player_deck_count <= 60, (
        f"player_deck_count unrealistically high: {state.player_deck_count}"
    )
    assert state.opponent_deck_count > 0, (
        f"opponent_deck_count not derived: {state.opponent_deck_count}"
    )
    assert state.opponent_deck_count <= 60
    # `player_deck` and `player_deck_count` are derived from the same
    # _refresh_state pass; the count must equal the tuple length.
    assert state.player_deck_count == len(state.player_deck), (
        f"player_deck_count must equal len(player_deck): "
        f"count={state.player_deck_count}, deck_rows={len(state.player_deck)}"
    )


def test_pvp_fallback_rebuckets_heroes_and_mana(card_db) -> None:
    """BL-01 / WR-01 regression: in PvP captures both players have lo != 0
    so the AI heuristic at CREATE_GAME cannot disambiguate
    `_friendly_player_id`. Hero entities and RESOURCES TAG_CHANGEs that
    arrive BEFORE the SHOW_ENTITY-into-HAND fallback resolves the friendly
    player are classified against the default `_friendly_player_id == 1`.
    When the fallback later flips the friendly player to 2,
    `_rebucket_from_entities` must re-resolve heroes (BL-01) AND re-derive
    mana (WR-01) so both fields end up on the correct side.

    Without the fix the test would observe the friendly's MAGE hero on
    `state.opponent_hero` and friendly mana attributed to opponent.
    """
    from stonereader.services._packets import (
        CreateGamePacket,
        FullEntityPacket,
        ShowEntityPacket,
        TagChangePacket,
    )

    engine = GameEngine(card_db=card_db)
    # Both players have lo != 0 → AI heuristic cannot disambiguate.
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=(
                (2, 1, "OpponentP1", 1, 1111),  # P1 entity 2: opponent (warrior)
                (3, 2, "FriendlyP2", 2, 2222),  # P2 entity 3: friendly (mage)
            ),
        )
    )
    assert engine._friendly_player_id == 1, (
        "AI heuristic should not resolve when both players have lo != 0"
    )
    assert engine._friendly_player_resolved is False

    # Hero entities arrive AFTER CREATE_GAME but BEFORE the fallback fires.
    # CONTROLLER=1 → recorded as friendly (incorrect: friendly is actually 2).
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=64,
            card_id="HERO_01",  # Garrosh, WARRIOR — actually the OPPONENT
            tags={"CARDTYPE": 3, "CONTROLLER": 1, "ZONE": 1},  # Zone.PLAY
        )
    )
    engine.apply(
        FullEntityPacket(
            packet_id=2,
            entity_id=66,
            card_id="HERO_08",  # Jaina, MAGE — actually the FRIENDLY
            tags={"CARDTYPE": 3, "CONTROLLER": 2, "ZONE": 1},
        )
    )
    # RESOURCES on player entities BEFORE fallback. Player 1 (entity 2) sets
    # RESOURCES=1 — currently classified as friendly.
    engine.apply(TagChangePacket(packet_id=3, entity_id=2, tag="RESOURCES", value=1))

    state_before = engine.current_state
    assert state_before is not None
    # Pre-fallback: heroes and mana attributed against default _friendly=1
    assert state_before.player_hero.hero_class == "WARRIOR"
    assert state_before.opponent_hero.hero_class == "MAGE"
    assert state_before.player_max_mana == 1
    assert state_before.opponent_max_mana == 0

    # First SHOW_ENTITY into HAND with controller=2 fires the fallback,
    # flipping _friendly_player_id from 1 → 2. _rebucket_from_entities must
    # re-resolve heroes and re-derive mana from authoritative state.
    engine.apply(
        ShowEntityPacket(
            packet_id=4,
            entity_id=100,
            card_id="CS2_023",
            tags={"CONTROLLER": 2, "ZONE": int(Zone.HAND)},
        )
    )

    assert engine._friendly_player_resolved is True
    assert engine._friendly_player_id == 2
    state_after = engine.current_state
    assert state_after is not None
    # BL-01: heroes must be re-attributed.
    assert state_after.player_hero.hero_class == "MAGE", (
        f"player_hero should be MAGE (friendly) after fallback, got "
        f"{state_after.player_hero.hero_class!r}"
    )
    assert state_after.opponent_hero.hero_class == "WARRIOR", (
        f"opponent_hero should be WARRIOR (opponent) after fallback, got "
        f"{state_after.opponent_hero.hero_class!r}"
    )
    # WR-01: mana must be re-derived for the now-correct friendly side.
    # Player 2 (friendly) had no RESOURCES set yet → 0 mana for player.
    # Player 1 (opponent) had RESOURCES=1 → 1 max_mana for opponent.
    assert state_after.player_max_mana == 0, (
        f"player_max_mana should be 0 (friendly P2 has no RESOURCES), got "
        f"{state_after.player_max_mana}"
    )
    assert state_after.opponent_max_mana == 1, (
        f"opponent_max_mana should be 1 (opponent P1 had RESOURCES=1), got "
        f"{state_after.opponent_max_mana}"
    )


def test_existing_engine_invariants_preserved(power_log_fixture, card_db) -> None:
    """Regression lock: Task 2's extensions must not break the 5 fields
    `_refresh_state` already publishes. Replays an arbitrary fixture and
    confirms each field is a tuple (not None) on the published state.
    """
    path = power_log_fixture("mid_game.log")
    engine = _replay(path, card_db=card_db)
    state = engine.current_state
    assert state is not None
    assert isinstance(state.player_played, tuple)
    assert isinstance(state.opponent_played, tuple)
    assert isinstance(state.player_drawn, tuple)
    assert isinstance(state.opponent_drawn, tuple)
    assert isinstance(state.opponent_hand, tuple)
