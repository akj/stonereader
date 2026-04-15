---
phase: 01-deck-management
reviewed: 2026-04-15T12:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - stonereader/app.py
  - stonereader/db.py
  - stonereader/input_layer.py
  - stonereader/models/__init__.py
  - stonereader/models/deck.py
  - stonereader/presenters/deck_contents.py
  - stonereader/presenters/deck_manager.py
  - stonereader/presenters/home.py
  - stonereader/presenters/import_deck.py
  - stonereader/views/deck_contents.py
  - stonereader/views/deck_manager.py
  - stonereader/views/home.py
  - stonereader/views/import_deck.py
  - tests/test_db.py
  - tests/test_deck_contents.py
  - tests/test_deck_manager.py
  - tests/test_home.py
  - tests/test_import_deck.py
  - tests/test_input_layer.py
  - tests/test_navigation.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-15T12:00:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 01 (Deck Management) adds a home screen, deck manager, deck contents viewer, deck import flow, clipboard auto-detection, and a NavigationController that replaces wx.Notebook with panel-swap navigation. The code is generally well-structured, follows the established MVP pattern with frozen dataclasses, and maintains good separation of concerns. Tests are thorough and cover the key behaviors.

Key concerns: one SQL injection-adjacent issue in the schema version table (no uniqueness constraint allowing duplicate version rows on concurrent init), a navigation stack leak where repeatedly opening decks accumulates hidden panels in the sizer, and a premature clipboard announcement in the export flow that fires before the clipboard write actually happens.

## Critical Issues

### CR-01: Navigation stack grows unboundedly when opening deck contents

**File:** `stonereader/app.py:287-296`
**Issue:** Every time the user opens a deck via Enter in the Deck Manager, `_on_open_deck` creates a fresh `DeckContentsPanel` and calls `nav.register_panel("Deck Contents", ...)`. The old panel is detached and destroyed, but `register_panel` re-adds the name to `_panels`, `_presenters`, and `_focus_targets` -- which is fine. However, `show_panel` on line 296 appends `"Deck Contents"` to `self._stack` every time. If the user opens deck A, goes back, opens deck B, goes back, opens deck C, the stack becomes `["Home", "Deck Manager", "Deck Contents", "Deck Contents", "Deck Contents"]` (with the earlier entries still present). Each `go_back()` will then try to show the "Deck Contents" panel name (whose underlying panel has already been destroyed), leading to either a stale reference crash or repeated "Deck Contents" entries the user must escape through one at a time.

**Fix:**
Before calling `nav.show_panel("Deck Contents")`, pop any existing "Deck Contents" entries from the stack, or better yet, add a method to NavigationController that replaces/reuses a panel rather than re-pushing:

```python
def _on_open_deck(deck: object) -> None:
    from stonereader.presenters.deck_contents import DeckContentsPresenter
    from stonereader.views.deck_contents import DeckContentsPanel

    contents_presenter = DeckContentsPresenter(speech, deck)  # type: ignore[arg-type]
    contents_panel = DeckContentsPanel(self._frame, contents_presenter)

    if "Deck Contents" in nav._panels:
        old_panel = nav._panels["Deck Contents"]
        nav._sizer.Detach(old_panel)
        old_panel.Destroy()
        # Also remove stale stack entries to prevent ghost navigation
        nav._stack = [name for name in nav._stack if name != "Deck Contents"]
    nav.register_panel(
        "Deck Contents", contents_panel, contents_presenter, contents_panel
    )
    nav.show_panel("Deck Contents")
    contents_presenter.announce_deck_header()
```

Alternatively, add a `replace_panel` method to `NavigationController` that handles this cleanly without reaching into private attributes.

## Warnings

### WR-01: Export announces "copied" before clipboard write occurs

**File:** `stonereader/presenters/deck_manager.py:162-171`
**Issue:** `export_current_deckstring()` calls `self._speech.speak("Deck code copied to clipboard")` on line 170, then returns the deckstring. The actual clipboard write happens in the view's `_on_export` callback (called by `_export_to_clipboard` on line 201-202). If the clipboard write fails (e.g., `wx.TheClipboard.Open()` returns False), the user has already been told the copy succeeded. This is a misleading announcement.

**Fix:**
Move the speech announcement to after the clipboard write succeeds, or have the export callback return success/failure:

```python
def export_current_deckstring(self) -> str | None:
    """Return deckstring of current deck for clipboard copy (D-15)."""
    item = self._current_item()
    if item is None or not isinstance(item, DeckSummary):
        return None
    # Don't announce here -- let view confirm success
    return item.deckstring

def _export_to_clipboard(self) -> None:
    deckstring = self.export_current_deckstring()
    if deckstring is not None and self._export_callback is not None:
        self._export_callback(deckstring)
        self._speech.speak("Deck code copied to clipboard")
```

### WR-02: Schema version table allows duplicate rows

**File:** `stonereader/db.py:11-13`
**Issue:** The `schema_version` table has no UNIQUE or PRIMARY KEY constraint on `version`, and `init_db` on line 63 always does `INSERT INTO schema_version (version) VALUES (?)`. If `init_db` is called concurrently from two processes (or if `get_schema_version` returns 0 due to a race), multiple version rows could be inserted. `get_schema_version` uses `fetchone()` which returns the first row -- this happens to work, but the table can accumulate stale rows.

