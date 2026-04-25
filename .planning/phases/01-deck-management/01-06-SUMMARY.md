---
phase: 01-deck-management
plan: 06
subsystem: navigation
tags: [navigation, panel-swap, transient, modal, back-navigation, gap-closure, uat]

# Dependency graph
requires:
  - phase: "01-04 (Integration and Navigation)"
    provides: "NavigationController with register_panel, show_panel, go_back, current_panel_name"
  - phase: "01-03 (Import Deck)"
    provides: "ImportDeckPanel and ImportDeckPresenter wired into OnInit"
provides:
  - "NavigationController.register_panel(..., transient=False) keyword-only parameter"
  - "_transient_panels: set[str] registry tracking transient panel names"
  - "_current_visible: str | None field as source of truth for the visible panel (transient or stacked)"
  - "Transient-aware show_panel: never appends transient names to _stack"
  - "Transient-aware go_back: hides transient and restores top of _stack"
  - "Transient-aware replace_panel: cleans up _transient_panels and accepts transient kwarg"
  - "current_panel_name now reads from _current_visible so callers see the visible transient"
  - "Import Deck registered with transient=True in StoneReaderApp.OnInit"
affects: [01-07-PLAN, future-modal-panels]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Transient panel registration -- a one-shot operation panel that is shown but never pushed onto the back-navigation stack (D-02 mental-model alignment)"
    - "Source-of-truth split: _stack tracks non-transient navigation history; _current_visible tracks the on-screen panel"
    - "Keyword-only transient parameter on register_panel/replace_panel keeps existing positional call sites working without modification"

key-files:
  created: []
  modified:
    - stonereader/app.py
    - tests/test_navigation.py

key-decisions:
  - "Chose Option A (transient flag at registration) over Option B (per-call replace=True) and Option C (import-success calls pop_self) because the flag declares the panel's nature once, requires zero call-site changes, and prevents leakage through the dialog clipboard auto-import path"
  - "Introduced _current_visible as a new private field rather than reusing _stack[-1]; needed because transients are never on _stack but must still drive current_panel_name so MainWindow._on_find delegates correctly"
  - "Transient panels always receive escape/back keys (even from Home) so the user can dismiss them without committing to the operation; non-transient Home retains its existing no-escape behavior"
  - "Used keyword-only parameter (after `*,`) on register_panel and replace_panel so existing positional callers in the codebase do not break"

patterns-established:
  - "Transient panels: register with transient=True for any one-shot operation that should be modal in mental model (Import Deck today; future Settings dialogs, Sync flows, etc.)"
  - "Static-text app.py grep test pattern: when a wx.App-dependent assertion is needed but constructing a second StoneReaderApp is impractical, regex the source file directly"

requirements-completed: [DECK-01, DECK-02]

# Metrics
duration: 5min
completed: 2026-04-25
---

# Phase 01 Plan 06: Transient-Panel Concept (UAT Gap 2 / D-02) Summary

**NavigationController gains a transient-panel concept: register_panel(transient=True) excludes a panel from _stack so go_back skips it; Import Deck is now a transient operation, never a back-navigation destination.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-25T18:53:26Z
- **Completed:** 2026-04-25T18:58:24Z
- **Tasks:** 1 of 1
- **Files modified:** 2

## Accomplishments

- Closed UAT Gap 2 (D-02, Test 8): user-reported behavior where Escape from a post-import panel walked back to Import Deck is fixed
- `NavigationController.register_panel` accepts a keyword-only `transient: bool = False`; transient names are tracked in `_transient_panels: set[str]`
- `show_panel` now hides whatever is currently visible (`_current_visible`) and conditionally appends to `_stack`: transient names are NEVER pushed
- `go_back` branches on whether the visible panel is transient: transients are hidden in place and `_stack[-1]` is re-shown (no pop); non-transients pop `_stack` exactly as before
- Transient panels always get `escape` and `back` keys injected (even when shown from Home), preserving the user's dismiss path
- `replace_panel` accepts and propagates the `transient` flag; old transient registrations are cleaned out of `_transient_panels` and `_current_visible` is reset if it pointed to the replaced name
- `current_panel_name` reads from `_current_visible` rather than `_stack[-1]` so callers (notably `MainWindow._on_find`) correctly delegate to a visible transient
- `StoneReaderApp.OnInit` registers `"Import Deck"` with `transient=True`; the existing import-success callback now leaves no Import Deck trace in `_stack` because `_stack` was never touched on the way in
- 10 new tests added (RED-then-GREEN); 16 existing navigation tests preserved unchanged
- Full suite green: 152 tests pass (was 142 -- net +10 new transient tests)
- Lint, format, and type checks all clean on touched files

