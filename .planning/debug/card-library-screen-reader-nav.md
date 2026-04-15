---
status: resolved
trigger: "Card library does not work with screen readers. Search element is focused but cannot navigate to actual cards. Need category menu (constructed, battlegrounds), arrow-traversable card list, and Ctrl+F find dialog."
created: 2026-04-15
updated: 2026-04-15
---

# Debug Session: card-library-screen-reader-nav

## Symptoms

- **Expected behavior:** When navigating to the library there should be a menu with choices for cards (constructed, battlegrounds, etc.). Clicking that menu should bring focus to the cards list, traversable with arrows. Ctrl+F brings up a find dialog to apply searches that limit the collection being shown in the main list.
- **Actual behavior:** Search element is focused. Can type a search and results appear visually, but cannot navigate to the actual card results with screen reader.
- **Error messages:** Silent — nothing happens when trying to navigate past search to results.
- **Timeline:** Never worked — card library navigation has always been broken since it was built.
- **Reproduction:** Launch app → go to card library tab → type search → results appear visually but can't navigate to them via keyboard/screen reader.

## Current Focus

- hypothesis: Card Library lacks category menu and has unfocusable list control
- test: Review _CardListCtrl.AcceptsFocus(), CardBrowserPanel layout, app.py registration
- expecting: AcceptsFocus returns False, no category selection, no Ctrl+F binding
- next_action: done
- specialist_hint: python

## Evidence

- timestamp: 2026-04-15 analysis
  - _CardListCtrl.AcceptsFocus() explicitly returns False (views/card_browser.py:32)
  - Card Library registered with focus_target=card_panel (app.py:244), not search_ctrl
  - No category menu exists — goes straight to search TextCtrl
  - No Ctrl+F shortcut for find/filter dialog
  - CardBrowserPresenter key_map uses left/right for navigation but panel intercepts keys
  - The entire Card Library tab is a flat search+list, not the expected category→list flow

## Eliminated

(none needed — root cause is structural: missing features + unfocusable list)

## Resolution

- root_cause: Card Library was missing the category menu navigation flow entirely. The old design was a flat search TextCtrl with an unfocusable visual-only ListCtrl (_CardListCtrl.AcceptsFocus returns False). There was no way to navigate to card results via keyboard/screen reader, no category browsing, and no Ctrl+F find dialog.
- fix: Redesigned Card Library as a two-panel navigation flow following existing MVP patterns. (1) New CardLibraryPresenter/CardLibraryPanel provides a category menu (All Cards, plus 12 class categories) navigable with arrows, Enter selects. (2) CardBrowserPresenter now accepts category_label and card_class_filter parameters, creates filtered card lists per category, and includes announce_entry() and open_search() methods. (3) CardBrowserPanel shows filtered results with a search dialog callback. (4) Ctrl+F accelerator added to MainWindow that delegates to the current panel's open_search() if available. (5) NavigationController dynamically creates Card Browser panels per category selection (same pattern as Deck Contents).
- verification: 137 tests pass (38 new/updated for card library and card browser), pyright 0 errors, ruff 0 errors on changed files
- files_changed: stonereader/presenters/card_library.py (new), stonereader/views/card_library.py (new), stonereader/presenters/card_browser.py (rewritten), stonereader/views/card_browser.py (rewritten), stonereader/app.py (updated wiring), tests/test_card_library.py (new), tests/test_card_browser.py (updated)
