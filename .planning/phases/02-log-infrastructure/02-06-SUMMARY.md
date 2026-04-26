---
phase: 02-log-infrastructure
plan: 06
subsystem: services
tags: [wxpython, log-watcher, game-engine, utf-8, file-tail, event-stream]

# Dependency graph
requires:
  - phase: 02-04
    provides: GameEvent taxonomy, extended GameState/Hero/GameEntity/PlayedCard models
  - phase: 02-05
    provides: Internal Packet types, Parser wrapping hslog
provides:
  - "_LineReader: UTF-8 boundary-safe byte-to-line splitter (Pitfall 8)"
  - "GameEngine: consumes Packets, emits 11 typed GameEvent kinds, maintains frozen GameState (D-05/D-06/D-07)"
  - "PowerLogWatcher: wx.Timer-driven file tail with backward-scan, truncation reset, 100k buffer cap"
affects: [02-07-tracker, 03-live-tracking, 04-replay-viewer]

# Tech tracking
tech-stack:
  added:
    - "codecs.IncrementalDecoder (UTF-8 boundary buffer)"
    - "wx.Timer (D-01 polling driver)"
  patterns:
    - "Engine isolation: GameEngine has zero hslog and zero wx imports (D-10, reusable for Phase 4 replays)"
    - "Watcher exposes _do_tick() for direct test invocation; start() only wires the Timer"
    - "Frozen-state-out, mutable-state-in: engine keeps mutable internal dicts/lists; published GameState/PlayedCard tuples are reconstructed via dataclasses.replace"
    - "Backward-scan with overlap tail buffer to catch needle spanning chunk boundaries"

key-files:
  created:
    - "stonereader/services/_line_reader.py (41 LOC)"
    - "stonereader/services/_engine.py (424 LOC)"
    - "stonereader/services/_watcher.py (170 LOC)"
    - "tests/test_services/test_line_reader.py (57 LOC, 6 tests)"
  modified:
    - "stonereader/services/__init__.py (export GameEngine, PowerLogWatcher)"
    - "tests/test_services/test_engine.py (4 stubs -> 1 active + 3 fixture-skipping)"
    - "tests/test_services/test_watcher.py (6 stubs -> 6 active tests)"

key-decisions:
  - "Engine maintains internal mutable dicts/lists; only the published GameState (frozen) ever leaves the boundary"
  - "Watcher's _do_tick() is public-for-tests so tests bypass wx.Timer entirely; start() exists only for wiring the Timer in production"
  - "_handle_reset always clears partial-decode buffer AND offset (Pitfall 8)"
  - "Backward-scan uses an overlap tail buffer (size of CREATE_GAME_NEEDLE) to catch matches that span 4 KB chunk boundaries"
  - "DamageDealt only emitted inside ATTACK or POWER blocks (avoid emission storm during card-text effect resolution)"

patterns-established:
  - "Engine packet handler dispatch: isinstance chain in apply(), handler methods named _on_<packet_type>"
  - "Watcher 'tick error containment' (D-04): _tick wraps _do_tick in try/except logger.exception; the Timer keeps ticking"
  - "Two-write-test idiom for truncation: write empty bytes, observe truncation tick, then write new content (validates that observed truncation flushes the partial-decode buffer)"

requirements-completed: [LOG-01, LOG-02, LOG-03]

# Metrics
duration: 25min
completed: 2026-04-25
---

# Phase 02 Plan 06: Watcher + Engine Summary

**UTF-8 boundary-safe `_LineReader`, packet-consuming `GameEngine` (frozen-state out, hslog-free), and `PowerLogWatcher` with 150 ms wx.Timer tail, backward-scan to last CREATE_GAME, and truncation/buffer-cap defenses.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 (TDD: test commit + impl commit each)
- **Files created:** 3 production modules + 1 new test file
- **Files modified:** 3 (services `__init__.py`, two existing test stubs)
- **Tests added:** 13 (6 line_reader + 4 engine + 6 watcher; 3 engine tests skip pending Wave 5 fixtures by design)
- **Full-suite result:** 235 passed, 7 skipped

## Accomplishments

