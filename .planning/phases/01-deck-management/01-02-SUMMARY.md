---
phase: 01-deck-management
plan: 02
subsystem: presenters
tags: [presenter, view, zone-navigation, speech, home-screen, deck-contents]

# Dependency graph
requires:
  - "01-01: DeckSummary, Deck model, db CRUD"
provides:
  - HomePresenter with zone navigation for 3-item feature menu
  - HomePanel with wx.ListBox and MSAA labels
  - DeckContentsPresenter for (Card, count) tuple navigation with detail inspection
  - DeckContentsPanel with virtual ListCtrl and MSAA labels
affects: [01-03, 01-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HomePresenter uses string items in zone navigation (MENU_ITEMS list)"
    - "DeckContentsPresenter reuses base _format_item_speech for (Card, count) tuples"
    - "announce_deck_header speaks deck metadata on view entry"
    - "Views use wx.StaticText sibling order for MSAA labeling"

# Key files
key-files:
  created:
    - stonereader/presenters/home.py
    - stonereader/views/home.py
    - stonereader/presenters/deck_contents.py
    - stonereader/views/deck_contents.py
    - tests/test_home.py
    - tests/test_deck_contents.py
  modified: []

# Decisions
decisions:
  - "HomePresenter uses up/down AND left/right for menu navigation (matches UI-SPEC)"
  - "DeckContentsPresenter does not include escape/back in key map -- NavigationController in Plan 04 handles it"
  - "Added 3 extra tests beyond plan specification for view callback coverage on jump_to_first/jump_to_last"

# Metrics
metrics:
  duration: "2 minutes"
  completed: "2026-04-15T06:11:42Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 23
  files_created: 6
  files_modified: 0
---

# Phase 01 Plan 02: Home and Deck Contents Presenters Summary

HomePresenter and DeckContentsPresenter with full zone navigation, speech output, and MSAA-labeled views -- 23 tests passing with zero regressions.

## Task Completion

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create HomePresenter and HomePanel with tests | ff02d49 | stonereader/presenters/home.py, stonereader/views/home.py, tests/test_home.py |
| 2 | Create DeckContentsPresenter and DeckContentsPanel with tests | 86f6b8b | stonereader/presenters/deck_contents.py, stonereader/views/deck_contents.py, tests/test_deck_contents.py |

## What Was Built

### HomePresenter (stonereader/presenters/home.py)
- Inherits `ZoneNavigationMixin` and `BasePresenter`
- Single "menu" zone with 3 items: "Card Library", "Deck Manager", "Import Deck"
- Announces items with position suffix (e.g. "Card Library, 1 of 3")
- `select_current()` fires `on_select` callback with the menu item name
- Key map: up, down, left, right, enter, home, end
- No feature-switching hotkeys (per D-03)

### HomePanel (stonereader/views/home.py)
- wx.Panel with wx.ListBox for feature menu
- "StoneReader" heading (wx.StaticText) for MSAA context
- "Features:" label placed before ListBox via sibling order (MSAA)
- `list_box` property exposes focus target for NavigationController

### DeckContentsPresenter (stonereader/presenters/deck_contents.py)
- Inherits `ZoneNavigationMixin` and `BasePresenter`
- Single "cards" zone navigating `(Card, int)` tuples from Deck.cards
- Base `_format_item_speech` handles tuple format: "CardName x{count}, N of M"
- Down/up arrows delegate to `read_detail_lines` for card detail inspection
- `announce_deck_header()` speaks "{name}: {total} cards, {class}, {format}"
- `set_on_state_changed` callback notifies view on navigation
- Key map: left, right, down, up, home, end (no escape -- handled by Plan 04)

### DeckContentsPanel (stonereader/views/deck_contents.py)
- wx.Panel with virtual ListCtrl for card display
- "Cards:" label via wx.StaticText sibling order (MSAA)
- `_DeckCardListCtrl` with `AcceptsFocus() -> False` (stays out of Tab order)
- Wires `on_state_changed` callback for visual sync

## Test Coverage

- **test_home.py**: 10 tests -- zone initialization, menu item listing, navigation (move/jump), selection callback, key map completeness, no feature-switching hotkeys
- **test_deck_contents.py**: 13 tests -- zone initialization, card tuple items, navigation with count format, boundary clamping, detail inspection, deck header announcement, key map completeness, no escape key, view callbacks on move/jump

## Verification Results

- `uv run pytest tests/test_home.py tests/test_deck_contents.py -v`: 23 passed
- `uv run pytest tests/ -v`: 87 passed (full suite, zero regressions)
- `uv run ruff check`: all 6 files clean
- `uv run pyright`: 0 errors on presenter files
- Views contain zero `_speech` references (speech only in presenters)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused MENU_ITEMS import in test_home.py**
- **Found during:** Task 1 lint check
- **Issue:** `MENU_ITEMS` was imported but not referenced in any test
- **Fix:** Removed the unused import
- **Files modified:** tests/test_home.py
- **Commit:** ff02d49 (included in task commit)

### Scope Additions

**2. Added 3 extra tests beyond plan specification**
- `test_key_map_does_not_have_feature_switching_hotkeys` (D-03 enforcement)
- `test_view_callback_fires_on_jump_to_first` (callback coverage)
- `test_view_callback_fires_on_jump_to_last` (callback coverage)

## Self-Check: PASSED

All 7 created files verified on disk. Both task commits (ff02d49, 86f6b8b) verified in git log.
