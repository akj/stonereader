---
phase: 02-log-infrastructure
plan: 08
subsystem: testing

requires:
  - phase: 02-log-infrastructure
    provides: Engine + parser + watcher implementations needing real-Power.log validation

provides:
  - Real Power.log fixtures for engine/parser test suites (4 files, anonymized)
  - Capture procedure documentation enabling future re-capture after Hearthstone patches
  - Closure of LOG-01 (≥1s detection) and LOG-02 (PowerTaskList dedup) integration tests

affects: phase-03-live-game-tracking, future-fixture-recapture

tech-stack:
  added: []
  patterns:
    - "Captured fixtures live under tests/fixtures/log/ (singular) — conftest FIXTURE_DIR convention"
    - "Anonymization: BattleTag -> Player1/Player2; AI characters (e.g. The Innkeeper) are not PII"
    - "Truncation at \\n boundary (head -c | sed '$d') — partial last line would trigger RegexParsingError"

key-files:
  created:
    - tests/fixtures/log/match_start.log
    - tests/fixtures/log/mid_game.log
    - tests/fixtures/log/game_end.log
    - tests/fixtures/log/reconnect.log
    - .planning/phases/02-log-infrastructure/02-FIXTURE-CAPTURE.md
  modified: []

key-decisions:
  - "Skipped optional battlegrounds.log — not required for v1 test suite, captured matches were standard Casual format"
  - "Reconnect fixture captures 2 sequential matches (not the actual reconnect re-dump pattern). Pitfall 7 fixture is deferred to Phase 3+ when force-quit + reconnect can be replayed cleanly"
  - "Fixtures truncated to 50/150/200/250 KB respectively (within plan budget). Source captures were 0.2-6 MB; truncation preserves enough lines for the existing engine tests (test_tick_under_50ms uses first 1000 lines)"

patterns-established:
  - "Capture-and-anonymize procedure documented in 02-FIXTURE-CAPTURE.md for future re-runs"
  - "Engine tests use `power_log_fixture(name)` helper from conftest — pytest.skip when missing, pass when present"

requirements-completed: [LOG-01, LOG-02]

duration: ~30min (procedure doc + capture + anonymization + truncation)
completed: 2026-04-26
---

# Phase 2 Plan 08: Power.log Fixture Capture Summary

**4 anonymized Hearthstone Power.log fixtures (51 KB-255 KB) committed under tests/fixtures/log/, unblocking 3 previously-skipped engine tests and closing integration-test coverage for LOG-01 + LOG-02**

## Performance

- **Duration:** ~30 minutes (Task 2 doc + Task 1 capture + truncation/anonymization + Task 3 verification)
- **Completed:** 2026-04-26
- **Tasks:** 3 (Task 1 human-action capture, Task 2 capture-procedure doc, Task 3 verification)
- **Files created:** 5

## Accomplishments

- 4 captured Power.log fixtures committed under `tests/fixtures/log/` (anonymized, size-budgeted)
- `02-FIXTURE-CAPTURE.md` documents the capture procedure for future re-captures after Hearthstone patches
- Previously-skipped engine tests now PASS (not SKIP):
  - `test_mid_game_fixture_emits_expected_events`
  - `test_dual_source_fixture_no_duplicates`
  - `test_tick_under_50ms`
- Full repo: 242 passed, 0 skipped (was 235 passed + 7 skipped)

## Task Commits

1. **Task 2: Document capture procedure** — `1e90401` (docs)
2. **Task 1: Capture, anonymize, truncate, place fixtures** — `<this commit>` (test) — see git log for the actual commit hash
3. **Task 3: Verification (no separate commit)** — All engine tests PASS; full suite green

## Fixture Inventory

| File | Size | CREATE_GAMEs | Scenario |
|------|------|--------------|----------|
| `match_start.log` | 51 KB | 1 | Mulligan + initial setup, no PLAYSTATE yet |
| `mid_game.log` | 153 KB | 1 | Match in progress, no PLAYSTATE WON/LOST |
| `game_end.log` | 204 KB | 1 + PLAYSTATE pair | One complete match (concession) |
| `reconnect.log` | 255 KB | 2 sequential | Two completed matches in sequence |

Total fixture footprint: 663 KB.

## Decisions Made

### Anonymization scope

