---
phase: 03-live-game-tracking
plan: 03
subsystem: services
tags: [phase-03, d-19, lineage, opponent-hand, engine, creation-lineage, frozen-dataclass]

# Dependency graph
requires:
  - phase: 02-log-infrastructure
    provides: GameEngine block bookkeeping (_block_stack, _block_subjects), _record_entity, _refresh_state, GameEntity frozen dataclass
  - phase: 03-live-game-tracking
    provides: 03-01 — xfail stub tests in tests/test_services/test_engine_lineage.py + power_log_fixture loader; 03-02 — 5-tuple CreateGamePacket and friendly_player_id resolution
provides:
  - GameEntity.creation_lineage (str, default "") field on the frozen dataclass
  - _record_entity lineage capture: INNERMOST POWER block subject card name, opponent-hand only, sticky once set
  - _refresh_state opponent_hand reconstruction from _entities (sorted by zone_position, dedupe by entity_id)
  - _record_entity now triggers _refresh_state so direct-into-HAND FullEntity packets surface in state.opponent_hand
  - 6 passing tests for D-19 (recorded / no-lineage-normal-draw / no-lineage-friendly / nested-blocks / show-entity-after / reconnect-fixture)
affects: [03-04, 03-05, 03-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lineage capture via INNERMOST stack-top subject (self._block_subjects[-1]) — locks nested-block semantics"
    - "Sticky-once-set bookkeeping ('creation_lineage' not in ent guard) for fields that must survive later updates"
    - "Implicit dedupe via dict iteration when reconstructing snapshots from entity_id-keyed bookkeeping"
    - "Unconditional _refresh_state call from _record_entity (no-op when _current_state is None) to keep published snapshot in sync after every entity update"

key-files:
  created:
    - .planning/phases/03-live-game-tracking/03-03-SUMMARY.md
  modified:
    - stonereader/models/game_state.py
    - stonereader/services/_engine.py
    - tests/test_services/test_engine_lineage.py

key-decisions:
  - "Option A (typed field on frozen dataclass) chosen over Option B (tags dict) per RESEARCH.md §Pattern 2 — type-safe, matches additive-default convention"
  - "_record_entity calls _refresh_state at end (no-op pre-CREATE_GAME) so direct-into-HAND FullEntity packets refresh state.opponent_hand. Existing _handle_zone_change refresh path remains unchanged"
  - "test_show_entity_after_lineage pre-resolves friendly_player via mulligan SHOW_ENTITY first to avoid WR-02 fallback misfiring on the opponent's reveal flipping friendly_player_id"
  - "Lineage best-effort: only INNERMOST subject captured, nested-generator chains attribute to inner subject only, stickiness prevents overwrite on later SHOW_ENTITY/TAG_CHANGE"

patterns-established:
  - "Lineage capture pattern: open-block-stack inspection + INNERMOST subject stamp + sticky-once-set guard. Reusable for any future best-effort attribution metadata"
  - "State-refresh after entity update: any _record_entity call now triggers _refresh_state, keeping the published frozen snapshot consistent with bookkeeping after every packet — avoids stale-state reads"

requirements-completed: []  # LIVE-04 deferred to plan 03-05 (presenter surface) per the 03-01 precedent — engine extension only enables it.
requirements-enabled: [LIVE-04]

# Metrics
duration: 6min
completed: 2026-04-27
---

# Phase 03 Plan 03: D-19 Creation Lineage + Opponent-Hand Reconstruction Summary

**Opponent-hand entities generated inside POWER blocks now carry `creation_lineage` (innermost subject card name, sticky once set), and `state.opponent_hand` is finally populated from engine bookkeeping — unblocking the D-04 / D-05 / D-14 hand-tracking surfaces in plan 03-05.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-27T03:24:38Z
- **Completed:** 2026-04-27T03:30:28Z
- **Tasks:** 2 (Task 1 model+engine, Task 2 tests; plus 1 follow-on bug fix)
- **Files modified:** 3 (1 model, 1 engine, 1 test)

## Accomplishments

- Added `GameEntity.creation_lineage: str = ""` with best-effort docstring documenting the four limitations (innermost only, sticky, dropped on reset, no Discover signal) per 03-REVIEWS.md MEDIUM 03-03.
- Implemented lineage capture in `_record_entity` with all 6 guards: open POWER block + non-empty subject stack + entity in HAND zone + non-friendly controller + known subject card_id + sticky guard.
- Reconstructed `state.opponent_hand` from `self._entities` in `_refresh_state` — sorted by zone_position, deduplicated by entity_id (implicit via dict iteration), with `creation_lineage` populated. Previously this was always `()`.
- Discovered and fixed a pre-existing engine bug: `_refresh_state` was only invoked from `_handle_zone_change`, so `FullEntity` packets arriving directly into HAND (no preceding zone) never republished. Now `_record_entity` triggers `_refresh_state` unconditionally (no-op pre-CREATE_GAME).
- Implemented all 6 D-19 lineage tests, replacing Wave 0 xfail stubs:
  - `test_lineage_recorded` — synthetic POWER block + opponent HAND captures Cabal Shadow Priest lineage.
  - `test_no_lineage_for_normal_draw` — no POWER block → no lineage.
  - `test_no_lineage_for_friendly` — friendly entities never tagged.
  - `test_lineage_nested_blocks` — innermost subject (Cabal) wins over outer (Wand of Disintegration).
  - `test_show_entity_after_lineage` — sticky guard preserves lineage when SHOW_ENTITY reveals card_id later.
  - `test_reconnect_drops_lineage` — captured `reconnect.log` confirms no stale lineage carries across CREATE_GAME boundary.
- All 256 production tests pass (24 xfailed in plans 03-04/05/06 stubs); zero regressions to 81 service tests, 6 friendly-player tests, parser tests.
- Frozen-dataclass discipline preserved — every `GameEntity` is constructed via `dataclasses.replace`, never mutated.
- Engine still has zero `hslog` imports (D-10 boundary preserved).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add creation_lineage field + opponent_hand reconstruction** — `92e4965` (feat)
2. **Bug fix discovered during Task 2: refresh published state on _record_entity** — `784b9de` (fix)
3. **Task 2: Implement 6 D-19 lineage tests** — `683c4d2` (test)

**Plan metadata commit:** pending (created with this SUMMARY).

## Files Created/Modified

- `stonereader/models/game_state.py` — Modified. Added `creation_lineage: str = ""` to `GameEntity` after `drawn_turn` with best-effort doc-comment block describing the four limitations.
- `stonereader/services/_engine.py` — Modified. `_record_entity` now captures lineage (innermost POWER block subject) and calls `_refresh_state` unconditionally; `_refresh_state` reconstructs `opponent_hand` from `self._entities`, sorted by zone_position, with `creation_lineage` populated.
- `tests/test_services/test_engine_lineage.py` — Modified. Replaced 6 Wave 0 xfail stubs with real test bodies. Added `_make_card`/`_make_card_db` helpers (mirror `tests/test_card_browser.py:13-54`). Removed `pytestmark = pytest.mark.xfail` and `pytest.xfail()` calls.

## Decisions Made

- **Option A (typed field on frozen dataclass) over Option B (tags dict storage):** RESEARCH.md §"Pattern 2 / Storage choice" recommends Option A — type-safe, surfaces clearly in IDE/pyright, matches the additive-default convention already established by `drawn_turn` and `hero_class`.
- **Unconditional `_refresh_state` call from `_record_entity`:** the alternative was to add refresh calls to every callsite (apply() FullEntity branch, ChangeEntity branch, _on_show_entity), but the central call inside `_record_entity` is one line vs three and impossible to forget. The early-return when `_current_state is None` makes it free during CREATE_GAME's own `_record_entity` calls (which fire before `_current_state` is set). No measurable cost for typical packet streams (each `_record_entity` is the bottleneck, not the recompute).
- **Pre-resolve friendly_player in `test_show_entity_after_lineage`:** without a prior friendly mulligan SHOW_ENTITY, the WR-02 fallback in `_resolve_friendly_player_show_entity_fallback` would interpret the opponent's revealed card as the first SHOW_ENTITY into HAND and flip `_friendly_player_id` from 1 to 2 — making the test scenario logically impossible. The test now mirrors real-game timing where friendly's mulligan reveals first.
- **drawn_turn left as `-1` (unknown) in opponent_hand reconstruction:** the engine doesn't currently capture per-entity draw turn at the bookkeeping level, only at the `PlayedCard.turn` snapshot. The presenter (plan 03-05) handles `-1` per 03-REVIEWS.md MEDIUM #5 by speaking "drawn turn unknown".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_refresh_state` not invoked when entities arrive directly into HAND**
- **Found during:** Task 2 (running `test_lineage_recorded` — `len(opponent_hand)` returned 0 instead of 1)
- **Issue:** `_refresh_state` was only called from `_handle_zone_change`, which fires on `TAG_CHANGE` zone transitions. When `FullEntityPacket` arrives directly into HAND (no preceding zone — common for cards generated mid-block, the very scenario this plan is implementing), `_record_entity` updates the bookkeeping dict but never republishes the snapshot. Result: `state.opponent_hand` stayed empty even though `self._entities[20]` had the correct ZONE/CONTROLLER/creation_lineage tags.
- **Fix:** Added `self._refresh_state()` at the end of `_record_entity`. Safe to invoke unconditionally — it's a no-op when `_current_state is None` (during CREATE_GAME's own `_record_entity` calls, before the initial state is constructed). All other callers benefit from automatic snapshot consistency.
- **Files modified:** `stonereader/services/_engine.py`
- **Verification:** All 6 lineage tests + 81 prior service tests pass.
- **Committed in:** `784b9de` (separate fix commit between Task 1 and Task 2 for bisectability).

