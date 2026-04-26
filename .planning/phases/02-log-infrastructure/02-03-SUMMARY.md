---
phase: 02-log-infrastructure
plan: 03
subsystem: services
tags:
  - log-path-discovery
  - process-detection
  - psutil
  - tdd
dependency-graph:
  requires:
    - 02-01 (Wave 0 — psutil dep + tests/test_services/conftest.py;
       not yet merged so Plan 02-03 bootstrapped its own subset)
  provides:
    - stonereader.services._log_path.discover_power_log_path
    - stonereader.services._process_detect.ProcessDetector
  affects:
    - pyproject.toml (psutil added)
    - uv.lock (regenerated)
    - tests/test_services/conftest.py (FakeClock, MockProcessDetector,
      power_log_fixture fixtures bootstrapped)
tech-stack:
  added:
    - psutil>=7.0,<8 (process enumeration; D-03)
  patterns:
    - clock injection (Callable[[], float]) for testable TTL caching
    - defensive try/except mirroring stonereader/speech_service.py
    - frozen-state-by-init (no mutation of cached results)
    - Path.startswith filter for path-traversal hygiene (T-2-01)
key-files:
  created:
    - stonereader/services/__init__.py
    - stonereader/services/_log_path.py
    - stonereader/services/_process_detect.py
    - tests/test_services/conftest.py
    - tests/test_services/test_log_path.py
    - tests/test_services/test_process_detect.py
  modified:
    - pyproject.toml (added psutil>=7.0,<8)
    - uv.lock (regenerated)
decisions:
  - "Initialize ProcessDetector._last_check with -float('inf') instead
     of 0.0 (RESEARCH.md skeleton) so the very first is_running() call
     always scans rather than returning the placeholder (False, None)
     default — required by the test_caches_within_ttl invariant."
  - "Adopt Path-prefix filter ('Hearthstone_') over glob to prevent
     path-traversal entries (e.g. '..') from leaking into the
     subdirectory scan (T-2-01 mitigation)."
  - "Inject `clock: Callable[[], float]` into ProcessDetector instead
     of monkeypatching time.monotonic globally — keeps tests
     deterministic without affecting other test files."
  - "Bootstrapped Plan 02-01's psutil dependency and conftest.py
     fixtures inline (Rule 3 deviation) since 02-01 had not been
     merged into this worktree's base. Limited bootstrap scope to
     what 02-03 actually needs (psutil only, NOT hslog; conftest.py,
     NOT the other 7 test stub files)."
metrics:
  duration: 5m
  tasks: 2
  files: 6
  completed: 2026-04-26T01:10:42Z
---

# Phase 02 Plan 03: Power.log Path Discovery and Process Detection Summary

Implemented two pure-data utilities in the new `stonereader/services/`
package: `discover_power_log_path()` (D-12) for locating Hearthstone's
live Power.log file and `ProcessDetector` (D-03) for detecting whether
Hearthstone.exe is running with TTL-cached scans. Both follow TDD with
RED-then-GREEN per task; 14 tests pass and no other suites regressed.

## What Was Done

### Task 1 — `_log_path.discover_power_log_path()` (D-12)

`stonereader/services/_log_path.py` (122 lines) implements the four-step
strategy from CONTEXT.md D-12:

1. Caller-supplied `install_dir` (typically derived from the running
   Hearthstone process by `ProcessDetector.get_install_dir()`).
2. `HKLM\SOFTWARE\Blizzard\Hearthstone\InstallPath` via `winreg`
   (Windows only; gracefully returns None on POSIX so tests can run
   cross-platform). Both 64-bit and `WOW6432Node` hives are tried.
3. Within `<install_dir>/Logs/`, pick the newest
   `Hearthstone_YYYY_MM_DD_HH_MM_SS/Power.log` subdirectory by mtime.
   Filtered by `entry.name.startswith("Hearthstone_")` so non-Hearthstone
   subdirs (and traversal entries like `..`) are skipped.
4. Fall back to the flat `Logs/Power.log` for older Hearthstone format.

Returns `Optional[Path]`; `None` when nothing matches.

