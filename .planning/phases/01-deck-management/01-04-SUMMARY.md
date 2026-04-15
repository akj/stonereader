---
phase: 01-deck-management
plan: 04
subsystem: app-integration
tags: [navigation, panel-swap, clipboard, integration, app-refactor]

# Dependency graph
requires:
  - "01-01: DeckSummary, Deck model, db CRUD"
  - "01-02: HomePresenter, HomePanel, DeckContentsPresenter, DeckContentsPanel"
  - "01-03: DeckManagerPresenter, DeckManagerPanel, ImportDeckPresenter, ImportDeckPanel"
provides:
  - NavigationController class replacing wx.Notebook with panel-swap stack
  - Refactored MainWindow with clipboard auto-detection
  - Refactored OnInit wiring all presenters and panels
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NavigationController panel-swap with navigation stack (D-01)"
    - "Escape/back key injection by NavigationController for non-home panels (D-02)"
    - "EVT_ACTIVATE clipboard auto-detection with suppress-on-launch guard (D-06)"
    - "Dynamic panel creation for DeckContentsPanel (re-registered on each deck open)"

key-files:
  created:
    - tests/test_navigation.py
  modified:
    - stonereader/app.py

key-decisions:
  - "NavigationController injects escape/back keys into key maps rather than presenters owning them"
  - "DeckContentsPanel created dynamically on each deck open (destroyed and recreated) because it depends on the specific Deck object"
  - "Clipboard check suppressed on initial launch via _suppress_clipboard_check flag (Pitfall 5)"
  - "Both InputLayer._on_activate and MainWindow._on_activate coexist via event.Skip() propagation"

patterns-established:
  - "Panel-swap navigation replaces wx.Notebook for all future features"
  - "NavigationController.register_panel/show_panel/go_back as standard panel lifecycle"

requirements-completed: [DECK-01, DECK-02, DECK-03, DECK-04, DECK-05]

# Metrics
duration: 3min
completed: 2026-04-15
---

# Phase 01 Plan 04: Integration and Navigation Summary

NavigationController replacing wx.Notebook with panel-swap stack navigation, clipboard auto-detection via EVT_ACTIVATE, and full wiring of all deck management presenters/panels in OnInit.

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-15T06:20:50Z
- **Completed:** 2026-04-15T06:23:24Z
- **Tasks:** 1 of 2 (Task 2 is human-verify checkpoint)
- **Files modified:** 2

## Accomplishments

- NavigationController class with register_panel, show_panel, go_back, current_panel_name
- Panel-swap navigation replaces wx.Notebook entirely (no wx.Notebook in code)
- Escape and Backspace keys automatically injected for all non-home panels (D-02)
- Home screen has no escape/back (nowhere to go)
- MainWindow refactored with clipboard auto-detection via EVT_ACTIVATE (D-06)
- Clipboard check suppressed on initial launch, deduplicates via last-checked tracking (Pitfall 5)
- OnInit wires Home, Card Library, Deck Manager, Import Deck panels
- DeckContentsPanel created dynamically when a deck is opened
- Import success callback navigates to Deck Manager and reloads deck list
- 11 new NavigationController tests all passing
- Full suite: 120 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create NavigationController and refactor app.py** - `e5e3d69` (feat)
2. **Task 2: Verify Deck Management end-to-end** - PENDING (human-verify checkpoint)

## Files Created/Modified

- `stonereader/app.py` - Complete rewrite: NavigationController, refactored MainWindow with clipboard auto-detection, refactored OnInit wiring all panels
- `tests/test_navigation.py` - 11 tests for NavigationController (register, show, hide, go_back, escape injection, key map restoration, deep stack)

## Decisions Made

- NavigationController injects escape/back keys into key maps rather than having each presenter define them -- centralizes back-navigation logic and ensures consistency
- DeckContentsPanel is created dynamically on each deck open because it depends on the specific Deck object; old panel destroyed and re-registered
- Clipboard check suppressed on initial launch via `_suppress_clipboard_check` flag to prevent unwanted dialog on app start
- InputLayer's `_on_activate` handler (text mode unstick) coexists with MainWindow's new `_on_activate` handler because both call `event.Skip()`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Added type annotation to _on_open_deck callback**
- **Found during:** Task 1
- **Issue:** The plan's `_on_open_deck` callback used bare `deck` parameter without type annotation
- **Fix:** Added `deck: object` type annotation and `# type: ignore[arg-type]` for DeckContentsPresenter constructor (since the actual type is Deck but the callback signature uses object for decoupling)
- **Files modified:** stonereader/app.py
- **Commit:** e5e3d69

**2. [Rule 2 - Missing] Added extra tests beyond plan specification**
- `test_go_back_restores_previous_key_map` -- verifies key map restoration on back navigation
- `test_deep_navigation_stack` -- verifies 3-level deep navigation and back traversal

---

**Total deviations:** 2 minor (1 type annotation, 1 extra test coverage)
**Impact on plan:** No scope creep. Improvements to type safety and test coverage.

## Issues Encountered

None.

## User Setup Required

None -- no external service configuration required.

## Checkpoint Status

Task 2 is a human-verify checkpoint awaiting manual testing of the complete deck management experience.

## Self-Check: PASSED

All 2 created/modified files exist on disk. Task 1 commit hash (e5e3d69) verified in git log. All key content markers verified (NavigationController class, register_panel method, clipboard detection). Task 2 pending human-verify checkpoint.