**2. [Rule 2 - Missing critical] Test scenario for `test_show_entity_after_lineage` had to pre-resolve friendly_player**
- **Found during:** Task 2 (running `test_show_entity_after_lineage` — `next(... entity_id == 60)` raised StopIteration after the SHOW_ENTITY)
- **Issue:** The plan's specified test sequence skipped the WR-02 friendly-player resolution step. With `_friendly_player_resolved == False`, the fallback in `_on_show_entity` interprets the SHOW_ENTITY-into-HAND of the opponent's revealed card as evidence that controller=2 is friendly. It flips `_friendly_player_id` from 1 to 2 and re-buckets — entity 60 (CONTROLLER=2) is now friendly, so it leaves `state.opponent_hand`. The test was logically inconsistent with the WR-02 fallback contract added in plan 03-02.
- **Fix:** Added a leading friendly-mulligan SHOW_ENTITY (entity_id=99, CONTROLLER=1, ZONE=HAND) before the lineage scenario. This pre-locks `_friendly_player_resolved = True` so subsequent SHOW_ENTITY events (including the opponent's reveal of entity 60) do not retrigger the fallback. Documented in the test docstring.
- **Files modified:** `tests/test_services/test_engine_lineage.py`
- **Verification:** Test passes; lineage is correctly preserved when card_id is revealed.
- **Committed in:** `683c4d2` (Task 2 commit).

---

**3. [Rule 1 - Bug] Reverted LIVE-04 requirement mark (engine enabler vs presenter surface)**
- **Found during:** State updates after Task 2 commit
- **Issue:** Plan frontmatter declares `requirements: [LIVE-04]`, and the standard execute-plan flow calls `gsd-sdk query requirements.mark-complete LIVE-04`. But LIVE-04 reads "User can see opponent's played cards in play order" — this is a USER-FACING requirement satisfied only when the presenter exposes the data, not when the engine merely makes it available. The plan's own objective text acknowledges this: "LIVE-04 is therefore listed in BOTH this plan's `requirements` (engine enabler) and 03-05's `requirements` (presenter surface)." Per the precedent set in plan 03-01's deviation note, requirement marks should track user-visible delivery, not enabler work.
- **Fix:** Manually unchecked the `[x]` box in `.planning/REQUIREMENTS.md` for LIVE-04 after the gsd-sdk handler ran. Updated SUMMARY.md frontmatter to `requirements-completed: []` with explanatory comment, and added `requirements-enabled: [LIVE-04]` to capture what was actually delivered (engine extension that enables the requirement). The traceability table already correctly reads "Pending" for LIVE-04.
- **Files modified:** `.planning/REQUIREMENTS.md`, `.planning/phases/03-live-game-tracking/03-03-SUMMARY.md`
- **Verification:** `grep "LIVE-04" .planning/REQUIREMENTS.md` shows the requirement unchecked and traceability still Pending.
- **Committed in:** Final metadata commit (this SUMMARY commit).

---

**Total deviations:** 3 auto-fixed (1 engine bug fix that the plan didn't anticipate, 1 test-scenario correction needed to align with plan-03-02's WR-02 fallback semantics, 1 requirement-mark correction to maintain user-visible-delivery accounting).

**Impact on plan:** Deviation 1 is a real engine correctness gap that affected the plan's central deliverable (`state.opponent_hand` was always `()` even before this plan, but the plan's own design implicitly required `_refresh_state` to fire on entity updates — without the fix, the opponent_hand reconstruction code never executed for the relevant packet flows). Deviation 2 was a pre-flight reading miss in the plan author's specification — the WR-02 fallback contract from 03-02 changed the SHOW_ENTITY semantics in a way that interacted with the plan's test design. Deviation 3 preserves accurate requirement-completion accounting per the 03-01 precedent. No scope creep — all three were corrections to maintain plan and accounting integrity.

