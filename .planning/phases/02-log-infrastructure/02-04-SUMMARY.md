---
phase: 02-log-infrastructure
plan: 04
subsystem: models+services
tags: [game-state, events, frozen-dataclass, tdd, data-layer, wave-2]

requires:
  - phase: 02-log-infrastructure
    plan: 01
    provides: "Wave 0 test scaffolding (conftest.py, stub tests)"

provides:
  - "stonereader/models/game_state.py — Hero+hero_class, GameEntity+drawn_turn, new PlayedCard, GameState+11 fields"
  - "stonereader/services/_events.py — GameEvent base + 10 concrete frozen event dataclasses"
  - "stonereader/services/__init__.py — re-exports all 12 event types via __all__"
  - "tests/test_services/test_game_state_extension.py — 7 tests verifying D-08 extension"
  - "tests/test_services/test_events.py — 5 tests verifying D-06 event taxonomy"

affects:
  - "02-05 (parser) — can import PlayedCard from stonereader.models.game_state"
  - "02-06 (engine) — consumes packets and emits these exact event types"
  - "02-07 (tracker) — imports GameEvent and concrete events from stonereader.services"

tech-stack:
  added: []
  patterns:
    - "Frozen dataclass inheritance for typed events — base class fields must be no-default so child classes can add required fields (default-ordering gotcha)"
    - "Tuple-only collections on GameState — List[X] would violate frozen immutability invariant (Pitfall 4)"
    - "Unused import removed from _events.py (PlayedCard was in plan template but not referenced by any event class)"

key-files:
  created:
    - stonereader/services/_events.py
    - tests/test_services/test_game_state_extension.py
    - tests/test_services/test_events.py
  modified:
    - stonereader/models/game_state.py
    - stonereader/services/__init__.py

decisions:
  - "opponent_deck deliberately NOT exposed as Tuple field — Hearthstone Power.log never reveals opponent deck contents; player_deck count-only field retains the existing opponent_deck_count int."
  - "PlayedCard import removed from _events.py — plan template included it but no event class references it; ruff F401 flagged it and CLAUDE.md mandates clean ruff check."
  - "GameState now has 29 fields total: 18 existing + 11 new (player_deck, player_played, opponent_played, player_drawn, opponent_drawn, game_state, game_type, format_type, player_playstate, opponent_playstate, player_starting_hand)."
  - "Plan noted 27 fields in output spec but actual count is 29 (the original 18 included player_mana, player_max_mana, opponent_mana, opponent_max_mana — 4 mana fields not counted in plan's estimate)."

metrics:
  duration: 5m
  completed: 2026-04-26T04:49:39Z
  tasks: 2
  files_created: 3
  files_modified: 2
  tests_added: 12
---

# Phase 2 Plan 04: Data Layer — GameState Extension + Event Taxonomy Summary

**GameState extended with 11 new fields (PlayedCard, player_deck, play/draw history, lifecycle strings); 12 frozen event dataclasses created covering game lifecycle, turn, card movement, and combat.**

## Performance

- **Duration:** 5m
- **Started:** 2026-04-26T04:44:17Z
- **Completed:** 2026-04-26T04:49:39Z
- **Tasks:** 2 (both TDD)
- **Files created:** 3
- **Files modified:** 2
- **Tests added:** 12 (7 for D-08 extension, 5 for D-06 events)

## Accomplishments

### Task 1 — D-08: Extend `stonereader/models/game_state.py`

- `Hero` gains `hero_class: str = ""` for matchup announcements (LIVE-08, GameStarted payload)
- `GameEntity` gains `drawn_turn: int = -1` (0 = mulligan, -1 = unknown/hidden opponent card)
- New `PlayedCard` frozen dataclass: `entity_id`, `card_id`, `base_card`, `name`, `turn`, `controller` — mirrors HDT's CardsPlayedThisMatch
- `GameState` gains 11 new defaulted fields:
  - `player_deck: Tuple[GameEntity, ...]` (drives LIVE-02 remaining deck)
  - `player_played`, `opponent_played: Tuple[PlayedCard, ...]` (drives LIVE-04 opponent plays)
  - `player_drawn`, `opponent_drawn: Tuple[PlayedCard, ...]` (drives LIVE-03 cards drawn)
  - `game_state: str = "RUNNING"`, `game_type`, `format_type` (game lifecycle queries)
  - `player_playstate`, `opponent_playstate` (win/loss detection)
  - `player_starting_hand: Tuple[GameEntity, ...]` (auto-deck-detect, deferred to Phase 3)
