---
phase: 03-live-game-tracking
fixed_at: 2026-04-29T00:00:00Z
review_path: .planning/phases/03-live-game-tracking/03-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-04-29T00:00:00Z
**Source review:** `.planning/phases/03-live-game-tracking/03-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope (blocker + warning): 6
- Fixed: 6
- Skipped: 0

All BL/WR findings landed as atomic commits on `main`. BL-01 and WR-01
share a single commit because they share root cause (the
`_rebucket_from_entities` post-flip pass never re-attributed heroes or
mana) and the user's instructions explicitly directed implementing the
helper once and calling it from one site. A new synthetic regression
test (`test_pvp_fallback_rebuckets_heroes_and_mana`) was added that
exercises the lo!=0 / lo!=0 multiplayer path, was confirmed to FAIL
without the engine fix, then PASS with it applied.

## Fixed Issues

### BL-01 + WR-01: Re-resolve heroes and mana on PvP fallback

**Files modified:** `stonereader/services/_engine.py`, `tests/test_services/test_engine_live_state.py`
**Commit:** `78778c3`
**Applied fix:** `_rebucket_from_entities` now also calls `_resolve_heroes()`
and a new `_reapply_mana_from_entities()` helper that walks player entity
rows and re-derives `player_mana`/`player_max_mana`/`opponent_mana`/
`opponent_max_mana` from authoritative `PLAYER_ID` after the friendly
player_id flips. New synthetic test
`test_pvp_fallback_rebuckets_heroes_and_mana` constructs a
multiplayer-shaped CREATE_GAME (both players have `lo != 0`), records
WARRIOR/MAGE hero FullEntities and a RESOURCES TagChange before the
fallback, then triggers a SHOW_ENTITY-into-HAND with controller=2 to
flip `_friendly_player_id`. Asserts `player_hero.hero_class == "MAGE"`
and `opponent_max_mana == 1` post-fallback. Verified the test FAILS on
pre-fix engine (player_hero stays WARRIOR) and PASSES on post-fix.

### WR-02: Preserve real HEALTH=0 in `_resolve_heroes`

**Files modified:** `stonereader/services/_engine.py`
**Commit:** `48cc39d`
**Applied fix:** Replaced `ent.get("HEALTH", 30) or 30` /
`ent.get("ARMOR", 0) or 0` with explicit `is None` checks (`health = 30
if health_raw is None else int(health_raw)`) so legitimate zero values
(SHOW_ENTITY rebroadcast after lethal) are no longer clamped back to 30.

### WR-03: Clarify `_resolve_heroes` call in `_on_create_game`

**Files modified:** `stonereader/services/_engine.py`
**Commit:** `745b802`
**Applied fix:** Updated the misleading comment on the `_on_create_game`
→ `_resolve_heroes()` call. The previous comment claimed hero
FullEntities were recorded inside CREATE_GAME's loop; in current hslog
each FullEntity is a separate top-level packet so the call is a no-op
in practice. New comment frames it as defensive coverage for the rare
case where hslog inlines hero rows under `CreateGame.entities`, so
future readers do not delete the call as redundant.

### WR-04: Deduplicate `_player_entity_id` PlayerReference handling

**Files modified:** `stonereader/services/_parser.py`
**Commit:** `7443f23`
**Applied fix:** `_player_entity_id` now delegates the
PlayerReference / int coercion to `_normalize_entity_id`, keeping
its `player_id` fallback only for the case where normalization yields
0. Eliminates the drift risk between the two near-identical helpers
that route CreateGame and TagChange paths.

### WR-05: Reduce engine private-state coupling in live-state tests

**Files modified:** `tests/test_services/test_engine_live_state.py`
**Commit:** `c23c26b`
**Applied fix:** `test_deck_counts_track_zone` no longer cross-checks
`state.player_deck_count` by iterating `engine._entities`; instead
asserts `state.player_deck_count == len(state.player_deck)` (both
fields are derived in the same `_refresh_state` pass, so equality is
the correct invariant and uses only public state).
`test_player_deck_rebuilt_from_entities` retains its
`engine._friendly_player_id` access (no public accessor exists yet) but
gains an explicit annotation matching the IN-03 "this is one of the
rare tests that DOES read internal state" pattern, so the coupling is
documented as intentional and trackable.

## Verification

- All 6 live-state tests pass (1 new + 5 existing in
  `test_engine_live_state.py`).
- All 93 service tests pass after each commit.
- `uv run ruff check` clean on touched files.
- `uv run ruff format` produces no diffs on touched files.
- `uv run pyright` reports 0 errors / 0 warnings on
  `stonereader/services/_engine.py` and `stonereader/services/_parser.py`.
- BL-01 regression test was confirmed to FAIL on pre-fix engine state
  (via `git stash` revert) and PASS with the fix applied.
- The 36 wx-related failures observed when running the full `tests/`
  suite are pre-existing environmental issues (`PyNoAppError` from
  test-cross-contamination in headless wx); reproduced identically on
  the pre-fix baseline (`102 passed` vs post-fix `103 passed` — the
  delta is exactly the new BL-01 regression test). Not caused by these
  fixes.

---

_Fixed: 2026-04-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