## Issues Encountered

None beyond the deviations above. The plan's pre-flight reading (Wave 0 stubs, engine source, packet definitions, RESEARCH/PATTERNS/REVIEWS context, captured fixtures) gave a clean execution path once the upstream gaps were addressed.

## Threat Flags

None. The implementation matches every threat in the plan's `<threat_model>`:

- **T-03-D19-01** (Information Disclosure / friendly mis-tag): mitigated by `controller != self._friendly_player_id` guard. `test_no_lineage_for_friendly` regression-locks.
- **T-03-D19-02** (Stale lineage on reconnect): mitigated by existing `reset()` clearing `self._entities` (drops `creation_lineage` keys). `test_reconnect_drops_lineage` regression-locks against the captured fixture.
- **T-03-D19-03** (DoS on malformed POWER block): mitigated by `if subject_card_id` + `if subject_card` short-circuits; engine `apply()` already wraps every packet in try/except.
- **T-03-D19-04** (Lineage overwritten by later TAG_CHANGE/SHOW_ENTITY): mitigated by `"creation_lineage" not in ent` sticky guard. `test_show_entity_after_lineage` regression-locks.
- **T-03-D19-05** (Nested-block subject ambiguity): mitigated by `self._block_subjects[-1]` (innermost). `test_lineage_nested_blocks` regression-locks.

