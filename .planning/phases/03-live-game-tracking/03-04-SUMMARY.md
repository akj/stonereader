---
phase: 03-live-game-tracking
plan: 04
subsystem: services
tags: [phase-03, live-09, global-hotkey, services, win32, register-hotkey, wxpython, mod-norepeat, pitfall-3, pitfall-4, pitfall-5]

# Dependency graph
requires:
  - phase: 03-live-game-tracking
    provides: Wave 0 stub tests/test_global_hotkey.py (5 xfail-marked tests, plan 03-01)
provides:
  - GlobalHotkeyService — wx.Frame.RegisterHotKey/UnregisterHotKey/EVT_HOTKEY wrapper
  - Cumulative `failed` accumulator surface for startup-failure announcements (Pitfall 4)
  - Automatic MOD_NOREPEAT (0x4000) OR'ing to prevent held-chord speech-queue flooding (Pitfall 5)
  - Callback exception isolation contract (Pitfall 3 / T-2-04) — one bad callback never breaks the rest
  - Idempotent clear_all() suitable for MainWindow._on_close
  - 5 passing unit tests (xfail stubs flipped to green) using monkeypatched wx.Frame methods (no real OS hotkey traffic)
affects: [03-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Private wx-frame-bound service module (`_global_hotkey.py`) — parity with `_watcher.py` and `_tracker.py` (CONVENTIONS.md `_*` private modules)"
    - "Register-then-fail-then-succeed: `_next_id` advances even on failure so subsequent registrations remain usable"
    - "Cumulative `failed` list across service lifetime — `clear_all()` does NOT reset it, so startup-failure announcements remain readable"
    - "Test scaffold: `wx.App() / wx.Frame(None) / try-finally Destroy()` + `monkeypatch.setattr(frame, 'RegisterHotKey', fake_register)` to avoid registering real OS hotkeys"

key-files:
  created:
    - stonereader/services/_global_hotkey.py
    - .planning/phases/03-live-game-tracking/deferred-items.md
  modified:
    - tests/test_global_hotkey.py

key-decisions:
  - "Service is intentionally NOT exported from `stonereader/services/__init__.py` — plan 03-06 will import directly from the private module path, mirroring how `_engine.py` is consumed in tests vs. how `GameTracker` is the public facade. Keeps the public services surface small."
  - "MOD_NOREPEAT (0x4000) is OR'd inside `register()` rather than left to callers — the plan's Pitfall 5 mandate is non-negotiable, and centralising the OR removes a way for callers to forget it."
  - "`_failed` is cumulative for service lifetime; `clear_all()` does NOT reset it. Startup-failure announcements may be triggered after re-registration attempts, and we want the original failure label to remain readable."
  - "EVT_HOTKEY binding is wired once in `__init__` and never unbound — frame `Destroy()` releases it automatically; the service's lifetime is tied to the parent frame's. This is documented in the module docstring."

patterns-established:
  - "Pre-existing wx test-ordering fragility logged as D-DEFER-01 in `.planning/phases/03-live-game-tracking/deferred-items.md` rather than fixed inline (out of scope per Scope Boundary)."
  - "TDD gate sequence for service-with-tests plans: replace stubs with real failing tests (RED), implement (GREEN), no refactor needed when implementation is small."

requirements-completed: [LIVE-09]

# Metrics
duration: ~5 min
completed: 2026-04-27
---

# Phase 03 Plan 04: GlobalHotkeyService Summary

**`GlobalHotkeyService` — a 142-line wx.Frame.RegisterHotKey wrapper with automatic MOD_NOREPEAT, cumulative failure accumulation, idempotent clear_all, and callback-exception isolation, locked by 5 unit tests.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-27T03:38:46Z
- **Completed:** 2026-04-27T03:43:05Z
- **Tasks:** 1 (TDD: RED + GREEN, no refactor needed)
- **Files modified:** 3 (1 created service, 1 modified test stub, 1 created deferred-items doc)

## Accomplishments

- Implemented `stonereader/services/_global_hotkey.py` with `class GlobalHotkeyService` — a thin wx.Frame wrapper that owns Win32 hotkey ids (1000+), accumulates registration failures (Pitfall 4), defaults to MOD_NOREPEAT (Pitfall 5), and isolates callback exceptions (Pitfall 3 / T-2-04).
- Replaced the 5 Wave 0 xfail stubs in `tests/test_global_hotkey.py` with 5 real tests using `monkeypatch.setattr(frame, "RegisterHotKey", fake_register)` so no real OS hotkey is registered during the test run. All 5 pass green.
- Locked the explicit review-feedback regressions: `test_callback_exception_isolation` (a raising callback does NOT poison subsequent dispatches) and `test_repeated_register_after_failure` (a failed `register()` does NOT poison subsequent `register()` calls).
- Locked the cumulative-`failed` lifetime contract: `test_clear_all_idempotent` asserts that `service.failed` survives `clear_all()`.
- ruff + pyright clean on the new module and test file.
- Logged the pre-existing wx test-ordering fragility (D-DEFER-01) in `.planning/phases/03-live-game-tracking/deferred-items.md` for a future test-infrastructure plan to address.

## Task Commits

Each step was committed atomically:

1. **Task 1 RED — replace Wave 0 stubs with failing tests** — `3ae4cd9` (test)
2. **Task 1 GREEN — implement GlobalHotkeyService** — `e10f20d` (feat)
3. **Deferred items log (D-DEFER-01)** — `9af9cd6` (docs)

**Plan metadata commit (this SUMMARY):** to be added by the final commit step below.

_Note: TDD ran as RED → GREEN; no REFACTOR commit because the GREEN implementation matched the design straight from the plan's `<action>` block — no cleanup opportunity surfaced. The third commit documents an out-of-scope pre-existing failure rather than introducing new code._

## Files Created/Modified

- `stonereader/services/_global_hotkey.py` — Created. 142 lines. Module docstring documents Pitfalls 3/4/5, the Win32 application id space, the EVT_HOTKEY-binding lifetime, and the rationale for living in `services/` next to `_watcher.py`/`_tracker.py`. Exposes a single class `GlobalHotkeyService` with `register`, `clear_all`, `failed` property, and a private `_on_hotkey` dispatcher.
- `tests/test_global_hotkey.py` — Modified. Dropped the file-level `pytestmark = pytest.mark.xfail` and the per-test `pytest.xfail()` calls. Replaced with 5 real tests, each using `pytest.importorskip("wx")` + `wx.App() / wx.Frame(None) / try-finally Destroy()` scaffolding and `monkeypatch.setattr(frame, "RegisterHotKey", ...)` so no real OS hotkey is registered.
- `.planning/phases/03-live-game-tracking/deferred-items.md` — Created. Logs D-DEFER-01: pre-existing wx test-ordering fragility in `tests/test_navigation.py` triggered by any test that constructs `wx.App()`. Reproducible with the existing `tests/test_services/test_tracker.py::test_start_stop_clean` from before plan 03-04, so out of scope per the Scope Boundary rule.

## Decisions Made

- **Do NOT export `GlobalHotkeyService` from `stonereader/services/__init__.py`.** The plan calls it a "private" service per CONVENTIONS.md `_*` convention. Plan 03-06 will import via the explicit private path `from stonereader.services._global_hotkey import GlobalHotkeyService`, mirroring how `_engine.py` is treated. Keeps the public services surface clean.
- **Centralise MOD_NOREPEAT OR'ing inside `register()`** rather than relying on callers to remember it. The plan's Pitfall 5 mandate is non-negotiable, and the centralised approach removes a way for plan 03-06 to forget the flag.
- **`_failed` is cumulative — `clear_all()` does NOT reset it.** The user-facing startup-failure announcement may be triggered after re-registration attempts (e.g. retry on chord conflict), and the original failure label should remain readable. Documented in both the module docstring and the `clear_all` method docstring.
- **`EVT_HOTKEY` is bound once in `__init__` and never unbound.** Documented in the module docstring as intentional — frame `Destroy()` releases the binding automatically and the service's lifetime equals the frame's.
- **No `frame.UnregisterHotKey` in tests that don't exercise `clear_all`.** Tests that only exercise `register` + `_on_hotkey` skip mocking `UnregisterHotKey` because `clear_all` is never called in those tests; the `wx.Frame.Destroy()` cleanup at the end of the test won't try to call it (we never registered a real OS hotkey to begin with).

## Deviations from Plan

### Auto-fixed Issues

None of the Rules 1/2/3 deviations applied — the plan was specified at line-by-line precision (literal Python source for both the implementation and tests) and execution matched it exactly. The only divergence from a "perfectly clean" execution was the pre-existing wx test-ordering issue logged below, which was explicitly out of scope per the Scope Boundary rule.

### Pre-existing issue (out of scope, logged but not fixed)

**1. [Out of scope - Pre-existing] wx test-ordering fragility (D-DEFER-01)**
- **Found during:** Final verification (`uv run pytest tests/ -q`)
- **Issue:** When the new (or any) wx-using test runs *before* `tests/test_navigation.py` in the same pytest session, ~29 of the 36 navigation tests fail with `wx.PyAssertionError`-style errors. In isolation each navigation test passes; the order `tests/test_navigation.py tests/test_global_hotkey.py` → all 36 + 5 pass.
- **Why pre-existing — not caused by 03-04:** Identical behaviour reproducible with the existing wx-using test added before this plan: `uv run pytest tests/test_services/test_tracker.py::test_start_stop_clean tests/test_navigation.py -q` → same 29 navigation failures. That test predates plan 03-04, so the new tests merely surface the same latent problem.
- **Action taken:** Logged as D-DEFER-01 in `.planning/phases/03-live-game-tracking/deferred-items.md` with reproduction commands and a recommended fix (session-scoped `wx.App` fixture). Not fixed in this plan per the Scope Boundary rule.
- **Files modified:** `.planning/phases/03-live-game-tracking/deferred-items.md` (created).
- **Verification:** Targeted run `uv run pytest tests/test_global_hotkey.py -v` → 5/5 pass; targeted run `uv run pytest tests/test_navigation.py -q` → 31/31 pass. Issue is purely test-session-ordering.
- **Committed in:** `9af9cd6` (docs deferred-items log).

---

**Total deviations:** 0 auto-fixes (Rules 1-3 did not trigger). 1 out-of-scope pre-existing issue logged.
**Impact on plan:** None — execution matched the plan's `<action>` block line-for-line. The pre-existing wx test-ordering issue is explicitly documented for a future test-infrastructure plan.

## Issues Encountered

- The full-suite `uv run pytest tests/` initially looked alarming (36 failures), but per-file isolation reveals every plan-04 acceptance criterion passes: `tests/test_global_hotkey.py -v` → 5/5 green, `ruff check` → clean, `pyright` → 0 errors. The failures were entirely confined to `tests/test_navigation.py` and only manifest when a wx-using test runs first — a pre-existing fragility (see D-DEFER-01).

## User Setup Required

None — the GlobalHotkeyService adds no new dependencies, no new config files, no external services. Real Windows hotkey traffic will only flow once plan 03-06 wires `MainWindow` to construct the service and call `register()` for the LIVE-09 chords.

## TDD Gate Compliance

- **RED gate:** ✅ `3ae4cd9` (test commit) — replaced Wave 0 stubs with 5 real tests; pytest run shows `ModuleNotFoundError: No module named 'stonereader.services._global_hotkey'` (test fails because implementation does not yet exist).
- **GREEN gate:** ✅ `e10f20d` (feat commit) — implemented `GlobalHotkeyService`; same pytest invocation now reports 5/5 passed in 0.13s.
- **REFACTOR gate:** intentionally skipped — the implementation matched the plan's literal `<action>` Python source and no cleanup opportunity surfaced.

## Next Phase Readiness

- **Plan 03-06 (LiveGamePanel + app wiring):** can now `from stonereader.services._global_hotkey import GlobalHotkeyService` and call `service = GlobalHotkeyService(self.frame)` followed by per-chord `service.register(wx.MOD_CONTROL | wx.MOD_SHIFT, ord("R"), self._on_remaining_deck, "Remaining Deck")`. The `failed` list is ready to be read at startup for the chord-conflict announcement (Pitfall 4). `service.clear_all()` is the contract for `MainWindow._on_close` to call before `frame.Destroy()` (Runtime State Inventory).
- **Plan 03-05 (LiveGamePresenter):** unaffected — does not import this service.
- **Plan 03-04 acceptance criteria:** all met (file/symbols/grep counts/test pass count/lint/types). See "Self-Check: PASSED" below.

## Threat Flags

No new threat surface beyond the plan's `<threat_model>` register. The service does not touch the network, the filesystem, the database, or any auth path. Win32 hotkey registration is the only OS surface, and the threat register T-03-LIVE-09-01..05 already cover it.

## Self-Check: PASSED

Verified files and commits exist on disk and in git history:

- `stonereader/services/_global_hotkey.py` — FOUND (142 lines, contains `class GlobalHotkeyService`, `_MOD_NOREPEAT = 0x4000`, `frame.Bind(wx.EVT_HOTKEY, ...)`, `def register`, `def clear_all`, `def _on_hotkey`, `def failed` property, `Cumulative` documented twice).
- `tests/test_global_hotkey.py` — FOUND (5 named test functions; `pytestmark = pytest.mark.xfail` marker removed).
- `.planning/phases/03-live-game-tracking/deferred-items.md` — FOUND (D-DEFER-01 logged).
- Commit `3ae4cd9` — FOUND (RED — failing-test commit).
- Commit `e10f20d` — FOUND (GREEN — implementation commit).
- Commit `9af9cd6` — FOUND (docs deferred-items).

Acceptance command verification:
- `uv run pytest tests/test_global_hotkey.py -x -v` → 5 passed in 0.13s.
- `uv run ruff check stonereader/services/_global_hotkey.py tests/test_global_hotkey.py` → All checks passed.
- `uv run pyright stonereader/services/_global_hotkey.py` → 0 errors, 0 warnings, 0 informations.
- `grep -c "import keyboard\|import pynput\|import pywinauto\|import win32con" stonereader/services/_global_hotkey.py` → 0.
- `grep -c "pytestmark = pytest.mark.xfail" tests/test_global_hotkey.py` → 0.

---
*Phase: 03-live-game-tracking*
*Completed: 2026-04-27*
