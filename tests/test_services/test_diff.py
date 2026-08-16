"""Pure GameState-pair diff tests (issue #4).

Mirrors the prior art in tests/test_services/test_engine_live_state.py: construct
GameState literals, call diff(), assert on the returned sequence. The diff module
is intentionally engine-free — these tests never instantiate GameEngine, Parser,
or anything that consumes Power.log packets.
"""

from __future__ import annotations

from typing import Optional

from stonereader.models.game_state import (
    AttackInProgress,
    GameEntity,
    GameState,
    Hero,
)
from stonereader.services._diff import diff
from stonereader.services._events import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    CardRemoved,
    CardRevealed,
    DamageDealt,
    GameEnded,
    GameStarted,
    MinionDied,
    MulliganDone,
    SecretPlayed,
    SecretRevealed,
    TurnChanged,
)


_EMPTY_HERO = Hero(id="?", name="?", health=30, armor=0, hero_power="", hero_class="")


def _entity(
    *,
    entity_id: int,
    zone: str,
    card_id: str = "",
    name: str = "",
    controller: int = 1,
    card_type: str = "",
    tags: Optional[dict] = None,
) -> GameEntity:
    return GameEntity(
        entity_id=entity_id,
        card_id=card_id,
        base_card=None,
        name=name,
        cost=0,
        current_attack=0,
        current_health=0,
        card_type=card_type,
        zone=zone,
        zone_position=0,
        controller=controller,
        tags=tags if tags is not None else {},
    )


def _state(**overrides) -> GameState:
    """Helper: GameState with sensible defaults that tests override per-case."""
    base = dict(
        turn=0,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=_EMPTY_HERO,
        opponent_hero=_EMPTY_HERO,
    )
    base.update(overrides)
    return GameState(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------ GameStarted


def test_cold_start_emits_game_started() -> None:
    """prev=None and curr.game_state == "RUNNING" → single GameStarted."""
    curr = _state(
        turn=0,
        game_state="RUNNING",
        game_type="RANKED",
        format_type="STANDARD",
        player_hero=Hero(
            id="HERO_08",
            name="Jaina",
            health=30,
            armor=0,
            hero_power="",
            hero_class="MAGE",
        ),
        opponent_hero=Hero(
            id="HERO_01",
            name="Garrosh",
            health=30,
            armor=0,
            hero_power="",
            hero_class="WARRIOR",
        ),
    )
    events = list(diff(None, curr))
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, GameStarted)
    assert ev.turn == 0
    assert ev.game_type == "RANKED"
    assert ev.format_type == "STANDARD"
    assert ev.player_class == "MAGE"
    assert ev.opponent_class == "WARRIOR"


def test_identical_states_return_empty_sequence() -> None:
    """Two equal GameStates produce no events — diff is the identity on no-op."""
    s = _state(turn=3, active_player_id=2, game_state="RUNNING")
    assert list(diff(s, s)) == []


# ------------------------------------------------------------------ GameEnded


def test_running_to_complete_emits_game_ended() -> None:
    """RUNNING → COMPLETE produces GameEnded carrying the playstate fields from curr."""
    prev = _state(turn=8, game_state="RUNNING")
    curr = _state(
        turn=8,
        game_state="COMPLETE",
        player_playstate="WON",
        opponent_playstate="LOST",
    )
    events = [e for e in diff(prev, curr) if isinstance(e, GameEnded)]
    assert len(events) == 1
    ev = events[0]
    assert ev.turn == 8
    assert ev.player_playstate == "WON"
    assert ev.opponent_playstate == "LOST"


def test_running_to_abandoned_emits_game_ended() -> None:
    """RUNNING → ABANDONED (Hearthstone-process-disappeared) also produces GameEnded."""
    prev = _state(turn=2, game_state="RUNNING")
    curr = _state(turn=2, game_state="ABANDONED")
    events = [e for e in diff(prev, curr) if isinstance(e, GameEnded)]
    assert len(events) == 1


# ------------------------------------------------------------------ TurnChanged


def test_active_player_id_flip_emits_turn_changed() -> None:
    """active_player_id change produces a TurnChanged carrying the new id."""
    prev = _state(turn=4, active_player_id=2)
    curr = _state(turn=5, active_player_id=3)
    events = [e for e in diff(prev, curr) if isinstance(e, TurnChanged)]
    assert len(events) == 1
    assert events[0].active_player_id == 3
    assert events[0].turn == 5


# ------------------------------------------------------------------ MulliganDone


