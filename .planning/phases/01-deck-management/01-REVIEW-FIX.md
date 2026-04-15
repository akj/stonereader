---
phase: 01-deck-management
fixed_at: 2026-04-15T12:30:00Z
review_path: .planning/phases/01-deck-management/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-04-15T12:30:00Z
**Source review:** .planning/phases/01-deck-management/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (1 Critical, 5 Warning)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: Navigation stack grows unboundedly when opening deck contents

**Files modified:** `stonereader/app.py`
**Commit:** 9b78a9a
**Applied fix:** Added stack cleanup in `_on_open_deck` -- when an existing "Deck Contents" panel is destroyed, stale entries are now filtered from `nav._stack` before re-registering the new panel. This prevents ghost navigation entries that accumulate when the user repeatedly opens different decks.

### WR-01: Export announces "copied" before clipboard write occurs

**Files modified:** `stonereader/presenters/deck_manager.py`, `tests/test_deck_manager.py`
**Commit:** 353d81b
**Applied fix:** Removed the premature `speak("Deck code copied to clipboard")` from `export_current_deckstring()` and moved the announcement to `_export_to_clipboard()`, where it fires after the view's clipboard callback has executed. Updated the existing test to no longer expect speech from `export_current_deckstring()` and added a new test `test_export_to_clipboard_announces_after_callback` that verifies the announcement fires after the callback.

### WR-02: Schema version table allows duplicate rows

**Files modified:** `stonereader/db.py`
**Commit:** 5244655
**Applied fix:** Changed the `schema_version` CREATE TABLE statement to use `version INTEGER PRIMARY KEY` instead of `version INTEGER NOT NULL`, ensuring uniqueness. Changed the INSERT on init to `INSERT OR REPLACE INTO schema_version` to handle idempotent re-initialization without creating duplicate rows.

### WR-03: Broad exception catch masks debugging information

**Files modified:** `stonereader/presenters/deck_manager.py`, `stonereader/presenters/import_deck.py`, `stonereader/app.py`
**Commit:** 5476399
**Applied fix:** Narrowed exception catches in three locations: (1) `deck_manager.py:open_current_deck` from `(ValueError, TypeError, Exception)` to `(ValueError, TypeError)`, (2) `import_deck.py:validate_and_import` from `(TypeError, Exception)` to `TypeError`, (3) `app.py:_check_clipboard_for_deckstring` from `(ValueError, TypeError, Exception)` to `(ValueError, TypeError)`. Unexpected exceptions now propagate for debugging instead of being silently swallowed.

### WR-04: Clipboard cleared after deckstring detection could lose user data

**Files modified:** `stonereader/app.py`
**Commit:** 392b2e8
**Applied fix:** Removed the clipboard clear block (`wx.TheClipboard.Open/Clear/Close`) that ran unconditionally after deckstring detection. The `_last_clipboard_deckstring` guard already prevents re-prompting for the same string, making the destructive clear unnecessary. Added a comment documenting this reasoning.

### WR-05: Missing module docstring in `models/deck.py`

**Files modified:** `stonereader/models/deck.py`
**Commit:** 905ab1e
**Applied fix:** Added module-level docstring `"""Hearthstone deck models -- Deck (resolved cards) and DeckSummary (lightweight list display)."""` per project convention requiring module-level docstrings on all files.

---

_Fixed: 2026-04-15T12:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