The acceptance test `test_picks_newest_subdirectory_by_mtime` proves
the mtime selection by writing two `Hearthstone_*` directories and
backdating one with `os.utime`. Two extra coverage tests (beyond the
plan's required three) catch:
- subdirs without `Power.log` are skipped
- non-Hearthstone-prefixed subdirs are ignored (path-traversal hygiene
  for T-2-01)

### Task 2 — `_process_detect.ProcessDetector` (D-03)

`stonereader/services/_process_detect.py` (100 lines) wraps psutil with
a TTL-cached scanner:

- `is_running()` returns `(bool, Optional[psutil.Process])`. First call
  always scans (the constructor seeds `_last_check` with `-inf` so the
  initial monotonic-now never falls inside the cache window). Subsequent
  calls within `cache_ttl_seconds` (default 2.0s) reuse the cached
  result without re-enumerating processes.
- `get_install_dir()` returns `Path(proc.exe()).parent` or `None`. Used
  by `_log_path.discover_power_log_path()` per D-12 step 1.
- `invalidate_cache()` forces the next `is_running()` call to re-scan.
  Tracker uses this after a process-gone reset so the next tick picks
  up a fresh Hearthstone restart immediately.
- Per-process `try/except (psutil.NoSuchProcess, psutil.AccessDenied)`
  keeps a transient race from killing the entire scan
  (T-2-Resilience). `process_iter` itself is wrapped in
  `except Exception` plus `logger.exception` so a catastrophic psutil
  failure logs but doesn't propagate.

Eight tests cover detection, absence, TTL caching with `FakeClock`,
case-insensitive matching (Pitfall A1), install-dir derivation,
install-dir-when-absent, NoSuchProcess resilience, and the
`invalidate_cache` rescan.

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `stonereader/services/__init__.py` | 8 | Empty package barrel |
| `stonereader/services/_log_path.py` | 122 | D-12 path discovery |
| `stonereader/services/_process_detect.py` | 100 | D-03 process detection |
| `tests/test_services/conftest.py` | 74 | Shared fixtures (FakeClock, MockProcessDetector, power_log_fixture) |
| `tests/test_services/test_log_path.py` | 82 | 6 tests |
| `tests/test_services/test_process_detect.py` | 133 | 8 tests |
| `pyproject.toml` | (modified) | Added `psutil>=7.0,<8` |
| `uv.lock` | (regenerated) | psutil 7.2.2 pinned |

**Total new lines:** 519 across 6 new files.
**Test count:** 14 new tests; all 183 tests in the project still pass.

## Tests

```
$ uv run pytest tests/test_services/test_log_path.py tests/test_services/test_process_detect.py -v
14 passed in 0.02s

$ uv run pytest tests/
183 passed in 0.81s
```

| Test file | Count | Coverage |
|-----------|-------|----------|
| `test_log_path.py` | 6 | mtime selection, flat fallback, no-Logs-dir, no-Power.log, subdir-without-log, non-Hearthstone-prefix filter |
| `test_process_detect.py` | 8 | detection, absence, TTL cache, case-insensitive, install-dir, install-dir-when-absent, NoSuchProcess resilience, invalidate_cache |

Plan success criterion was "7+ tests pass"; delivered 14.

## Tooling

```
$ uv run ruff check stonereader/services/ tests/test_services/
All checks passed!

$ uv run ruff format --check stonereader/services/ tests/test_services/
All files already formatted

$ uv run pyright stonereader/services/_log_path.py stonereader/services/_process_detect.py
0 errors, 0 warnings, 0 informations
```

## Decisions

### `_last_check` initialised to `-float('inf')` (deviation from RESEARCH.md skeleton)

The RESEARCH.md skeleton (line 602) seeds `_last_check = 0.0` and
`_last_result = (False, None)`. With that default and any non-trivial
`time.monotonic()` value, the first call's `now - 0.0 < self._ttl`
check could spuriously return `(False, None)` from cache. The plan
explicitly calls this out (see Task 2 action note). I used
`-float('inf')` so the first call's `now - (-inf) = +inf >= ttl`
always falls outside the cache window and triggers a real scan.
`test_caches_within_ttl` asserts `call_count == 1` after the very
first `is_running()` invocation, so the deviation is validated.

### Path-prefix filter over glob (T-2-01)

`_newest_session_log` filters entries with
`entry.name.startswith("Hearthstone_")` rather than
`logs_dir.glob("Hearthstone_*/Power.log")`. The startswith filter
naturally rejects `..`, `Logs/.`, and any directory whose name doesn't
begin with the literal prefix. Combined with `entry.is_dir()` and
`power_log.exists()` checks, this satisfies T-2-01's "no path
traversal" mitigation without explicit normalisation. The threat model
notes both sources of `install_dir` (psutil `proc.exe()` parent and
HKLM registry) are user-owned trust boundaries, so the function is
reading user-controlled paths, not honoring untrusted external input.

### `clock: Callable[[], float]` injection

The plan's interface block requires clock injection. Without it,
`test_caches_within_ttl` would have to monkeypatch `time.monotonic`
globally — risky in a pytest shared-state environment and brittle if
unrelated test code samples wall-clock time. The `clock` parameter
defaults to `time.monotonic` so production code is unaffected.

### Cross-platform `get_install_dir` test

`test_get_install_dir_returns_parent_of_exe` originally used a
hard-coded `r"C:\Program Files\Hearthstone\Hearthstone.exe"` literal.
On Linux runners, `pathlib.Path(...)` selects `PosixPath` and treats
the entire string as a single filename, leaving `.parent` empty. The
test was rewritten to use `tmp_path / "Hearthstone" / "Hearthstone.exe"`
so it parses correctly on both POSIX and Windows. Production behaviour
is unchanged; the Windows registry lookup still returns Windows-style
paths, and `pathlib.Path` selects `WindowsPath` there.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bootstrap psutil dependency and conftest.py**

- **Found during:** Plan startup, before Task 1.
- **Issue:** Plan 02-03 declares `depends_on: [02-01]` and the worktree
  was based on commit fc69291 — Plan 02-01 (Wave 0, which establishes
  `psutil` in pyproject.toml and `tests/test_services/conftest.py`)
  had not been merged. Without these, the planned tests would have
  failed to collect (no `fake_clock` fixture, no psutil import).
- **Fix:** Added `psutil>=7.0,<8` to pyproject.toml via `uv add`;
  created `tests/test_services/conftest.py` verbatim from Plan 02-01
  Task 2 (FakeClock, MockProcessDetector, power_log_fixture,
  fake_clock, mock_process_detector). Bootstrap was scoped to ONLY the
  Plan 02-01 deliverables that 02-03 needs — hslog and the other six
  test stub files (test_log_config, test_parser, test_engine,
  test_watcher, test_tracker, test_logging_config) remain Plan 02-01's
  responsibility.
- **Files modified:** `pyproject.toml`, `uv.lock`,
  `tests/test_services/conftest.py`.
- **Commit:** `c682b8b` (`chore(02-03): bootstrap psutil dependency
  and test scaffolding`).

### Test refinement (not a deviation, just an adjustment)

`test_get_install_dir_returns_parent_of_exe` was rewritten between
RED commit and GREEN commit to use `tmp_path` instead of a Windows-
style literal. This was a test-code-only change to satisfy
cross-platform Path parsing; production code was already correct.

## Threat Model Verification

| Threat ID | Component | Disposition | Verified by |
|-----------|-----------|-------------|-------------|
| T-2-01 | `_log_path` path traversal | mitigate | `test_non_hearthstone_subdirs_are_ignored` covers the prefix filter; the function is read-only; `entry.is_dir()` and `power_log.exists()` are exercised by the green path. |
| T-2-01b | HKLM read | accept | No special permission required; non-secret value. |
| T-2-DOS | psutil.process_iter cost | mitigate | `test_caches_within_ttl` proves at most one enumeration per TTL window. |
| T-2-Resilience | psutil.NoSuchProcess race | mitigate | `test_skips_processes_that_disappear_during_iteration` exercises the per-process try/except. |

No new threat surface introduced beyond what the plan's
`<threat_model>` already covered.

## Notes

- **Windows-only registry path** — `_path_from_registry()` returns
  `None` immediately when `sys.platform != "win32"` and also when the
  `winreg` import fails. This lets tests run unmodified on Linux and
  macOS CI runners; production behaviour is unaffected.
- **Pitfall 1 mitigation lives at the caller** — D-12 mandates "must
  call every tick". `discover_power_log_path()` is cheap (one
  directory listing + a few `stat` calls), so callers are free to
  invoke it per Timer tick. The function deliberately does not cache
  its result so a Hearthstone restart with a new
  `Logs/Hearthstone_*/` directory is picked up on the next tick.
- **TDD gate compliance** — Two RED commits (`9d3c934`, `ce9a826`)
  precede the corresponding GREEN commits (`aa416f8`, `642f2fa`). One
  bootstrap chore commit (`c682b8b`) precedes both, isolating the
  Rule 3 deviation from the substantive feature work.

## Self-Check: PASSED

- [x] `stonereader/services/__init__.py` exists
- [x] `stonereader/services/_log_path.py` exists
- [x] `stonereader/services/_process_detect.py` exists
- [x] `tests/test_services/conftest.py` exists
- [x] `tests/test_services/test_log_path.py` exists
- [x] `tests/test_services/test_process_detect.py` exists
- [x] `pyproject.toml` modified with psutil dep
- [x] Commit `c682b8b` (bootstrap chore) exists
- [x] Commit `9d3c934` (RED test_log_path) exists
- [x] Commit `aa416f8` (GREEN _log_path) exists
- [x] Commit `ce9a826` (RED test_process_detect) exists
- [x] Commit `642f2fa` (GREEN _process_detect) exists
- [x] 14 tests pass; full suite (183 tests) green
- [x] ruff check + format clean; pyright 0 errors