def test_mulligan_complete_flip_emits_mulligan_done() -> None:
    """mulligan_complete False → True produces a MulliganDone."""
    prev = _state(turn=0, mulligan_complete=False)
    curr = _state(turn=0, mulligan_complete=True)
    events = [e for e in diff(prev, curr) if isinstance(e, MulliganDone)]
    assert len(events) == 1
    assert events[0].turn == 0


def test_mulligan_already_complete_no_event() -> None:
    """A state pair where mulligan_complete was already True produces no MulliganDone."""
    s = _state(turn=1, mulligan_complete=True)
    events = [e for e in diff(s, s) if isinstance(e, MulliganDone)]
    assert events == []


# ------------------------------------------------------------------ AttackStarted


def test_attack_in_progress_appears_emits_attack_started() -> None:
    """attack_in_progress None → set produces AttackStarted with the lifted payload."""
    prev = _state(turn=3, attack_in_progress=None)
    aip = AttackInProgress(
        attacker_entity_id=42,
        defender_entity_id=99,
        attacker_controller=2,
    )
    curr = _state(turn=3, attack_in_progress=aip)
    events = [e for e in diff(prev, curr) if isinstance(e, AttackStarted)]
    assert len(events) == 1
    ev = events[0]
    assert ev.attacker_entity_id == 42
    assert ev.defender_entity_id == 99
    assert ev.attacker_controller == 2


# ------------------------------------------------------------------ CardDrawn


def test_entity_entering_hand_emits_card_drawn() -> None:
    """An entity that was outside HAND in prev and inside HAND in curr produces CardDrawn."""
    in_deck = _entity(entity_id=10, zone="DECK", card_id="CS2_023", controller=1)
    in_hand = _entity(entity_id=10, zone="HAND", card_id="CS2_023", controller=1)
    prev = _state(turn=1, player_deck=(in_deck,))
    curr = _state(turn=1, player_hand=(in_hand,))
    events = [e for e in diff(prev, curr) if isinstance(e, CardDrawn)]
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_id == 10
    assert ev.card_id == "CS2_023"
    assert ev.controller == 1


def test_new_entity_appearing_in_hand_emits_card_drawn() -> None:
    """An entity that did not exist in prev but appears in HAND in curr produces CardDrawn
    (e.g. opponent generated card revealed directly into hand)."""
    in_hand = _entity(entity_id=55, zone="HAND", card_id="CS2_023", controller=2)
    prev = _state(turn=2)
    curr = _state(turn=2, opponent_hand=(in_hand,))
    events = [e for e in diff(prev, curr) if isinstance(e, CardDrawn)]
    assert len(events) == 1
    assert events[0].entity_id == 55


# ------------------------------------------------------------------ CardPlayed


def test_entity_entering_play_under_play_block_emits_card_played() -> None:
    """HAND → PLAY while curr.block_stack[-1] == "PLAY" produces CardPlayed."""
    in_hand = _entity(entity_id=20, zone="HAND", card_id="CS2_023", controller=1)
    in_play = _entity(entity_id=20, zone="PLAY", card_id="CS2_023", controller=1)
    prev = _state(turn=4, player_hand=(in_hand,), block_stack=("PLAY",))
    curr = _state(turn=4, player_board=(in_play,), block_stack=("PLAY",))
    events = [e for e in diff(prev, curr) if isinstance(e, CardPlayed)]
    assert len(events) == 1
    assert events[0].entity_id == 20
    assert events[0].controller == 1


def test_entity_entering_play_without_play_block_does_not_emit_card_played() -> None:
    """An entity moving to PLAY while no PLAY block is open is NOT a CardPlayed
    (e.g. an effect summons a minion under a POWER block)."""
    in_hand = _entity(entity_id=21, zone="HAND", card_id="CS2_023", controller=1)
    in_play = _entity(entity_id=21, zone="PLAY", card_id="CS2_023", controller=1)
    prev = _state(turn=4, player_hand=(in_hand,), block_stack=("POWER",))
    curr = _state(turn=4, player_board=(in_play,), block_stack=("POWER",))
    events = [e for e in diff(prev, curr) if isinstance(e, CardPlayed)]
    assert events == []


# ------------------------------------------------------------------ MinionDied