- All new fields are defaulted — existing constructors in tests and Phase 1 code remain unchanged
- No `List[X]` types (Pitfall 4 preserved — T-2-DATA threat mitigated)

### Task 2 — D-06: Create `stonereader/services/_events.py`

Twelve frozen dataclasses (1 base + 11 concrete):

| Class | Fields beyond timestamp+turn |
|-------|------------------------------|
| `GameEvent` | base: `timestamp: float`, `turn: int` |
| `GameStarted` | `player_class`, `opponent_class`, `game_type`, `format_type` |
| `GameEnded` | `player_playstate`, `opponent_playstate` |
| `TurnChanged` | `active_player_id` |
| `MulliganDone` | (no extra fields) |
| `CardDrawn` | `entity_id`, `card_id`, `base_card`, `name`, `controller` |
| `CardPlayed` | `entity_id`, `card_id`, `base_card`, `name`, `controller` |
| `CardRevealed` | `entity_id`, `card_id`, `base_card`, `name`, `controller` |
| `CardRemoved` | `entity_id`, `card_id`, `controller` |
| `AttackStarted` | `attacker_entity_id`, `defender_entity_id`, `attacker_controller` |
| `MinionDied` | `entity_id`, `card_id`, `name`, `controller` |
| `DamageDealt` | `target_entity_id`, `amount`, `target_controller` |

`services/__init__.py` updated to re-export all 12 types in `__all__`. Plan 07 (GameTracker) will add `GameTracker` to the same `__all__`.

## Task Commits

| Task | Phase | Commit | Description |
|------|-------|--------|-------------|
| 1 | RED | `d80bd38` | Failing tests for GameState D-08 extension |
| 1 | GREEN | `e20c680` | Extend GameState (Hero, GameEntity, PlayedCard) |
| 2 | RED | `b2ec1f7` | Failing tests for D-06 event classes |
| 2 | GREEN | `8f12bd7` | Create _events.py with 11 frozen event classes |

## Tests

```
$ uv run pytest tests/test_services/test_game_state_extension.py tests/test_services/test_events.py -v
12 passed in 0.10s

$ uv run pytest tests/
202 passed, 17 skipped in 0.95s
```

| Test file | Count | Coverage |
|-----------|-------|----------|
| `test_game_state_extension.py` | 7 | hero_class default/set, drawn_turn default, PlayedCard frozen, GameState new fields, tuple collections, backward compat |
| `test_events.py` | 5 | inheritance, frozen dataclass params, GameStarted shape, CardDrawn shape, __all__ completeness |

## Acceptance Criteria — All Met