## Task Commits

Each task was committed atomically (TDD):

1. **Task 1 RED: failing tests for transient-panel navigation** - `9517ab4` (test)
2. **Task 1 GREEN: NavigationController transient-panel concept + Import Deck registered transient=True** - `19a13f7` (feat)

(REFACTOR phase skipped: implementation reads cleanly; the small key-map activation duplication between `show_panel` and `go_back` is intentional -- each path computes the key map for the panel it just made visible.)

## Files Created/Modified

- `stonereader/app.py` -- Added `_transient_panels` set and `_current_visible` field on NavigationController; reworked `show_panel`/`go_back`/`replace_panel`/`current_panel_name` for transient-aware logic; updated OnInit to register "Import Deck" with `transient=True`
- `tests/test_navigation.py` -- Added 10 transient-panel tests covering registration, show, go_back from transient at depth and at home, forward-navigation cleanup, escape-key presence, replace_panel preservation/clearing, and OnInit static check; existing 16 tests untouched

## Decisions Made

- **Option A (transient flag at registration) chosen over Option B/C** -- declares nature once, zero call-site churn, covers the dialog clipboard auto-import path automatically
- **`_current_visible` introduced as separate state from `_stack`** -- required because transients are visible but absent from `_stack`; reusing `_stack[-1]` would either omit the transient from `current_panel_name` (breaking `_on_find`) or push the transient (defeating the whole abstraction)
- **Transient panels always escape-able** -- even when shown from Home, `escape`/`back` are injected so the user can dismiss the modal-like operation; non-transient Home keeps its no-escape policy
- **Keyword-only parameter** -- `*, transient: bool = False` keeps existing positional callers (Home, Card Library, Deck Manager, Card Browser, Deck Contents) byte-for-byte compatible

## Deviations from Plan

None -- plan executed exactly as written. The plan's pseudocode for each step matched what landed in `stonereader/app.py`, and the test list matched verbatim.

## Issues Encountered

None.

## TDD Gate Compliance

- RED gate: `9517ab4 test(01-06): add failing tests for transient-panel navigation` -- 10 tests fail with `TypeError: register_panel() got an unexpected keyword argument 'transient'` and `AssertionError` on the OnInit static check
- GREEN gate: `19a13f7 feat(01-06): add transient-panel concept to NavigationController` -- all 26 tests in `test_navigation.py` pass; full suite (152 tests) green
- REFACTOR gate: skipped intentionally -- no cleanup warranted

## Acceptance Criteria Verification

- `grep -cn "_transient_panels" stonereader/app.py` -> 7 (need >=4) [pass]
- `grep -cn "_current_visible" stonereader/app.py` -> 13 (need >=4) [pass]
- `grep -cn "transient: bool = False" stonereader/app.py` -> 2 (need >=2) [pass]
- Multiline regex `register_panel(...Import Deck...transient=True...)` matches in `stonereader/app.py` [pass]
- 10 new transient test functions found by anchored grep [pass]
- `uv run pytest tests/test_navigation.py -v` -> 26 passed [pass]
- `uv run pytest tests/ -v` -> 152 passed [pass]
- `uv run ruff check stonereader/app.py tests/test_navigation.py` -> All checks passed! [pass]
- `uv run ruff format --check ...` -> 2 files already formatted [pass]
- `uv run pyright stonereader/app.py` -> 0 errors, 0 warnings [pass]
- `inspect.signature(NavigationController.register_panel)` contains `transient` parameter [pass]

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- UAT Gap 2 closed; Test 8 of UAT (D-02 Escape/Backspace back navigation) should now pass on a re-test
- Pattern is ready for reuse: any future modal/transient flow (Settings, Refresh-Card-Data, Sync) registers with `transient=True` and gets correct back-navigation semantics for free
- Plans 01-05 (in-flight on a sibling worktree) and 01-07 (clipboard No-path focus) close the remaining two UAT gaps; this plan does not block or conflict with either

## Self-Check: PASSED

- File `stonereader/app.py` exists [verified]
- File `tests/test_navigation.py` exists [verified]
- File `.planning/phases/01-deck-management/01-06-SUMMARY.md` exists [will be verified post-write]
- Commit `9517ab4` (RED) found in git log [verified]
- Commit `19a13f7` (GREEN) found in git log [verified]

---
*Phase: 01-deck-management*
*Plan: 06*
*Completed: 2026-04-25*