def test_play_to_graveyard_emits_minion_died() -> None:
    """A MINION that goes from zone="PLAY" to zone="GRAVEYARD" produces MinionDied."""
    alive = _entity(
        entity_id=30,
        zone="PLAY",
        card_id="CS2_023",
        name="Bloodfen",
        controller=1,
        card_type="MINION",
    )
    dead = _entity(
        entity_id=30,
        zone="GRAVEYARD",
        card_id="CS2_023",
        name="Bloodfen",
        controller=1,
        card_type="MINION",
    )
    prev = _state(turn=5, player_board=(alive,))
    curr = _state(turn=5, player_board=(dead,))
    events = [e for e in diff(prev, curr) if isinstance(e, MinionDied)]
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_id == 30
    assert ev.name == "Bloodfen"
    assert ev.controller == 1


def test_play_to_graveyard_weapon_emits_card_removed_not_minion_died() -> None:
    """A non-minion (e.g. a destroyed WEAPON) going PLAY → GRAVEYARD is a
    CardRemoved, never a MinionDied — terminal-zone entities are now visited by
    the diff, so the GRAVEYARD branch must be gated by card type."""
    equipped = _entity(
        entity_id=31, zone="PLAY", card_id="CS2_106", controller=1, card_type="WEAPON"
    )
    destroyed = _entity(
        entity_id=31,
        zone="GRAVEYARD",
        card_id="CS2_106",
        controller=1,
        card_type="WEAPON",
    )
    prev = _state(turn=5, player_weapon=equipped)
    curr = _state(turn=5, graveyard=(destroyed,))
    events = diff(prev, curr)
    assert [e for e in events if isinstance(e, MinionDied)] == []
    removed = [e for e in events if isinstance(e, CardRemoved)]
    assert len(removed) == 1
    assert removed[0].entity_id == 31
    assert removed[0].controller == 1


# ------------------------------------------------------------------ CardRemoved


def test_hand_to_graveyard_emits_card_removed() -> None:
    """A non-PLAY entity that transitions to GRAVEYARD/REMOVEDFROMGAME produces CardRemoved
    (e.g. a discard from hand). PLAY → GRAVEYARD is MinionDied; this case is everything else."""
    in_hand = _entity(entity_id=40, zone="HAND", card_id="CS2_023", controller=2)
    discarded = _entity(entity_id=40, zone="GRAVEYARD", card_id="CS2_023", controller=2)
    prev = _state(turn=2, opponent_hand=(in_hand,))
    curr = _state(turn=2, opponent_hand=(discarded,))
    events = [e for e in diff(prev, curr) if isinstance(e, CardRemoved)]
    assert len(events) == 1
    assert events[0].entity_id == 40
    assert events[0].controller == 2


def test_play_to_removed_from_game_emits_card_removed() -> None:
    """A board entity removed directly from the game (PLAY → REMOVEDFROMGAME,
    e.g. a transform/removal effect) is a CardRemoved, never a MinionDied, and
    must not be silently dropped now that terminal-zone entities are visited."""
    on_board = _entity(
        entity_id=32, zone="PLAY", card_id="EX1_001", controller=1, card_type="MINION"
    )
    removed = _entity(
        entity_id=32,
        zone="REMOVEDFROMGAME",
        card_id="EX1_001",
        controller=1,
        card_type="MINION",
    )
    prev = _state(turn=5, player_board=(on_board,))
    curr = _state(turn=5, graveyard=(removed,))
    events = diff(prev, curr)
    assert [e for e in events if isinstance(e, MinionDied)] == []
    removed_events = [e for e in events if isinstance(e, CardRemoved)]
    assert len(removed_events) == 1
    assert removed_events[0].entity_id == 32
    assert removed_events[0].controller == 1


def test_deck_to_removed_from_game_emits_card_removed() -> None:
    """REMOVEDFROMGAME from a non-PLAY zone is a CardRemoved (e.g. mill, transform)."""
    in_deck = _entity(entity_id=41, zone="DECK", card_id="CS2_023", controller=1)
    removed = _entity(
        entity_id=41, zone="REMOVEDFROMGAME", card_id="CS2_023", controller=1
    )
    prev = _state(turn=3, player_deck=(in_deck,))
    curr = _state(turn=3, player_deck=(removed,))
    events = [e for e in diff(prev, curr) if isinstance(e, CardRemoved)]
    assert len(events) == 1
    assert events[0].entity_id == 41


