---
phase: 01-deck-management
reviewed: 2026-04-25
depth: standard
files_reviewed: 17
files_reviewed_list:
  - stonereader/app.py
  - stonereader/db.py
  - stonereader/input_layer.py
  - stonereader/models/__init__.py
  - stonereader/models/deck.py
  - stonereader/presenters/deck_contents.py
  - stonereader/presenters/home.py
  - stonereader/presenters/import_deck.py
  - stonereader/views/deck_contents.py
  - stonereader/views/home.py
  - tests/test_db.py
  - tests/test_deck.py
  - tests/test_deck_contents.py
  - tests/test_home.py
  - tests/test_import_deck.py
  - tests/test_input_layer.py
  - tests/test_navigation.py
findings:
  critical: 0
  warning: 4
  info: 7
  total: 11
status: issues_found
reviewer: gsd-code-reviewer
supersedes: 2026-04-15 review (re-run after gap-closure plans 01-05/06/07)
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-25 (re-run after 01-05/06/07 gap-closure)
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Recently-changed files concentrate around graceful-degrade deckstring import (DECK-01), the transient-panel concept in `NavigationController`, and `restore_focus()` for the clipboard-No path. Implementations are solid: `MissingCardsError` correctly subclasses `ValueError`, the placeholder-card pattern is preserved through speech, transient panel logic is well-tested, and `restore_focus()` correctly uses `wx.CallAfter`. No security issues, no critical bugs, no SQL injection (all DB calls parameterized).

The most material issue is encapsulation: `MainWindow._check_clipboard_for_deckstring` reaches into `NavigationController._panels` (a private attribute). Secondary issues: `HomePanel`'s `wx.ListBox` not synced with the presenter cursor (UX inconsistency vs `DeckContentsPanel`), and quality smells (duplicated `except` blocks, fragile string-prefix discriminator for placeholder cards).

## Warnings

### WR-01: NavigationController encapsulation violation in clipboard auto-import

**File:** `stonereader/app.py:323-328`

**Issue:** `MainWindow._check_clipboard_for_deckstring` accesses `self._nav._panels.get("Import Deck")` — reaching into a private attribute of `NavigationController` from outside the class. The `NavigationController` exposes `get_presenter()` but no `get_panel()`. This couples `MainWindow` to the controller's internal storage and silently breaks if `_panels` is renamed/restructured. It also forces an `isinstance(import_panel, ImportDeckPanel)` check inside an unrelated method.

**Fix:** Add a public accessor on `NavigationController`:
```python
def get_panel(self, name: str) -> wx.Panel | None:
    """Return the panel for a registered name, or None."""
    return self._panels.get(name)
```
Then in `_check_clipboard_for_deckstring`, replace `self._nav._panels.get("Import Deck")` with `self._nav.get_panel("Import Deck")`.

### WR-02: HomePanel never reflects presenter cursor in the wx.ListBox selection

**File:** `stonereader/views/home.py:36-48` (and `stonereader/presenters/home.py`)

**Issue:** `HomePresenter` maintains a zone cursor and announces "N of 3" via speech, but `HomePanel` never wires a state-changed callback. Compared to `DeckContentsPanel` (which calls `presenter.set_on_state_changed(self._on_state_changed)`), the home `wx.ListBox` selection always stays at index 0 visually. For sighted screen-reader users, mouse users, or anyone who tabs into the ListBox after navigating with arrows, the visual state diverges from the speech state. MSAA "selected item" property does not match the presenter's logical cursor — a screen reader querying the listbox directly will read the wrong item.

**Fix:** Add a state-changed callback in `HomePresenter` mirroring `DeckContentsPresenter`'s pattern, and have `HomePanel` bind `_list_box.SetSelection(cursor)` in the callback.

### WR-03: `_make_placeholder_card` produces a Card with `card_set=""` that may break group-by-set indexing

**File:** `stonereader/models/deck.py:23-38`

**Issue:** Placeholder cards are constructed with `card_set=""` (empty string) while real cards have non-empty enum values. If a future feature groups deck contents by set, or asks `CardDatabase.cards_by_set` about cards in a deck, the empty bucket may shadow logic. Same concern, smaller scale, applies to `card_class="NEUTRAL"` masquerading as a real class.

**Fix:** Either pick a sentinel (`card_set="UNKNOWN"`) and document it, or — preferred — add a Card-level discriminator (`is_placeholder: bool = False`). Then `count_unknown_cards` becomes `sum(count for card, count in deck.cards if card.is_placeholder)`.

### WR-04: `count_unknown_cards` uses fragile string-prefix discriminator

**File:** `stonereader/models/deck.py:41-48`