- `_LineReader.feed(bytes) -> List[str]` correctly buffers UTF-8 multibyte sequences split across chunk boundaries; `reset()` clears both decoder state and `_partial` (Pitfall 8 verified).
- `GameEngine.apply(packet) -> List[GameEvent]` covers the full 11-event behavior table from the plan: GameStarted, GameEnded, TurnChanged, MulliganDone, CardDrawn, CardPlayed, CardRevealed, CardRemoved, AttackStarted, MinionDied, DamageDealt. `current_state` returns a frozen GameState snapshot rebuilt via `dataclasses.replace` on every meaningful change.
- `PowerLogWatcher` tails Power.log via a 150 ms wx.Timer, backward-scans up to 1 MB looking for the most-recent `CREATE_GAME` line on first tick, detects truncation by `size < offset`, caps per-tick line buffer at 100 000, and contains tick errors per D-04 (tick keeps ticking).
- Engine has no `hslog` or `wx` imports, preserving D-10 isolation and keeping it reusable for Phase 4 replay playback.
- `__init__.py` now exports `GameEngine` and `PowerLogWatcher` for tracker (Plan 07) and downstream phases.

## Task Commits

1. **Task 1 RED:** `babc3c3` test(02-06): add failing tests for `_LineReader` and `GameEngine`
2. **Task 1 GREEN:** `a338f99` feat(02-06): implement `_LineReader` and `GameEngine`
3. **Task 2 RED:** `e58fb2e` test(02-06): add failing tests for `PowerLogWatcher`
4. **Task 2 GREEN:** `0ca57b1` feat(02-06): implement `PowerLogWatcher` with backward-scan and rotation detection

## Files Created/Modified

- `stonereader/services/_line_reader.py` — UTF-8 incremental decoder + partial-line buffer
- `stonereader/services/_engine.py` — GameEngine (D-05/D-06/D-07), no hslog, no wx
- `stonereader/services/_watcher.py` — PowerLogWatcher with wx.Timer + backward-scan + truncation reset + buffer cap
- `stonereader/services/__init__.py` — export GameEngine, PowerLogWatcher
- `tests/test_services/test_line_reader.py` — 6 new tests
- `tests/test_services/test_engine.py` — converted 4 stubs to real tests (1 active, 3 fixture-skipping)
- `tests/test_services/test_watcher.py` — converted 6 stubs to real tests (all 6 active)

## Decisions Made

- **Engine bookkeeping:** internal mutable dicts/lists are an implementation detail; only frozen `GameState` and frozen `GameEvent` instances ever leave the boundary. This is faster than rebuilding tuples for every entity tag while still preserving the "no leaked mutation" invariant for subscribers (D-08, Pitfall 4).
- **Watcher testability:** `_do_tick()` is the "real" tick body; `_tick()` is a thin wrapper that adds the D-04 try/except. Tests construct watchers without calling `start()` and drive `_do_tick()` directly, eliminating any dependency on a real `wx.Timer` and keeping the suite portable to non-GUI CI.
- **Backward-scan overlap tail:** to catch a `CREATE_GAME` needle that straddles two 4 KB chunks, each iteration saves `len(NEEDLE)` bytes from the current chunk to prepend to the next, matching HDT's behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_reset_clears_partial_line_buffer` could not actually trigger truncation**

- **Found during:** Task 2 (PowerLogWatcher tests)
- **Issue:** The test as written in the plan wrote 58 bytes, then overwrote with 61 bytes. Because `Path.write_bytes` does not change inode/mtime in a way the watcher observes mid-test, and the new size is *larger* than the prior size, the watcher's truncation rule (`size < offset`) never fired. The partial buffer therefore never got flushed and the assertion `"13:00:01" in line` failed (the emitted line carried the old "13:00:00" timestamp because the partial prefix leaked).
- **Fix:** Restructured the test to (a) write the partial line, (b) tick, (c) write empty bytes (genuine truncation), (d) tick (observe truncation, watcher resets), (e) write the new line, (f) tick (read the new line cleanly). Added an extra assertion `not any("13:00:00" in ln and "CREATE_GAME" in ln)` to make the partial-buffer-leak signature explicit.
- **Verification:** All 6 watcher tests now pass; the test still validates the originally-intended invariant (a flushed partial buffer).
- **Committed in:** `0ca57b1` (Task 2 GREEN)

**2. [Rule 2 - Missing Critical] `_maybe_backward_scan` could request 0 or negative bytes near file start**

- **Found during:** Task 2 implementation
- **Issue:** When `read_offset == 0` and `scanned > 0`, `read_bytes = min(BACKWARD_SCAN_CHUNK, file_size - 0 - scanned)` could be `<= 0`, leading `fp.read(0)` to return `b""` and the loop to spin until `scanned >= file_size`. Mostly harmless but could exhaust the cap on small files.
- **Fix:** Added explicit `if read_bytes <= 0: break` early-exit.
- **Verification:** All backward-scan tests pass.
- **Committed in:** `0ca57b1` (Task 2 GREEN)

