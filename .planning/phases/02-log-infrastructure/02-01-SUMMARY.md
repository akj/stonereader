---
phase: 02-log-infrastructure
plan: 01
subsystem: testing
tags: [pytest, hslog, psutil, fixtures, scaffolding, wave-0]

# Dependency graph
requires:
  - phase: 01-deck-management
    provides: tests/conftest.py MockSpeechService pattern (mirrored by MockProcessDetector)
provides:
  - hslog 1.18.0 and psutil 7.2.2 pinned in pyproject.toml + uv.lock
  - tests/test_services/conftest.py with FakeClock, MockProcessDetector, power_log_fixture
  - 8 stub test files covering LOG-01..05 with 29 importorskip-guarded test functions
  - Test name conventions matching 02-VALIDATION.md exactly so per-task verify commands resolve once real bodies land
affects: [02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08]

# Tech tracking
tech-stack:
  added: [hslog>=1.18.0, psutil>=7.0]
  patterns:
    - "pytest.importorskip + pytest.skip stub pattern: lets stubs commit before production module exists, converts to real test by replacing skip line"
    - "FakeClock test double: monotonic time controlled by .advance() for TTL cache verification (D-03)"
    - "MockProcessDetector pattern mirrors MockSpeechService — bypass parent __init__ to avoid touching real psutil"
    - "power_log_fixture loader skips gracefully when fixture missing — Wave 0 commits cleanly before Wave 5 fixture capture"

key-files:
  created:
    - tests/test_services/conftest.py
    - tests/test_services/test_engine.py
    - tests/test_services/test_log_config.py
    - tests/test_services/test_log_path.py
    - tests/test_services/test_logging_config.py
    - tests/test_services/test_parser.py
    - tests/test_services/test_process_detect.py
    - tests/test_services/test_tracker.py
    - tests/test_services/test_watcher.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "psutil chosen over pywin32 for D-03 process detection — avoids Windows-only imports leaking into cross-platform test runs"
  - "No tests/test_services/__init__.py created — mirrors existing pytest auto-discovery convention used by tests/"
  - "Each stub uses pytest.importorskip on its target services._<module> followed by pytest.skip — stubs report SKIPPED until target exists, then a one-line edit (remove the skip) converts them to real tests"

patterns-established:
  - "Stub test pattern: pytest.importorskip(target) → pytest.skip(reference) — collection-safe before module exists"
  - "Fixture loader skip-on-missing: power_log_fixture skips test if fixture file absent (Wave 5 captures real Power.log)"
  - "Test double init bypass: MockProcessDetector skips real ProcessDetector.__init__ (mirrors MockSpeechService)"

requirements-completed: [LOG-01, LOG-02, LOG-03, LOG-04, LOG-05]

# Metrics
duration: 3m
completed: 2026-04-26
---

# Phase 2 Plan 01: Log Infrastructure — Wave 0 Test Scaffolding Summary

**hslog 1.18.0 + psutil 7.2.2 pinned, plus 29 importorskip-guarded stub tests across 8 service modules with FakeClock/MockProcessDetector test doubles**

## Performance

- **Duration:** 3m 9s
- **Started:** 2026-04-26T01:03:48Z
- **Completed:** 2026-04-26T01:06:57Z
- **Tasks:** 3
- **Files created:** 9
- **Files modified:** 2

## Accomplishments

- Phase 2 dependencies (`hslog>=1.18.0,<2`, `psutil>=7.0,<8`) installed and pinned with upper bounds; uv.lock regenerated
- Shared `tests/test_services/conftest.py` provides `FakeClock`, `MockProcessDetector`, and `power_log_fixture` loader — all consumed by Wave 1+ tests
- 8 stub test files created covering every LOG-01..05 row from `02-VALIDATION.md` "Phase Requirements -> Test Map" (29 tests total, exceeds the planned ≥27)
- `uv run pytest tests/test_services/ -x` reports `29 skipped` cleanly; `uv run pytest tests/ -v` reports `169 passed, 29 skipped` (existing tests unaffected)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add hslog and psutil dependencies** — `00f601b` (chore)
2. **Task 2: Create tests/test_services/conftest.py with shared fixtures** — `6843eb0` (test)
3. **Task 3: Create test stub files for all LOG-XX requirements** — `6527976` (test)

**Plan metadata commit:** to be added after this SUMMARY.md is written.

## Files Created/Modified

### Created
- `tests/test_services/conftest.py` (71 lines) — `FakeClock`, `MockProcessDetector`, `power_log_fixture`, `fake_clock`, `mock_process_detector` fixtures; `FIXTURE_DIR` resolved to `tests/fixtures/log/`
- `tests/test_services/test_log_config.py` — 3 stubs targeting `stonereader.services._log_config` (LOG-04)
- `tests/test_services/test_log_path.py` — 3 stubs targeting `stonereader.services._log_path` (D-12)
- `tests/test_services/test_process_detect.py` — 3 stubs targeting `stonereader.services._process_detect` (D-03)
- `tests/test_services/test_parser.py` — 3 stubs targeting `stonereader.services._parser` (LOG-02)
- `tests/test_services/test_engine.py` — 4 stubs targeting `stonereader.services._engine` (LOG-01/02 integration)
- `tests/test_services/test_watcher.py` — 6 stubs targeting `stonereader.services._watcher` (LOG-01, LOG-03)
- `tests/test_services/test_tracker.py` — 4 stubs targeting `stonereader.services._tracker` (LOG-05/D-19)
- `tests/test_services/test_logging_config.py` — 3 stubs targeting `stonereader.services._logging_config` (D-16)