def test_play_to_graveyard_does_not_double_emit_card_removed() -> None:
    """A MINION PLAY → GRAVEYARD is MinionDied, not CardRemoved. Each transition
    emits exactly one event."""
    alive = _entity(
        entity_id=30, zone="PLAY", card_id="CS2_023", controller=1, card_type="MINION"
    )
    dead = _entity(
        entity_id=30,
        zone="GRAVEYARD",
        card_id="CS2_023",
        controller=1,
        card_type="MINION",
    )
    prev = _state(turn=5, player_board=(alive,))
    curr = _state(turn=5, player_board=(dead,))
    removed = [e for e in diff(prev, curr) if isinstance(e, CardRemoved)]
    assert removed == []


# ------------------------------------------------------------------ CardRevealed


def test_hidden_to_revealed_card_id_emits_card_revealed() -> None:
    """An entity whose card_id was empty in prev and is non-empty in curr produces CardRevealed
    (e.g. opponent secret triggers, joust reveal, hand reveal)."""
    hidden = _entity(entity_id=50, zone="HAND", card_id="", controller=2)
    revealed = _entity(entity_id=50, zone="HAND", card_id="EX1_006", controller=2)
    prev = _state(turn=4, opponent_hand=(hidden,))
    curr = _state(turn=4, opponent_hand=(revealed,))
    events = [e for e in diff(prev, curr) if isinstance(e, CardRevealed)]
    assert len(events) == 1
    ev = events[0]
    assert ev.entity_id == 50
    assert ev.card_id == "EX1_006"
    assert ev.controller == 2


# ------------------------------------------------------------------ Secrets


def test_entity_entering_secret_emits_secret_played_without_revealing_name() -> None:
    hidden_in_hand = _entity(entity_id=60, zone="HAND", controller=2)
    hidden_secret = _entity(entity_id=60, zone="SECRET", controller=2)
    prev = _state(turn=3, opponent_hand=(hidden_in_hand,))
    curr = _state(turn=3, opponent_secrets=(hidden_secret,))

    events = list(diff(prev, curr))

    assert events == [SecretPlayed(timestamp=0.0, turn=3, controller=2)]


def test_known_entity_entering_secret_is_still_only_secret_played() -> None:
    hidden_in_hand = _entity(entity_id=62, zone="HAND", controller=1)
    known_secret = _entity(
        entity_id=62,
        zone="SECRET",
        card_id="EX1_611",
        name="Freezing Trap",
        controller=1,
    )
    prev = _state(turn=3, player_hand=(hidden_in_hand,))
    curr = _state(turn=3, player_secrets=(known_secret,))

    events = list(diff(prev, curr))

    assert events == [SecretPlayed(timestamp=0.0, turn=3, controller=1)]


def test_known_secret_leaving_for_graveyard_emits_secret_revealed_once() -> None:
    hidden_secret = _entity(entity_id=61, zone="SECRET", controller=2)
    revealed = _entity(
        entity_id=61,
        zone="GRAVEYARD",
        card_id="EX1_611",
        name="Freezing Trap",
        controller=2,
    )
    prev = _state(turn=4, opponent_secrets=(hidden_secret,))
    curr = _state(turn=4, graveyard=(revealed,))

    events = list(diff(prev, curr))

    assert events == [
        SecretRevealed(
            timestamp=0.0,
            turn=4,
            name="Freezing Trap",
            controller=2,
        )
    ]


# ------------------------------------------------------------------ DamageDealt


def test_damage_tag_change_during_attack_emits_damage_dealt() -> None:
    """An entity whose DAMAGE tag changes while curr.attack_in_progress is set produces DamageDealt."""
    healthy = _entity(
        entity_id=70, zone="PLAY", card_id="EX1_001", controller=2, tags={"DAMAGE": 0}
    )
    hurt = _entity(
        entity_id=70, zone="PLAY", card_id="EX1_001", controller=2, tags={"DAMAGE": 3}
    )
    aip = AttackInProgress(
        attacker_entity_id=80, defender_entity_id=70, attacker_controller=1
    )
    prev = _state(turn=6, opponent_board=(healthy,), attack_in_progress=aip)
    curr = _state(turn=6, opponent_board=(hurt,), attack_in_progress=aip)
    events = [e for e in diff(prev, curr) if isinstance(e, DamageDealt)]
    assert len(events) == 1
    ev = events[0]
    assert ev.target_entity_id == 70
    assert ev.amount == 3
    assert ev.target_controller == 2