**Fix:**
Add a PRIMARY KEY or UNIQUE constraint, or use REPLACE/INSERT OR IGNORE:

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
```

And change the insert on line 63 to:
```python
conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (1,))
```

### WR-03: Broad exception catch masks debugging information

**File:** `stonereader/presenters/deck_manager.py:122-125`
**Issue:** `open_current_deck` catches `(ValueError, TypeError, Exception)` on line 122. Since `Exception` is the base class of both `ValueError` and `TypeError`, listing all three is redundant but also overly broad -- it silently swallows unexpected errors (e.g., `AttributeError` from a code bug in `Deck.from_deckstring`) with only a generic "Could not load deck cards" message, making debugging difficult.

The same pattern appears in `stonereader/presenters/import_deck.py:77` and `stonereader/app.py:181`.

**Fix:**
Catch only the expected exceptions (`ValueError`, `TypeError`) and let unexpected ones propagate, or at minimum log them:

```python
try:
    deck = Deck.from_deckstring(item.deckstring, self._card_db, item.name)
except (ValueError, TypeError) as exc:
    self._speech.speak("Could not load deck cards")
    return
```

### WR-04: Clipboard cleared after deckstring detection could lose user data

**File:** `stonereader/app.py:206-208`
**Issue:** After detecting a valid deckstring on the clipboard and the user accepts the import dialog, the clipboard is unconditionally cleared. This destroys whatever was on the clipboard. If the user had other content copied after the deckstring (due to timing), or if they decline and the deckstring text was also useful for pasting elsewhere, the clear is destructive. The clear also happens even if `pre_fill_deckstring` fails for any reason.

**Fix:**
Only clear the clipboard if the import panel was successfully pre-filled, and consider whether clearing is truly necessary (the `_last_clipboard_deckstring` guard already prevents re-prompting for the same string):

```python
if result == wx.ID_YES:
    self._nav.show_panel("Import Deck")
    import_panel = self._nav._panels.get("Import Deck")
    if import_panel is not None:
        from stonereader.views.import_deck import ImportDeckPanel
        if isinstance(import_panel, ImportDeckPanel):
            import_panel.pre_fill_deckstring(text)
            wx.CallAfter(import_panel.name_ctrl.SetFocus)
    # Don't clear clipboard -- _last_clipboard_deckstring prevents re-prompt
```

### WR-05: Missing `__init__.py` module docstring in `models/deck.py`

**File:** `stonereader/models/deck.py:1`
**Issue:** Per the project conventions documented in CLAUDE.md ("Module-level docstrings present on all files"), `deck.py` is missing its module-level docstring. This is the only source file among the 13 reviewed source files that lacks one.

**Fix:**
Add a module docstring at the top of the file:

```python
"""Hearthstone deck models -- Deck (resolved cards) and DeckSummary (lightweight list display)."""
```

## Info

### IN-01: Accessing private NavigationController attributes from app wiring

**File:** `stonereader/app.py:198, 287-289`
**Issue:** `_check_clipboard_for_deckstring` accesses `self._nav._panels` (line 198) and `_on_open_deck` accesses `nav._panels`, `nav._sizer`, and `nav._stack` (lines 287-289). This couples the app wiring code to NavigationController internals. If the NavigationController implementation changes, these will break silently.

**Fix:**
Add public methods to `NavigationController`:

```python
def get_panel(self, name: str) -> wx.Panel | None:
    return self._panels.get(name)

def replace_panel(self, name: str, panel: wx.Panel, presenter: object, focus_target: wx.Window) -> None:
    """Replace an existing panel, destroying the old one."""
    if name in self._panels:
        old = self._panels[name]
        self._sizer.Detach(old)
        old.Destroy()
        self._stack = [n for n in self._stack if n != name]
    self.register_panel(name, panel, presenter, focus_target)
```

### IN-02: Global mutable state in test helper `_next_dbf_id`

**File:** `tests/test_deck_contents.py:10`, `tests/test_import_deck.py:12`
**Issue:** Both test files use a global `_next_dbf_id` counter with `global _next_dbf_id` to generate unique card IDs. This creates order-dependent state between tests if they run in the same process. While pytest typically isolates modules, this is a fragile pattern.

**Fix:**
Use `itertools.count()` or pass dbf_id explicitly:

```python
_dbf_counter = itertools.count(9000)

def _make_card(name: str = "Test Card", ...) -> Card:
    dbf_id = next(_dbf_counter)
    ...
```

### IN-03: Redundant exception types in except clauses

**File:** `stonereader/app.py:181`, `stonereader/presenters/import_deck.py:77`
**Issue:** `except (ValueError, TypeError, Exception)` is redundant -- `Exception` already covers both `ValueError` and `TypeError`. Listing all three suggests the author intended to catch only specific exceptions but added `Exception` as a safety net. This makes the intent unclear.

**Fix:**
Either catch only the specific expected exceptions:
```python
except (ValueError, TypeError):
```
Or if truly all exceptions must be caught, use just:
```python
except Exception:
```

### IN-04: `DeckManagerPanel` does not display empty state in the view

**File:** `stonereader/views/deck_manager.py:40-68`
**Issue:** When the deck list is empty, the `_DeckListCtrl` shows nothing visually. The presenter handles the speech announcement ("Deck Manager: no saved decks"), but sighted users (or screen reader users who missed the announcement) have no persistent indication that the list is empty. Consider adding a static text label that shows/hides based on whether decks exist.

**Fix:**
This is a minor UX improvement -- add a "No saved decks" label that toggles visibility:

```python
self._empty_label = wx.StaticText(self, label="No saved decks. Import a deck to get started.")
sizer.Add(self._empty_label, 0, wx.ALL, 8)

def _on_state_changed(self, decks, cursor):
    self._list_ctrl.set_decks(decks)
    self._empty_label.Show(not decks)
    if decks:
        self._list_ctrl.Select(cursor)
    self.Layout()
```

---

_Reviewed: 2026-04-15T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