**Issue:** `count_unknown_cards` identifies placeholder cards via `card.id.startswith("UNKNOWN_")`. Couples the helper to the literal string emitted by `_make_placeholder_card`. If anyone changes the placeholder ID format, the counter silently returns 0 and the import success message stops mentioning unknown cards — a silent regression with no test failure unless a test pins the exact string.

**Fix:** Replace string check with a structural discriminator (see WR-03), or expose `_PLACEHOLDER_ID_PREFIX = "UNKNOWN_"` as a module-level constant used by both functions.

## Info

### IN-01: Local import inside `_check_clipboard_for_deckstring` runs on every window activation

**File:** `stonereader/app.py:303`

**Issue:** `from hearthstone.deckstrings import parse_deckstring` is imported lazily inside the method, which fires on every `wx.EVT_ACTIVATE`. First call pays the import cost; subsequent calls hit Python's import cache. The same symbol is plausibly already used elsewhere transitively via `Deck.from_deckstring`.

**Fix:** Move the import to the top of `app.py` alongside the other `hearthstone` imports.

### IN-02: Two near-identical `except` blocks in `validate_and_import`

**File:** `stonereader/presenters/import_deck.py:69-80`

**Issue:** `except ValueError` and `except TypeError` use identical message bodies. Maintenance hazard.

**Fix:**
```python
except (ValueError, TypeError):
    self._show_error(
        "Invalid deck code. Check that you copied the full "
        "code from Hearthstone and try again."
    )
    return False
```
Note: `MissingCardsError` is a `ValueError` subclass, so its handler must remain ordered before the combined clause.

### IN-03: `_on_open_deck` parameter typed as `object` with `# type: ignore[arg-type]`

**File:** `stonereader/app.py:433-437`

**Issue:** The lambda signature `def _on_open_deck(deck: object) -> None:` constructs `DeckContentsPresenter(speech, deck)` with `# type: ignore[arg-type]`. The `type: ignore` masks the contract instead of expressing it.

**Fix:** Type the parameter precisely (`def _on_open_deck(deck: Deck) -> None:` after a TYPE_CHECKING import) and remove the `# type: ignore`.

### IN-04: Shift-modifier rule comment does not match implementation

**File:** `stonereader/input_layer.py:45-48`

**Issue:** Comment says "Shift prefix for letter keys only — not arrows, enter, etc." but the check `if event.ShiftDown() and name not in _KEY_NAMES.values():` will also prefix digit and punctuation characters. shift+digit would emit `"shift+1"`.

**Fix:** Tighten implementation (`if event.ShiftDown() and name.isalpha() and len(name) == 1:`) and update comment, or broaden the comment. Also cache `_NAMED_KEYS = frozenset(_KEY_NAMES.values())` to avoid per-event O(n) scan.

### IN-05: `StoneReaderApp._frame` attribute lifecycle

**File:** `stonereader/app.py:347-459`

**Issue:** `StoneReaderApp` attaches `self._frame = MainWindow()` inside `OnInit`. There is no `__init__` and no class-level annotation. Currently nothing else reads it, so this is purely a hygiene note.

**Fix:** Either annotate at class scope (`_frame: MainWindow`) or skip the attribute and just `MainWindow().Show()` since nothing else needs the reference.

### IN-06: `_format_missing_cards_message` is private but tested directly

**File:** `stonereader/presenters/import_deck.py:110-126` and `tests/test_import_deck.py:221-242`

**Issue:** Method is underscore-prefixed (private convention) yet two tests call it directly through `presenter._format_missing_cards_message(...)`.

**Fix:** If the formatted string is part of the public contract (it is user-visible), drop the underscore. Otherwise drive validation through `validate_and_import` with `set_on_show_error` capturing the message.

### IN-07: `wx.App(False)` instantiated at module scope in two test files

**File:** `tests/test_input_layer.py:6` and `tests/test_navigation.py:12`

**Issue:** Each file creates `_app = wx.App(False)` at import time. wx allows only one `wx.App` per process; pytest collects both modules in the same process, so whichever imports second gets a no-op (or, on some wx versions, an error/warning). Construction order is undefined.

**Fix:** Move the `wx.App` setup to a session-scoped autouse fixture in `tests/conftest.py`:
```python
@pytest.fixture(scope="session", autouse=True)
def _wx_app():
    app = wx.App(False)
    yield app
```
Then drop the module-level `_app = wx.App(False)` from both test files.

---

_Reviewer: gsd-code-reviewer_
_Depth: standard_
_Reviewed: 2026-04-25_
_Note: Supersedes the 2026-04-15 review (which ran before gap-closure plans 01-05/06/07). Older findings should be cross-checked against current code before assuming resolution._