def test_damage_tag_change_during_power_block_emits_damage_dealt() -> None:
    """DAMAGE tag changes while curr.block_stack[-1] == "POWER" also produces DamageDealt
    (e.g. spell-damage from a played card)."""
    healthy = _entity(
        entity_id=71, zone="PLAY", card_id="EX1_001", controller=2, tags={"DAMAGE": 0}
    )
    hurt = _entity(
        entity_id=71, zone="PLAY", card_id="EX1_001", controller=2, tags={"DAMAGE": 2}
    )
    prev = _state(turn=6, opponent_board=(healthy,), block_stack=("POWER",))
    curr = _state(turn=6, opponent_board=(hurt,), block_stack=("POWER",))
    events = [e for e in diff(prev, curr) if isinstance(e, DamageDealt)]
    assert len(events) == 1
    assert events[0].amount == 2


def test_hero_face_damage_emits_damage_dealt() -> None:
    """A hero's DAMAGE tag change under an ATTACK block (damage to face) produces
    DamageDealt — hero entities must be part of the diff input, or attacks and
    spells to face are silently dropped (codex review round 9)."""
    healthy = _entity(
        entity_id=64,
        zone="PLAY",
        card_id="HERO_01",
        controller=2,
        card_type="HERO",
        tags={"DAMAGE": 0},
    )
    hurt = _entity(
        entity_id=64,
        zone="PLAY",
        card_id="HERO_01",
        controller=2,
        card_type="HERO",
        tags={"DAMAGE": 6},
    )
    aip = AttackInProgress(
        attacker_entity_id=10, defender_entity_id=64, attacker_controller=1
    )
    prev = _state(turn=6, opponent_hero_entity=healthy, attack_in_progress=aip)
    curr = _state(turn=6, opponent_hero_entity=hurt, attack_in_progress=aip)
    events = [e for e in diff(prev, curr) if isinstance(e, DamageDealt)]
    assert len(events) == 1
    assert events[0].target_entity_id == 64
    assert events[0].amount == 6
    assert events[0].target_controller == 2


def test_damage_tag_change_outside_attack_or_power_block_does_not_emit() -> None:
    """DAMAGE changes outside of an ATTACK/POWER block are NOT DamageDealt
    (e.g. board snapshots after a block has already closed)."""
    healthy = _entity(
        entity_id=72, zone="PLAY", card_id="EX1_001", controller=2, tags={"DAMAGE": 0}
    )
    hurt = _entity(
        entity_id=72, zone="PLAY", card_id="EX1_001", controller=2, tags={"DAMAGE": 1}
    )
    prev = _state(turn=6, opponent_board=(healthy,))
    curr = _state(turn=6, opponent_board=(hurt,))
    events = [e for e in diff(prev, curr) if isinstance(e, DamageDealt)]
    assert events == []


# ------------------------------------------------------------------ ordering / determinism


def test_diff_is_deterministic_for_identical_inputs() -> None:
    """Same input → same output (same elements, same order)."""
    e_low = _entity(entity_id=10, zone="HAND", card_id="A", controller=1)
    e_high = _entity(entity_id=20, zone="HAND", card_id="B", controller=1)
    prev = _state(turn=1, active_player_id=2, mulligan_complete=False)
    curr = _state(
        turn=2,
        active_player_id=3,
        mulligan_complete=True,
        player_hand=(e_high, e_low),
    )
    first = list(diff(prev, curr))
    second = list(diff(prev, curr))
    assert first == second


def test_diff_orders_lifecycle_then_per_entity_by_id() -> None:
    """Documented ordering: turn lifecycle (TurnChanged, MulliganDone) before per-entity events,
    and per-entity events sorted by ascending entity_id so iteration order is stable
    regardless of how a tuple was constructed."""
    e_high = _entity(entity_id=99, zone="HAND", card_id="A", controller=1)
    e_low = _entity(entity_id=11, zone="HAND", card_id="B", controller=1)
    prev = _state(turn=1, active_player_id=2, mulligan_complete=False)
    curr = _state(
        turn=2,
        active_player_id=3,
        mulligan_complete=True,
        player_hand=(e_high, e_low),  # deliberately reversed order in the tuple
    )
    events = list(diff(prev, curr))
    types = [type(e).__name__ for e in events]
    # TurnChanged and MulliganDone come before any CardDrawn
    turn_idx = types.index("TurnChanged")
    mull_idx = types.index("MulliganDone")
    drawn_idxs = [i for i, t in enumerate(types) if t == "CardDrawn"]
    assert turn_idx < drawn_idxs[0]
    assert mull_idx < drawn_idxs[0]
    # Per-entity events sorted by entity_id ascending (11 before 99)
    drawn_events = [e for e in events if isinstance(e, CardDrawn)]
    assert [e.entity_id for e in drawn_events] == [11, 99]