---

**Total deviations:** 2 auto-fixed (1 test-design bug, 1 missing edge-case guard)
**Impact on plan:** Neither change altered the plan's intent — both shore up correctness of the originally-specified behavior. No scope creep.

## Threat Model Compliance

| Threat | Disposition | Status |
|--------|-------------|--------|
| T-2-03 (per-tick buffer overflow) | mitigate | Verified by `test_buffer_cap_drops_oldest_lines` with monkeypatched `MAX_BUFFERED_LINES=5` |
| T-2-03b (single huge line OOM) | accept | Acknowledged; not exercised |
| T-2-03c (backward-scan reading whole file) | mitigate | `BACKWARD_SCAN_MAX_BYTES = 1_048_576` cap enforced in loop |
| T-2-RESET (stale partial buffer) | mitigate | Verified by `test_reset_clears_partial_line_buffer` (after deviation 1 fix) |
| T-2-D04 (single tick failure kills Timer) | mitigate | `_tick` wraps `_do_tick` in try/except `logger.exception` |
| T-2-PATH-DOWN (path_provider returns None) | mitigate | Watcher detects `path is None or not path.exists()` and triggers reset |

## Issues Encountered

None beyond the deviations above.

## Acceptance Criteria

All Task 1 and Task 2 acceptance criteria from the plan pass:

- `class _LineReader`, `def feed`, `def reset`, `getincrementaldecoder` present in `_line_reader.py`
- `class GameEngine`, `def apply` present; no `hslog` or `wx` imports in `_engine.py`
- `class PowerLogWatcher`, `def start`, `def stop`, `def _tick`, `def _maybe_backward_scan` present
- `POLL_INTERVAL_MS = 150`, `MAX_BUFFERED_LINES = 100_000`, `BACKWARD_SCAN_MAX_BYTES = 1_048_576`, `CREATE_GAME_NEEDLE`, `logger.exception` all present in `_watcher.py`
- `tests/test_services/test_watcher.py` contains zero `pytest.skip` calls
- All 6 line_reader tests pass; engine snapshot test passes; engine fixture-dependent tests skip cleanly; all 6 watcher tests pass

Verification commands:

```text
$ uv run pytest tests/test_services/test_line_reader.py tests/test_services/test_engine.py tests/test_services/test_watcher.py
# 13 passed, 3 skipped (fixture-dependent — Wave 5 will supply)

$ grep -lr "import hslog\|from hslog" stonereader/services/
stonereader/services/_packets.py    # docstring only
stonereader/services/_parser.py     # the one allowed translator (D-10)

$ grep -E "^import wx|^from wx" stonereader/services/_engine.py
# (no output — engine is wx-free)
```

## Next Phase Readiness

- Wave 4 (Plan 07) can now construct `GameTracker(parent=frame, card_db=db)` to wire `PowerLogWatcher → Parser → GameEngine → subscribers`.
- The wave-3 deliverables (line reader, engine, watcher) compose without additional wiring; tracker only needs to register `on_lines = lambda lines: parser.feed_each(lines) -> engine.apply(...)` and route the resulting `GameEvent`s to subscribers.
- `power_log_fixture` skip path (3 tests) is intentional — Wave 5 (fixture capture) turns those skips into passes without engine code changes.

## Self-Check: PASSED

- `stonereader/services/_line_reader.py` — FOUND
- `stonereader/services/_engine.py` — FOUND
- `stonereader/services/_watcher.py` — FOUND
- `tests/test_services/test_line_reader.py` — FOUND
- Commits `babc3c3`, `a338f99`, `e58fb2e`, `0ca57b1` — all present in `git log`

## TDD Gate Compliance

- Task 1 RED: `babc3c3` test(02-06): add failing tests for _LineReader and GameEngine
- Task 1 GREEN: `a338f99` feat(02-06): implement _LineReader and GameEngine
- Task 2 RED: `e58fb2e` test(02-06): add failing tests for PowerLogWatcher
- Task 2 GREEN: `0ca57b1` feat(02-06): implement PowerLogWatcher with backward-scan and rotation detection

Sequence verified: each `feat` commit follows the corresponding `test` commit; no implementation preceded its tests.

---
*Phase: 02-log-infrastructure*
*Completed: 2026-04-25*