- `grep -c "class PlayedCard" stonereader/models/game_state.py` == 1
- `grep -c "hero_class:" stonereader/models/game_state.py` == 1
- `grep -c "drawn_turn:" stonereader/models/game_state.py` == 1
- `grep -c "player_played:" stonereader/models/game_state.py` == 1
- `grep -c "opponent_played:" stonereader/models/game_state.py` == 1
- `grep -c "player_drawn:" stonereader/models/game_state.py` == 1
- `grep -c "game_state:" stonereader/models/game_state.py` == 1
- `grep -c "player_starting_hand:" stonereader/models/game_state.py` == 1
- `grep -E "List\[.*\]" stonereader/models/game_state.py` returns nothing (no List — Pitfall 4)
- `grep -cE "@dataclass\(frozen=True\)" stonereader/services/_events.py` == 12
- All 12 event classes present in `_events.py`
- `from stonereader.services._events import` present in `__init__.py`
- `uv run pyright stonereader/models/game_state.py stonereader/services/_events.py` — 0 errors
- Full suite: 202 passed, 17 skipped

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `PlayedCard` import from `_events.py`**
- **Found during:** Task 2 GREEN (ruff check pass)
- **Issue:** The plan's `_events.py` template included `from stonereader.models.game_state import PlayedCard`, but none of the 11 event classes reference `PlayedCard` in their fields — they use `Optional[Card]` for `base_card`. Ruff F401 flagged the unused import. CLAUDE.md mandates `uv run ruff check .` passes.
- **Fix:** Removed the `PlayedCard` import line from `_events.py`. The import is correctly placed in the test file (`test_game_state_extension.py`) where `PlayedCard` is actually used.
- **Files modified:** `stonereader/services/_events.py`
- **Verification:** `uv run ruff check stonereader/services/_events.py` — "All checks passed!"
- **Committed in:** `8f12bd7` (Task 2 GREEN — fix applied before commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — unused import, pure lint hygiene)
**Impact on plan:** No behavioral change. `PlayedCard` remains importable from `stonereader.models.game_state` for use by Plan 05 (parser) and Plan 06 (engine).

## Threat Model Verification

| Threat ID | Disposition | Verified by |
|-----------|-------------|-------------|
| T-2-DATA (Tampering — collection mutability) | mitigated | `test_game_state_collections_are_tuples` + `grep -E "List\[" stonereader/models/game_state.py` returns empty. All Tuple fields verified in GameState. |

No new threat surface: this plan is pure data definitions with no I/O, no external input, no network endpoints.

## Notes

- **GameState field count:** 29 total (18 existing + 11 new). The plan's `<output>` section stated "existing + new = 27" — the actual existing count was 18 not 16 (the 4 mana fields `player_mana`, `player_max_mana`, `opponent_mana`, `opponent_max_mana` were included in the original). The implementation matches the RESEARCH.md diff exactly; only the plan's estimate was off.
- **`__all__` Plan 07 readiness:** The `services/__init__.py` `__all__` list currently contains 12 entries. Plan 07 (GameTracker) appends `"GameTracker"` to this list without conflict — confirmed by reviewing the plan's import expectations.
- **Memory bound note (RESEARCH.md line 404):** `player_played + opponent_played + player_drawn + opponent_drawn` grow O(game length). Engine subscribers must not retain old snapshots; only the latest GameState should be held. This is documented for Plan 06 (engine docstring).

## TDD Gate Compliance

| Task | RED commit | GREEN commit | REFACTOR |
|------|------------|--------------|---------|
| 1 (D-08 GameState) | `d80bd38` | `e20c680` | not needed |
| 2 (D-06 events) | `b2ec1f7` | `8f12bd7` | not needed |

## Self-Check: PASSED

- [x] `stonereader/models/game_state.py` exists and contains `PlayedCard`, `hero_class`, `drawn_turn`, `player_played`, `opponent_played`, `player_drawn`, `game_state`, `player_starting_hand`
- [x] `stonereader/services/_events.py` exists with 12 frozen dataclasses
- [x] `stonereader/services/__init__.py` updated with event re-exports and `__all__`
- [x] `tests/test_services/test_game_state_extension.py` exists (7 tests)
- [x] `tests/test_services/test_events.py` exists (5 tests)
- [x] Commit `d80bd38` (RED Task 1) — FOUND
- [x] Commit `e20c680` (GREEN Task 1) — FOUND
- [x] Commit `b2ec1f7` (RED Task 2) — FOUND
- [x] Commit `8f12bd7` (GREEN Task 2) — FOUND
- [x] `uv run pytest tests/` — 202 passed, 17 skipped
- [x] `uv run pyright stonereader/models/game_state.py stonereader/services/_events.py` — 0 errors, 0 warnings
- [x] `uv run ruff check stonereader/` — All checks passed

---
*Phase: 02-log-infrastructure*
*Plan: 04*
*Completed: 2026-04-26*