## User Setup Required

None — the plan touched models, engine, and tests only; no new dependencies, config files, or external services.

## Next Phase Readiness

- **Plan 03-04 (GlobalHotkeyService):** unaffected — purely UI/wx layer.
- **Plan 03-05 (LiveGamePresenter):** can now consume `state.opponent_hand` for the `opponent_hand` zone (D-04, D-05, LIVE-05). Lineage is available via `entity.creation_lineage` for "generated by [card]" speech. Drawn-turn fallback per REVIEWS.md MEDIUM #5 (`drawn_turn == -1` → "drawn turn unknown") works as documented.
- **Plan 03-06 (LiveGamePanel + app wiring):** unaffected.
- **Phase 4 (Replay viewer):** the engine remains hslog-free (D-10), so the lineage capture works identically when replaying HSReplay XMLs.

## Self-Check: PASSED

Verified files and commits exist on disk and in git history:

- `stonereader/models/game_state.py` — FOUND (`creation_lineage: str = ""` present, "Best-effort" doc-comment present)
- `stonereader/services/_engine.py` — FOUND (`creation_lineage` referenced 5+ times, `INNERMOST subject` comment, `opponent_hand=tuple(opponent_hand_entities)`, `opponent_hand_entities.sort(key=lambda e: e.zone_position)`, `self._refresh_state()` call inside `_record_entity`)
- `tests/test_services/test_engine_lineage.py` — FOUND (6 named test functions, no `pytestmark = pytest.mark.xfail`, helpers `_make_card`/`_make_card_db` present)
- `.planning/phases/03-live-game-tracking/03-03-SUMMARY.md` — FOUND (this file)
- Commit `92e4965` — FOUND (Task 1: model + engine)
- Commit `784b9de` — FOUND (fix: refresh on _record_entity)
- Commit `683c4d2` — FOUND (Task 2: 6 lineage tests)

Plan-level verification:
- `uv run pytest tests/ -q` → 256 passed, 24 xfailed (other Phase 3 stubs in 03-04/05/06)
- `uv run pytest tests/test_services/test_engine_lineage.py -v` → 6 passed
- `uv run pytest tests/test_services/ -q` → 87 passed (was 81 + 6 newly-passing lineage)
- `uv run ruff check stonereader/models/game_state.py stonereader/services/_engine.py tests/test_services/test_engine_lineage.py` → All checks passed
- `uv run pyright stonereader/models/game_state.py stonereader/services/_engine.py` → 0 errors, 0 warnings
- `grep "import hslog\|from hslog" stonereader/services/_engine.py` → no matches (D-10 boundary preserved)

---
*Phase: 03-live-game-tracking*
*Completed: 2026-04-27*
