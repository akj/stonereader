---
phase: 02-log-infrastructure
plan: 02
subsystem: infra
tags: [logging, configparser, rotatingfilehandler, log.config, hearthstone]

requires:
  - phase: 02-log-infrastructure
    provides: "Plan 01 (Wave 0) was scheduled to scaffold tests/test_services/conftest.py and dependency pins. In this worktree, that scaffolding had not yet been merged from the parallel Plan 01 worktree at execution time, so the two test files were authored directly as real (non-stub) tests."
provides:
  - "stonereader/services/__init__.py — package barrel (intentionally empty docstring; Plan 04 + Plan 07 expand the public API)"
  - "stonereader/services/_logging_config.py — D-16 stdlib logging setup (configure_logging())"
  - "stonereader/services/_log_config.py — D-11 idempotent Hearthstone log.config bootstrap (ensure_log_config(), log_config_path())"
  - "tests/test_services/test_logging_config.py — 3 real tests (creates dir/file, idempotent, STONEREADER_DEBUG env)"
  - "tests/test_services/test_log_config.py — 4 real tests (creates absent, preserves siblings, idempotent return, LOCALAPPDATA-rooted path)"
affects:
  - "02-04 (events) — will import logging.getLogger(__name__) and rely on configure_logging() at app entry"
  - "02-06 (watcher) — depends on D-04 catch-and-log-on-tick-error, which presupposes configure_logging() ran"
  - "02-07 (tracker) — wires configure_logging() and ensure_log_config() at app startup"
  - "02-08 (app integration) — calls both bootstrap functions exactly once"

tech-stack:
  added:
    - "stdlib logging (file + console root handlers)"
    - "stdlib logging.handlers.RotatingFileHandler (2MB cap, 3 backups)"
    - "stdlib configparser.RawConfigParser with optionxform=str"
  patterns:
    - "Idempotent-with-changed-flag bootstrap (mirrors db.init_db's check-then-act control flow)"
    - "Module-level Path constant (LOG_DIR) so tests can monkeypatch redirect without subprocess isolation"
    - "Handler-class deduplication for safe double configure_logging() — RotatingFileHandler vs non-rotating StreamHandler discriminator"

key-files:
  created:
    - "stonereader/services/__init__.py (1 line)"
    - "stonereader/services/_logging_config.py (61 lines)"
    - "stonereader/services/_log_config.py (70 lines)"
    - "tests/test_services/test_logging_config.py (76 lines)"
    - "tests/test_services/test_log_config.py (69 lines)"
  modified: []

key-decisions:
  - "Added a 4th test (test_log_config_path_uses_localappdata) beyond the plan's 3 named tests because log_config_path() is listed in the plan frontmatter `truths` and acceptance criteria (`grep -c \"def log_config_path\"` >= 1) — testing it directly closes the obvious gap."
  - "Excluded RotatingFileHandler when checking for an existing console StreamHandler (RotatingFileHandler subclasses StreamHandler, so naive isinstance(StreamHandler) would falsely report a console handler is already present after only the file handler was added)."
  - "Added an autouse fixture (_reset_root_logger) to test_logging_config.py that snapshots/restores root logger handlers + level around each test, preventing handler leakage between tests in the shared process."

patterns-established:
  - "TDD per task: RED commit (failing test) → GREEN commit (implementation) — 4 commits across 2 tasks."
  - "Frozen module constants (LOG_DIR, LOG_FILE_NAME, REQUIRED_POWER_SECTION) at module top so tests can monkeypatch.setattr() them cleanly."
  - "ensure_*_path() helpers separate from ensure_*() side-effects — testable independently."

requirements-completed: [LOG-04]

duration: 4min
completed: 2026-04-25
---

# Phase 2 Plan 02: Logging + log.config Bootstrap Summary

**Stdlib logging configured with rotating file + console handlers, plus idempotent Hearthstone log.config writer that preserves HDT/Firestone sections.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-26T01:07:09Z
- **Completed:** 2026-04-26T01:11:12Z
- **Tasks:** 2 (both TDD)
- **Files created:** 5 (3 production, 2 test)
- **Files modified:** 0

## Accomplishments

