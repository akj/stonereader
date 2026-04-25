---
phase: 01-deck-management
plan: 07
subsystem: navigation
tags: [navigation, focus-management, modal, accessibility, gap-closure, uat, screen-reader]

# Dependency graph
requires:
  - phase: "01-06 (Transient-Panel Concept)"
    provides: "_current_visible field on NavigationController as source of truth for the visible panel"
  - phase: "01-04 (Integration and Navigation)"
    provides: "NavigationController with _focus_targets registry"
provides:
  - "NavigationController.restore_focus() public helper that schedules wx.CallAfter(focus_target.SetFocus) on the currently visible panel"
  - "_check_clipboard_for_deckstring No-path focus restoration via self._nav.restore_focus()"
  - "Documented Yes-path override: name_ctrl.SetFocus deliberately replaces the default deckstring_ctrl focus target after pre-fill"
affects: [future-modal-callsites, delete-confirmation-dialog, error-dialogs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "restore_focus() helper pattern: a single reusable method that any modal callsite can call after its dialog.Destroy() to recover focus to the active panel, eliminating per-callsite wx.CallAfter boilerplate"
    - "Defensive _focus_targets.get() lookup: if the panel was destroyed mid-flight (e.g. replace_panel raced with the dialog), restore_focus silently no-ops rather than raising"

key-files:
  created: []
  modified:
    - stonereader/app.py
    - tests/test_navigation.py

key-decisions:
  - "Chose Option A (restore_focus helper on NavigationController) over Option B (inline wx.CallAfter on the No path only) because Option A generalizes to every future modal callsite at the cost of ~5 lines, while Option B would force each future callsite to re-derive the same focus-recovery logic"
  - "Made the Yes-path explicitly comment its deliberate focus override (name_ctrl rather than the default deckstring_ctrl) so the asymmetry between Yes and No paths is intentional, not accidental"
  - "Used patch('stonereader.app.wx.CallAfter') in tests rather than patching the global wx module: scopes the mock to the production import path the method actually resolves through, and patch.object auto-restores on exception via context-manager semantics, preserving test-to-test isolation"

patterns-established:
  - "Modal callsite focus recovery: after dialog.ShowModal() / dialog.Destroy(), call self._nav.restore_focus() on any path that does NOT navigate elsewhere"
  - "Test pattern for wx.CallAfter scheduling: patch the symbol on the production import path inside a `with patch(...)` block and assert call_args[0] equals the expected SetFocus bound method"

requirements-completed: [DECK-01]

# Metrics
duration: 2min
completed: 2026-04-25
---

# Phase 01 Plan 07: Clipboard No-Path Focus Restoration (UAT Gap 3 / D-06) Summary

**NavigationController gains a public restore_focus() helper, and MainWindow._check_clipboard_for_deckstring's No path now routes through it so screen reader users no longer silently lose focus after dismissing the auto-import dialog with No.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-25T19:04:23Z
- **Completed:** 2026-04-25T19:06:29Z
- **Tasks:** 1 of 1
- **Files modified:** 2

## Accomplishments

- Closed UAT Gap 3 (D-06, Test 8): screen readers no longer silently lose focus after the clipboard auto-import dialog is dismissed with No
- `NavigationController.restore_focus()`: public helper that schedules `wx.CallAfter(focus_target.SetFocus)` on the currently visible panel; no-op when no panel is visible or the target was destroyed mid-flight
- `_check_clipboard_for_deckstring`: adds an `else` branch after `dialog.Destroy()` that calls `self._nav.restore_focus()`, mirroring the existing focus restoration the Yes path performs (different target widget, same wx.CallAfter mechanism)
- Documented the deliberate Yes-path override: a code comment now explains that `name_ctrl.SetFocus` intentionally replaces the default `deckstring_ctrl` focus target after pre-fill, so a future reader cannot mistake it for accidental duplication
- 5 new tests added (RED-then-GREEN); 26 existing navigation tests preserved unchanged
- Full suite green: 169 tests pass (was 164 -- net +5 new restore_focus tests)
- Lint, format, and type checks all clean on touched files

## Task Commits

Each task was committed atomically (TDD):

1. **Task 1 RED: failing tests for NavigationController.restore_focus** - `5d83017` (test)
2. **Task 1 GREEN: NavigationController.restore_focus + clipboard No-path routing** - `387a3f9` (feat)

(REFACTOR phase skipped: implementation is minimal -- 5 effective lines plus docstring -- and matches the plan's specified shape exactly. No cleanup warranted.)

## Files Created/Modified

- `stonereader/app.py` -- Added `restore_focus()` public method on `NavigationController`; added `else` branch with `self._nav.restore_focus()` to `MainWindow._check_clipboard_for_deckstring`; documented the Yes-path's deliberate `name_ctrl` focus override
- `tests/test_navigation.py` -- Added 5 tests covering restore_focus semantics: schedules SetFocus on visible panel, no-op when nothing visible, targets correct widget after panel switch, targets transient's focus widget while transient is visible, and a static-text check on app.py confirming the No-path else branch routes through restore_focus

## Decisions Made

- **Option A (restore_focus helper on NavigationController) chosen over Option B (inline wx.CallAfter)** -- generalizes to every future modal callsite for ~5 lines; Option B would force each future modal to re-derive the same recovery logic
- **`_focus_targets.get()` defensive lookup** -- matches existing pattern; silently no-ops if the panel was destroyed mid-flight rather than raising AttributeError
- **Deliberate Yes/No path asymmetry** -- Yes path keeps its `name_ctrl.SetFocus` (post-pre-fill UX expectation) but is now annotated; No path uses the default focus target via `restore_focus()`. Documenting the asymmetry prevents a future "hygiene" pass from collapsing them and breaking the import-after-paste flow
- **Test mock scoped to `stonereader.app.wx.CallAfter`** -- binds to the production import path; `patch.object` auto-restores on exception, preserving test-to-test isolation even if an assertion fails mid-block

## Deviations from Plan

None -- plan executed exactly as written. The plan's pseudocode for both Step A (restore_focus method placement) and Step B (else-branch wiring) matched what landed in `stonereader/app.py`, and the 5-test list matched verbatim.

## Issues Encountered

None.

## TDD Gate Compliance

- RED gate: `5d83017 test(01-07): add failing tests for NavigationController.restore_focus` -- 5 tests fail with `AttributeError: 'NavigationController' object has no attribute 'restore_focus'` (4 behavioral) and `AssertionError` on the static regex check (1 structural)
- GREEN gate: `387a3f9 feat(01-07): add NavigationController.restore_focus and route clipboard No-path through it` -- all 31 tests in `test_navigation.py` pass; full suite (169 tests) green
- REFACTOR gate: skipped intentionally -- no cleanup warranted

## Acceptance Criteria Verification

- `grep -n "def restore_focus" stonereader/app.py` -> 1 line at line 193 [pass]
- `grep -n "self._nav.restore_focus" stonereader/app.py` -> 1 line at line 337 (in `_check_clipboard_for_deckstring`) [pass]
- YES/else regex pair matches in `_check_clipboard_for_deckstring` (test enforces this) [pass]
- `uv run pytest tests/test_navigation.py -v` -> 31 passed (26 existing + 5 new) [pass]
- `uv run pytest tests/ -v` -> 169 passed (full suite green) [pass]
- `uv run ruff check stonereader/app.py tests/test_navigation.py` -> All checks passed! [pass]
- `uv run ruff format --check stonereader/app.py tests/test_navigation.py` -> 2 files already formatted [pass]
- `uv run pyright stonereader/app.py` -> 0 errors, 0 warnings, 0 informations [pass]
- `python -c "from stonereader.app import NavigationController; assert hasattr(NavigationController, 'restore_focus'); print('OK')"` -> OK [pass]

## Repo-Wide Lint Note

`uv run ruff check .` (whole-repo) still reports 2 F401 errors in `tests/test_deck_manager.py` (unused `get_all_decks` and `DeckSummary` imports). These are pre-existing, documented in `.planning/phases/01-deck-management/deferred-items.md`, and out of scope per this plan. Touched files (`stonereader/app.py`, `tests/test_navigation.py`) are fully clean.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- UAT Gap 3 closed; Test 8 of UAT (D-06 clipboard No-path focus loss) should now pass on a re-test
- `restore_focus()` is ready for reuse: any future modal callsite (delete confirmation, error dialog, settings dialog) can call `self._nav.restore_focus()` after its `dialog.Destroy()` and inherit correct focus recovery for free
- Wave 2 of Phase 01 gap closure is now complete (01-05, 01-06, 01-07 all merged); the only remaining repo-wide lint debt is the documented pre-existing F401 pair in `tests/test_deck_manager.py`, which can be cleaned up in a future hygiene pass

## Self-Check: PASSED

- File `stonereader/app.py` exists [verified]
- File `tests/test_navigation.py` exists [verified]
- File `.planning/phases/01-deck-management/01-07-SUMMARY.md` exists [will be verified post-write]
- Commit `5d83017` (RED) found in git log [verified]
- Commit `387a3f9` (GREEN) found in git log [verified]

---
*Phase: 01-deck-management*
*Plan: 07*
*Completed: 2026-04-25*
