---
phase: 03-live-game-tracking
plan: 01
subsystem: testing
tags: [pytest, xfail, mock-tracker, test-scaffolding, wave-0, phase-03]

# Dependency graph
requires:
  - phase: 02-log-infrastructure
    provides: GameTracker subscribe/unsubscribe contract, GameEvent classes, GameState model, power_log_fixture loader
provides:
  - MockGameTracker test double with subscribe/unsubscribe/current_state/dispatch/set_state surface
  - Public caught_exceptions accessor for asserting subscriber-isolation behavior
  - 36 named stub tests covering LIVE-01..09 + WR-02 + D-19 (xfail-marked, awaiting implementation)
  - Verified `tests.conftest` import pattern works for new Phase 3 test modules
affects: [03-02, 03-03, 03-04, 03-05, 03-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest.mark.xfail file-level pytestmark + per-test pytest.xfail() body for Wave 0 stubs"
    - "MockGameTracker mirrors GameTracker public surface but exposes caught_exceptions for test visibility"

key-files:
  created:
    - tests/test_live_game_presenter.py
    - tests/test_global_hotkey.py
    - tests/test_services/test_engine_friendly_player.py
    - tests/test_services/test_engine_lineage.py
    - .planning/phases/03-live-game-tracking/03-01-SUMMARY.md
  modified:
    - tests/conftest.py

key-decisions:
  - "MockGameTracker exposes caught_exceptions list (vs production silent log) so tests can assert subscriber isolation explicitly per 03-REVIEWS.md 03-01 LOW concern"
  - "All Wave 0 stubs use pytest.mark.xfail(strict=False) at file level + pytest.xfail() in body — accidental implementation flips XFAIL→XPASS without breaking the build, but a stub with no implementation still fails-as-expected if reached"
  - "Global-hotkey stubs use pytest.importorskip('wx') so non-Windows CI collects but skips them"

patterns-established:
  - "Wave 0 stub format: file-level pytestmark = pytest.mark.xfail + module docstring referencing plan owner + per-test pytest.xfail('not implemented yet — plan 03-NN')"
  - "Test fixture parity: MockGameTracker docstring documents exception-isolation contract identical to production GameTracker._dispatch (Pitfall 3)"

requirements-completed: []  # Wave 0 is test-scaffolding only — actual LIVE-01..09 implementation lands in plans 03-02..03-06
requirements-scaffolded: [LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, LIVE-06, LIVE-07, LIVE-08, LIVE-09]

# Metrics
duration: 5min
completed: 2026-04-27
---

# Phase 03 Plan 01: Wave 0 Test Scaffolds + MockGameTracker Summary

**MockGameTracker test double + 36 xfail-marked stub tests across 4 new test files give Phase 3 Waves 1-3 a fast feedback loop with no production code touched.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-27T02:58:13Z
- **Completed:** 2026-04-27T03:03:01Z
- **Tasks:** 3
- **Files modified:** 5 (1 modified, 4 created)

## Accomplishments

- Added `MockGameTracker` to `tests/conftest.py` mirroring the production `GameTracker` subscribe/unsubscribe/current_state contract, plus `dispatch()` and `set_state()` test helpers and a `caught_exceptions` accessor that surfaces subscriber-raise behavior (vs the production silent log).
- Created `tests/test_live_game_presenter.py` with 19 named stubs covering LIVE-01..09 + D-07/D-08/D-09 + the LIVE-03 cards-drawn zone + drawn-turn-unknown speech + public-accessor lockdown + number-key zone switching (per VALIDATION.md, REVIEWS.md, and CHECKER blocker #1).
- Created `tests/test_global_hotkey.py` with 5 named stubs covering LIVE-09 register/dispatch/clear-all + callback exception isolation + repeated-register-after-failure (per VALIDATION.md + REVIEWS.md).
- Created `tests/test_services/test_engine_friendly_player.py` with 6 stubs for WR-02 friendly-player resolution including the new mixed-timing-fallback and reconnect-resolves cases per REVIEWS.md HIGH #2.
- Created `tests/test_services/test_engine_lineage.py` with 6 stubs for D-19 creation-lineage tracking including nested-block subject selection and show-entity-after-lineage stickiness per REVIEWS.md MEDIUM 03-03.
- 36 total stub tests — all collected (`uv run pytest tests/ --collect-only -q` shows 280 tests, up from 244), all marked XFAIL, no real PASS or FAIL outcomes, no collection errors.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add MockGameTracker fixture to tests/conftest.py** — `3423d69` (feat)
2. **Task 2: Create stub test files for LiveGamePresenter + GlobalHotkey** — `e1145f9` (test)
3. **Task 3: Create stub test files for engine WR-02 + lineage extensions** — `bc79862` (test)

**Plan metadata commit:** pending (created with this SUMMARY).

## Files Created/Modified

- `tests/conftest.py` — Modified. Added typing/GameState/GameEvent imports and `MockGameTracker` class (idempotent subscribe, exception-isolated dispatch, `set_state` helper, `caught_exceptions` list).
- `tests/test_live_game_presenter.py` — Created. 19 xfail-marked stubs for the LiveGamePresenter behaviors that plans 03-05/03-06 will implement.
- `tests/test_global_hotkey.py` — Created. 5 xfail-marked stubs (with `pytest.importorskip("wx")`) for the GlobalHotkeyService that plan 03-04 will implement.
- `tests/test_services/test_engine_friendly_player.py` — Created. 6 xfail-marked stubs for WR-02 friendly-player resolution that plan 03-02 will implement; fixture-bound stubs use `power_log_fixture` injection.
- `tests/test_services/test_engine_lineage.py` — Created. 6 xfail-marked stubs for D-19 creation-lineage tracking that plan 03-03 will implement.

## Decisions Made

- **`caught_exceptions` accessor on MockGameTracker** — Production `GameTracker._dispatch` swallows subscriber exceptions to a `logger.exception` call. The test double captures them in a list instead so tests can assert isolation behavior explicitly (per 03-REVIEWS.md 03-01 LOW concern about hidden debug signal).
- **File-level `pytestmark = pytest.mark.xfail(strict=False)` + per-test `pytest.xfail()` body** — File-level mark keeps the suite green during Wave 0..2; the inner `xfail()` call ensures any stub that's accidentally un-marked still surfaces as a deliberate failure rather than a misleading pass.
- **`pytest.importorskip("wx")` on every global-hotkey stub** — Linux CI cannot import wx, but the stubs must still be collectible. Importorskip is the established pattern from `tests/test_services/test_tracker.py:82-103`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reverted premature requirements completion**
- **Found during:** State updates (after Task 3 commit)
- **Issue:** Plan frontmatter lists `requirements: [LIVE-01..LIVE-09]`, and the standard execute-plan flow calls `gsd-sdk query requirements.mark-complete` for each. Wave 0 only delivers test scaffolding — none of LIVE-01..09 are actually implemented yet (production code lands in plans 03-02..03-06). Marking them complete would falsely signal Phase 3 done.
- **Fix:** Manually unchecked the `[x]` boxes in `.planning/REQUIREMENTS.md` for LIVE-01..09 after the gsd-sdk handler ran. Updated SUMMARY.md frontmatter to `requirements-completed: []` and added `requirements-scaffolded: [LIVE-01..LIVE-09]` to capture what was actually delivered.
- **Files modified:** `.planning/REQUIREMENTS.md`, `.planning/phases/03-live-game-tracking/03-01-SUMMARY.md`
- **Verification:** `grep "^- \[ \] \*\*LIVE-0" .planning/REQUIREMENTS.md` shows all 9 unchecked.
- **Committed in:** Final metadata commit (this SUMMARY commit).

---

**Total deviations:** 1 auto-fixed (1 bug-correction).
**Impact on plan:** No scope creep. The fix preserves accurate requirement-completion accounting — Wave 0 builds the test scaffold; later waves flip stubs to passing AND mark the requirements complete.

## Issues Encountered

None. The plan's pre-flight reading (existing `MockSpeechService`, `_tracker.py:90-108` contract, `power_log_fixture` from `tests/test_services/conftest.py`) gave a clean execution path.

## User Setup Required

None — Wave 0 adds no new dependencies, no new config files, no external services.

## Next Phase Readiness

- **Plan 03-02 (WR-02 friendly-player resolution):** Can wire its implementation against `tests/test_services/test_engine_friendly_player.py`'s 6 xfail stubs. Removing each `pytest.xfail()` line and the file-level pytestmark will flip them to passing when the implementation lands.
- **Plan 03-03 (D-19 creation lineage):** Same pattern with `tests/test_services/test_engine_lineage.py`.
- **Plan 03-04 (GlobalHotkeyService):** Same pattern with `tests/test_global_hotkey.py`.
- **Plan 03-05 (LiveGamePresenter):** Imports `MockGameTracker` and `MockSpeechService` from `tests.conftest`; 19 stubs already name every required behavior.
- **Plan 03-06 (LiveGamePanel + app wiring):** May extend `tests/test_live_game_presenter.py` with additional view-binding stubs as needed; the plan acceptance is "all required named tests exist" (not a frozen total).

## Self-Check: PASSED

Verified files and commits exist on disk and in git history:

- `tests/conftest.py` — FOUND (modified, contains `class MockGameTracker`, `class MockSpeechService` preserved)
- `tests/test_live_game_presenter.py` — FOUND (19 named test functions, all xfail)
- `tests/test_global_hotkey.py` — FOUND (5 named test functions, all xfail with importorskip wx)
- `tests/test_services/test_engine_friendly_player.py` — FOUND (6 named test functions, all xfail)
- `tests/test_services/test_engine_lineage.py` — FOUND (6 named test functions, all xfail)
- Commit `3423d69` — FOUND (Task 1: MockGameTracker)
- Commit `e1145f9` — FOUND (Task 2: LiveGamePresenter + GlobalHotkey stubs)
- Commit `bc79862` — FOUND (Task 3: engine WR-02 + lineage stubs)

Plan-level verification:
- `uv run pytest tests/ --collect-only -q` → 280 tests collected, 0 errors
- `uv run ruff check` (all 5 files) → All checks passed
- `uv run pyright tests/conftest.py` → 0 errors, 0 warnings

---
*Phase: 03-live-game-tracking*
*Completed: 2026-04-27*
