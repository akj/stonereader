---
phase: 01-deck-management
plan: 01
subsystem: database
tags: [sqlite, dataclass, crud, frozen-model, input-layer]

# Dependency graph
requires: []
provides:
  - DeckSummary frozen dataclass for deck list display
  - save_deck/get_all_decks/delete_deck CRUD functions in db.py
  - WXK_DELETE key mapping in InputLayer
affects: [01-02, 01-03, 01-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DeckSummary frozen dataclass for lightweight list display (no resolved cards)"
    - "Parameterized SQL for all deck CRUD operations"
    - "ORDER BY created_at DESC, id DESC for stable newest-first ordering"

key-files:
  created: []
  modified:
    - stonereader/models/deck.py
    - stonereader/models/__init__.py
    - stonereader/db.py
    - stonereader/input_layer.py
    - tests/test_db.py
    - tests/test_input_layer.py

key-decisions:
  - "Added id DESC tiebreaker to ORDER BY clause for stable ordering when timestamps match"

patterns-established:
  - "DeckSummary pattern: lightweight frozen dataclass for list display without resolving full card objects"
  - "CRUD functions in db.py accept Connection as first param, return domain models"

requirements-completed: [DECK-02, DECK-04, DECK-05]

# Metrics
duration: 2min
completed: 2026-04-15
---

# Phase 01 Plan 01: Data Foundation Summary

**DeckSummary frozen dataclass with SQLite CRUD (save/list/delete) and WXK_DELETE key mapping for deck management**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-15T06:04:19Z
- **Completed:** 2026-04-15T06:06:27Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- DeckSummary frozen dataclass with deck_id, name, hero_class, format, deckstring, created_at fields
- save_deck, get_all_decks, delete_deck functions with parameterized SQL queries
- get_all_decks returns results ordered newest-first with stable tiebreaker
- WXK_DELETE mapped to "delete" in InputLayer for deck deletion hotkey support
- 7 new tests (5 db CRUD + 2 input layer) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add DeckSummary model and db CRUD functions** - `58c32b8` (feat)
2. **Task 2: Add WXK_DELETE to InputLayer key mapping** - `3d3da7d` (feat)

## Files Created/Modified
- `stonereader/models/deck.py` - Added DeckSummary frozen dataclass after existing Deck class
- `stonereader/models/__init__.py` - Export DeckSummary in import and __all__
- `stonereader/db.py` - Added save_deck, get_all_decks, delete_deck CRUD functions with DeckSummary import
- `stonereader/input_layer.py` - Added wx.WXK_DELETE: "delete" to _KEY_NAMES dict
- `tests/test_db.py` - Added 5 tests for CRUD operations (save, list, empty, delete, created_at)
- `tests/test_input_layer.py` - Added 2 tests for delete key spec and callback dispatch

## Decisions Made
- Added `id DESC` as tiebreaker in ORDER BY clause: SQLite CURRENT_TIMESTAMP has only second-level precision, so rapid inserts get identical timestamps. Adding `id DESC` ensures stable newest-first ordering regardless of timing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added id DESC tiebreaker to ORDER BY clause**
- **Found during:** Task 1 (DeckSummary model and db CRUD functions)
- **Issue:** `ORDER BY created_at DESC` alone produced unstable ordering when multiple decks were inserted within the same second (CURRENT_TIMESTAMP has only second precision)
- **Fix:** Changed to `ORDER BY created_at DESC, id DESC` so auto-increment id breaks ties
- **Files modified:** stonereader/db.py
- **Verification:** test_get_all_decks_returns_summaries passes reliably
- **Committed in:** 58c32b8 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for test reliability and correct ordering behavior. No scope creep.

## Issues Encountered
None beyond the ORDER BY tiebreaker addressed above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DeckSummary model ready for DeckManagerPresenter (Plan 02)
- CRUD functions ready for deck import workflow (Plan 03)
- Delete key mapping ready for deck deletion UX (Plan 02)
- All existing tests still pass (no regressions)

## Self-Check: PASSED

All 6 files exist, both commit hashes found, all key content markers verified.

---
*Phase: 01-deck-management*
*Completed: 2026-04-15*