- `Eyeronic#11298` (user's BattleTag) → `Player1` across all four files
- `The Innkeeper` (AI opponent in Practice mode) is a Hearthstone character, not real PII — not anonymized
- No `BnetID=<hi> <lo>` lines present in these captures (this format applies to ranked / multiplayer matches only)

### Truncation strategy

- Each file capped at byte boundary corresponding to its plan size budget (50/150/200/250 KB)
- `head -c <bytes> | sed '$d'` removes the partial trailing line, ensuring `\n` termination
- Verified each fixture still contains ≥ 1 `CREATE_GAME` (drives `GameStarted` event in tests)
- Verified `mid_game.log` has ≥ 1000 lines (used by `test_tick_under_50ms`)

### Reconnect coverage gap (deferred)

Plan called for `reconnect.log` to exercise Pitfall 7 — reconnect after force-quit re-dumps the full game state, producing **consecutive `CREATE_GAME` blocks without an intervening `PLAYSTATE WON/LOST`**. The captured `reconnect.log` contains 2 `CREATE_GAME`s, but they belong to two separate sequential matches (the user did not force-quit + reconnect mid-game during capture).

**Impact:** No engine test currently asserts the reconnect re-dump invariant, so Phase 2 is not blocked. Phase 3+ tests that need this scenario should re-capture with a deliberate force-quit step (procedure documented in `02-FIXTURE-CAPTURE.md` step 6).

**Tracking:** Flagged in this summary's `key-decisions` and the plan's threat model (T-2-FIXTURE-DRIFT — accepted residual risk).

### Battlegrounds (optional fixture) skipped

- Not required by Phase 2 tests
- Optional in plan frontmatter (`optional: true`)
- Re-capture procedure available in `02-FIXTURE-CAPTURE.md` if Phase 3+ needs Battlegrounds stress coverage

## Files Created/Modified

- `tests/fixtures/log/match_start.log` — 51 KB, 1 short conceded match (mulligan + setup)
- `tests/fixtures/log/mid_game.log` — 153 KB, 1 mid-match snapshot
- `tests/fixtures/log/game_end.log` — 204 KB, 1 complete match
- `tests/fixtures/log/reconnect.log` — 255 KB, 2 sequential matches
- `.planning/phases/02-log-infrastructure/02-FIXTURE-CAPTURE.md` — re-capture procedure with anonymization + truncation steps + when-to-recapture triggers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Path correction] Fixtures pushed to wrong directory by user**

- **Found during:** Task 1 (after user push)
- **Issue:** User committed fixtures to `tests/fixtures/logs/` (plural) instead of `tests/fixtures/log/` (singular). The `conftest.py` `FIXTURE_DIR = Path(...) / "fixtures" / "log"` looks for the singular form, so tests would not have located the fixtures.
- **Fix:** Truncated, anonymized, and rewrote each file under `tests/fixtures/log/`. Removed the original `tests/fixtures/logs/` directory.
- **Files modified:** `tests/fixtures/log/*.log` (created), `tests/fixtures/logs/*.log` (deleted)
- **Verification:** `uv run pytest tests/test_services/test_engine.py -v` reports 4 PASSED (was 3 SKIPPED)

**2. [Rule 1 — Size compliance] Source captures were 0.2-6 MB, way over plan budget**

- **Found during:** Task 1 (after user push)
- **Issue:** Plan budgets are 30-50 KB / 80-150 KB / 100-200 KB / 150-250 KB. User's captures were 215 KB / 2.5 MB / 5.4 MB / 6.0 MB. Total of 14.1 MB committed to repo would bloat clones.
- **Fix:** Truncated each file at byte boundary (`head -c $bytes`) and dropped the partial trailing line with `sed '$d'` to preserve `\n` termination. Files now fit within plan budgets (51/153/204/255 KB).
- **Files modified:** All 4 fixtures
- **Verification:** `wc -c` confirms within budget; `tail` confirms `\n`-terminated

**3. [Rule 1 — PII scrubbing] Source captures contained user's real BattleTag**

- **Found during:** Task 1 (after user push)
- **Issue:** Files contained `PlayerName=Eyeronic#11298` (user's real BattleTag). Plan acceptance criterion requires anonymization before commit.
- **Fix:** `sed 's/Eyeronic#11298/Player1/g'` applied during truncation
- **Files modified:** All 4 fixtures
- **Verification:** `grep "Eyeronic" tests/fixtures/log/*.log` returns empty

---

**Total deviations:** 3 auto-fixed (all Rule 1 — path/size/PII compliance).
**Impact on plan:** No scope creep — all fixes were required by the plan's acceptance criteria. The user committed raw captures and asked for examination + anonymization + scenario coverage check, which is exactly what these auto-fixes do.

## Issues Encountered

- **Reconnect re-dump pattern not captured.** User did not force-quit Hearthstone mid-match during capture. The `reconnect.log` fixture covers "2 sequential matches" rather than "1 match interrupted + reconnected". Documented as accepted residual coverage gap; will be addressed in a future re-capture if Phase 3+ tests require it.

## User Setup Required

None — fixtures are committed; future re-captures follow `02-FIXTURE-CAPTURE.md`.

## Next Phase Readiness

Phase 2 verification can now run with full integration-test coverage. LOG-01 (line detection) and LOG-02 (dual-source dedup) are exercised against real Hearthstone Power.log content. Phase 3 (Live Game Tracking) can build on these fixtures and add scenario-specific captures (e.g., dormant minions, BG combat sequences) using the documented procedure.

---
*Phase: 02-log-infrastructure*
*Completed: 2026-04-26*