- `configure_logging()` produces a root logger with a 2MB-rotating file handler at `~/.stonereader/stonereader.log` (matches existing `db.py` directory pattern) and a console mirror; second call is a no-op (handler dedup).
- `STONEREADER_DEBUG=1` switches the root logger to DEBUG; any other value (or unset) keeps INFO.
- `ensure_log_config(path)` writes the required `[Power]` section with all 5 keys (LogLevel=1, FilePrinting=True, ConsolePrinting=False, ScreenPrinting=False, Verbose=True), and preserves any other existing sections (HDT's `[Achievements]`, `[FullScreenFX]`, etc.) — Pitfall 5 verified by test.
- `ensure_log_config()` returns False on the second call when the file is already correct (idempotent change-detection).
- `log_config_path()` resolves to `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config` on Windows and falls back to `~/AppData/Local/...` when `LOCALAPPDATA` is unset (so tests can run on Linux/macOS hosts).
- 7 new tests, all passing (3 logging + 4 log.config). Full suite 176/176 green.

## Task Commits

1. **Task 1 RED: failing tests for configure_logging** — `99401ee` (test)
2. **Task 1 GREEN: implement configure_logging()** — `bff1aec` (feat)
3. **Task 2 RED: failing tests for ensure_log_config** — `f62591f` (test)
4. **Task 2 GREEN: implement ensure_log_config()** — `4a5a0ac` (feat)

(Plan metadata commit will be added by orchestrator after worktree merge.)

## Files Created/Modified

- `stonereader/services/__init__.py` — package barrel (docstring only; Plan 04/07 expand)
- `stonereader/services/_logging_config.py` — `configure_logging()`, `LOG_DIR`, `LOG_FILE_NAME`
- `stonereader/services/_log_config.py` — `ensure_log_config()`, `log_config_path()`, `REQUIRED_POWER_SECTION`
- `tests/test_services/test_logging_config.py` — 3 tests with autouse root-logger snapshot fixture
- `tests/test_services/test_log_config.py` — 4 tests using tmp_path filesystem isolation

## Decisions Made

- **D-16 implementation matched RESEARCH.md skeleton (lines 770-806) verbatim** with one logical refinement: the console-handler dedup check excludes `RotatingFileHandler` instances explicitly, because `RotatingFileHandler` is a `StreamHandler` subclass and a naive `isinstance(StreamHandler)` check would erroneously skip console-handler installation on the first call.
- **D-11 implementation matched RESEARCH.md skeleton (lines 808-856) verbatim** with one cross-platform refinement: `log_config_path()` falls back to `~/AppData/Local/...` when `LOCALAPPDATA` is unset, so tests can exercise the function on Linux without `monkeypatch.setenv` boilerplate.
- **Bonus test added for `log_config_path()`** (test_log_config_path_uses_localappdata) — the plan didn't enumerate this test but the function is in the public surface listed in plan frontmatter `truths` and acceptance criteria. Better to verify than omit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan 02-01 (Wave 0) artifacts not present in worktree base**
- **Found during:** Task 1 setup
- **Issue:** Plan 02-02 instructs "Convert Wave 0 stubs in test_logging_config.py to real green tests." Plan 02-01 owns those stubs and the `tests/test_services/conftest.py` shared fixtures, but its commits live in a separate parallel worktree (agent-a6edfa) and had not been merged into base `fc69291` before this executor was spawned. The `tests/test_services/` directory simply did not exist.
- **Fix:** Wrote the test files directly as real (non-stub) tests using the test specifications already provided in Plan 02-02's `<action>` block. The new tests don't reference `MockProcessDetector` or `FakeClock`, so the missing `conftest.py` is irrelevant for this plan's scope. Orchestrator will resolve any merge conflict in `tests/test_services/` when integrating Plan 02-01 + 02-02 worktrees (test files are disjoint: this plan owns `test_logging_config.py` + `test_log_config.py` with real bodies, Plan 02-01 owns the others as stubs).
- **Files modified:** `tests/test_services/test_logging_config.py` (created with real tests instead of stubs), `tests/test_services/test_log_config.py` (created with real tests instead of stubs).
- **Verification:** All 7 tests PASSED; full suite 176/176; ruff + pyright clean.
- **Committed in:** `99401ee` (RED for Task 1), `f62591f` (RED for Task 2).

**2. [Rule 1 - Auto-fix] Ruff F401 unused-import + format pass**
- **Found during:** Task 2 verify pass
- **Issue:** `test_log_config.py` had a residual `import pytest` line and one long string literal needed to be reflowed. Ruff flagged both.
- **Fix:** `uv run ruff check --fix` removed the unused import; `uv run ruff format` reflowed the multi-line string.
- **Files modified:** `tests/test_services/test_log_config.py`
- **Verification:** Re-ran tests (all 7 pass), ruff check + format check clean.
- **Committed in:** `4a5a0ac` (Task 2 GREEN; combined with the implementation commit because the format fix landed on the same iteration).

---

**Total deviations:** 2 auto-fixed (1 blocking dependency-not-yet-merged, 1 lint cleanup)
**Impact on plan:** Both auto-fixes were necessary for the plan to verify-clean. Production code matches the RESEARCH.md skeleton with only the documented logical refinements. No scope creep.

## Issues Encountered

None beyond the deviations noted above. Both TDD cycles ran cleanly (RED failed for the expected reasons — `ModuleNotFoundError`, not test-logic errors — then GREEN passed on the first implementation attempt).

## TDD Gate Compliance

The plan does not declare `type: tdd` at the plan level (each task is `tdd="true"` individually), so plan-level RED/GREEN/REFACTOR gate enforcement does not apply. Per-task TDD compliance:

| Task | RED commit | GREEN commit | REFACTOR? |
| ---- | ---------- | ------------ | --------- |
| 1    | `99401ee`  | `bff1aec`    | not needed |
| 2    | `f62591f`  | `4a5a0ac`    | not needed |

## Threat Surface

- **T-2-02 (Tampering — log.config shared INI):** Mitigated as planned. `RawConfigParser` + `optionxform=str` + change-detection idempotency. `test_preserves_other_sections` enforces Pitfall 5 — adding a `[Power]` section never strips `[Achievements]` / `[FullScreenFX]`.
- **T-2-DOS (Logging unbounded growth):** Mitigated. `RotatingFileHandler(maxBytes=2_000_000, backupCount=3)` caps total log size at 8MB.
- No new threat surface introduced beyond the entries already in the plan's `<threat_model>`.

## Self-Check: PASSED

Verified each artifact exists at HEAD:

- FOUND: `stonereader/services/__init__.py`
- FOUND: `stonereader/services/_logging_config.py`
- FOUND: `stonereader/services/_log_config.py`
- FOUND: `tests/test_services/test_logging_config.py`
- FOUND: `tests/test_services/test_log_config.py`

Verified each commit exists in `git log`:

- FOUND: `99401ee` (test RED Task 1)
- FOUND: `bff1aec` (feat GREEN Task 1)
- FOUND: `f62591f` (test RED Task 2)
- FOUND: `4a5a0ac` (feat GREEN Task 2)

Acceptance criteria — all met:

- `grep -c "def configure_logging" stonereader/services/_logging_config.py` == 1 ✓
- `grep -c "RotatingFileHandler" stonereader/services/_logging_config.py` >= 1 (6 occurrences) ✓
- `grep -c "STONEREADER_DEBUG" stonereader/services/_logging_config.py` >= 1 (2 occurrences) ✓
- `grep "Path.home() / \".stonereader\""` matches ✓
- `grep -c "def ensure_log_config" stonereader/services/_log_config.py` == 1 ✓
- `grep -c "def log_config_path" stonereader/services/_log_config.py` == 1 ✓
- `grep "RawConfigParser" stonereader/services/_log_config.py` matches ✓
- `grep "optionxform = str" stonereader/services/_log_config.py` matches ✓
- All 5 required `[Power]` keys present in `REQUIRED_POWER_SECTION` ✓
- `grep -c "pytest.skip" tests/test_services/test_logging_config.py` == 0 ✓
- `grep -c "pytest.skip" tests/test_services/test_log_config.py` == 0 ✓
- `uv run pytest tests/test_services/test_logging_config.py -x` exits 0, 3 PASSED ✓
- `uv run pytest tests/test_services/test_log_config.py -x` exits 0, 4 PASSED ✓
- `uv run pytest tests/ ` 176 PASSED, 0 failed ✓
- `uv run ruff check stonereader/services/ tests/test_services/` clean ✓
- `uv run pyright stonereader/services/ tests/test_services/` 0 errors ✓

## Next Phase Readiness

- LOG-04 fully covered. Ready for Plan 04 (events) and Plan 06 (watcher) to call `logging.getLogger(__name__)` without further bootstrapping.
- Plan 07 (tracker) / Plan 08 (app integration) will need to invoke `configure_logging()` and `ensure_log_config()` exactly once at app startup; both functions are already idempotent so accidental double-call is harmless.
- The `[Power]` section is the only section this plan touches; if Phase 3 needs other Hearthstone log streams (`[Achievements]`, `[Decks]`), extend `REQUIRED_POWER_SECTION` into a per-section dict, or split into `ensure_section(name, keys)`.

---
*Phase: 02-log-infrastructure*
*Completed: 2026-04-25*