### Modified
- `pyproject.toml` — added `hslog>=1.18.0,<2` and `psutil>=7.0,<8` to `[project] dependencies`
- `uv.lock` — regenerated by `uv add`

## Decisions Made

- **Removed unused `import time`** from the conftest template — Ruff F401 would have failed CI. The plan's verbatim template included `import time` but `FakeClock.monotonic` returns `self._now` directly with no `time` API access; the import was dead. (See Deviations below.)
- All other code matches the plan's verbatim template exactly. No `__init__.py` was added to `tests/test_services/` — mirrors the existing `tests/` pytest auto-discovery convention. (Note: `tests/__init__.py` exists but is empty/single-line; pytest collection works without one in `tests/test_services/` because pytest's default rootdir-and-conftest discovery picks the package up from the conftest presence.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `import time` from conftest.py**
- **Found during:** Task 2 (conftest creation)
- **Issue:** Plan provided a verbatim template that included `import time`, but `FakeClock` uses no `time` API — it stores monotonic time as a plain float advanced by `.advance()`. Ruff F401 reported the unused import. CLAUDE.md mandates `uv run ruff check .` passes (project-wide convention).
- **Fix:** Removed the `import time` line. `FakeClock.monotonic()` already returned `self._now` directly; no behavioral change.
- **Files modified:** `tests/test_services/conftest.py`
- **Verification:** `uv run ruff check tests/test_services/conftest.py` → "All checks passed!"
- **Committed in:** `6843eb0` (Task 2 commit — fix applied before commit)

---

**Total deviations:** 1 auto-fixed (1 bug — unused import)
**Impact on plan:** No scope creep. Pure lint hygiene; behavior identical. Wave 1+ tests that depend on `FakeClock` are unaffected.

## Issues Encountered

- **Python version mismatch (informational, not blocking):** `uv sync` provisioned the worktree's `.venv` with CPython 3.14.0 instead of the project's documented 3.12.x. This is consistent with `requires-python = ">=3.12"` so the build is valid. All 169 existing tests pass on 3.14.0; the 29 new stubs skip cleanly. No action required, but worth flagging for the wider team in case 3.12-only patterns surface later in Phase 2.

## TDD Gate Compliance

This plan is `type: execute` (scaffolding only — `nyquist_compliant: false` per frontmatter), not `type: tdd`. The stub tests are placeholders that target modules that do not yet exist; they all skip via `pytest.importorskip` until Plans 02-08 land their production modules. The RED gate is deferred to each subsequent plan, where stubs will be replaced with real failing tests before implementation.

## User Setup Required

None — no external service configuration required. Phase 2 dependencies install via `uv sync`.

## Next Phase Readiness

**Ready for Wave 1 (Plan 02 + Plan 03):**
- `hslog` and `psutil` installable and importable in CI
- `tests/test_services/conftest.py` fixtures ready for consumption by `test_logging_config.py`, `test_log_config.py`, `test_log_path.py`, `test_process_detect.py`
- Per-task verify commands in `02-VALIDATION.md` resolve to real test files (no more "MISSING" rows for stub paths)
- `power_log_fixture` skip-on-absent contract lets fixture-dependent tests in Wave 3 (Plan 06) commit before Wave 5 (Plan 08) captures actual `Power.log` files

**Blockers:** None for Wave 1. Wave 3 fixture-dependent tests (`test_engine.py::test_mid_game_*`, `test_dual_source_*`, `test_tick_under_50ms`) will skip until Plan 08 captures real fixtures — this is by design and documented in `02-VALIDATION.md` "Wave 0 Requirements".

## Self-Check: PASSED

Verified post-write:

- `tests/test_services/conftest.py` — FOUND
- `tests/test_services/test_log_config.py` — FOUND
- `tests/test_services/test_log_path.py` — FOUND
- `tests/test_services/test_process_detect.py` — FOUND
- `tests/test_services/test_parser.py` — FOUND
- `tests/test_services/test_engine.py` — FOUND
- `tests/test_services/test_watcher.py` — FOUND
- `tests/test_services/test_tracker.py` — FOUND
- `tests/test_services/test_logging_config.py` — FOUND
- Commit `00f601b` (Task 1) — FOUND in `git log`
- Commit `6843eb0` (Task 2) — FOUND in `git log`
- Commit `6527976` (Task 3) — FOUND in `git log`
- `uv run pytest tests/test_services/` — 29 skipped, 0 failed
- `uv run pytest tests/` — 169 passed, 29 skipped

---
*Phase: 02-log-infrastructure*
*Plan: 01*
*Completed: 2026-04-26*
