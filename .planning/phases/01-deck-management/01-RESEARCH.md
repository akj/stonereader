# Phase 1: Deck Management - Research

**Researched:** 2026-04-15
**Domain:** wxPython desktop GUI, SQLite CRUD, screen reader accessibility, navigation architecture
**Confidence:** HIGH

## Summary

Phase 1 replaces the existing `wx.Notebook` tab shell with a home-screen navigation pattern and implements full deck management (import, browse, inspect, delete, export). The codebase already has strong foundations: `Deck.from_deckstring()` handles deckstring parsing, `ZoneNavigationMixin` provides reusable cursor-per-zone navigation, `db.py` has the `decks` table schema, and the CardBrowser provides a reference implementation for the MVP pattern.

The primary technical challenges are: (1) refactoring `MainWindow` from `wx.Notebook` to a panel-swap navigation stack, (2) implementing SQLite CRUD functions for deck persistence, (3) wiring clipboard auto-detection via `EVT_ACTIVATE`, and (4) extending `InputLayer._KEY_NAMES` to include the Delete key (currently unmapped). All components use established project patterns -- no new libraries, frameworks, or architectural departures needed.

**Primary recommendation:** Follow the existing CardBrowser MVP pattern exactly. Create `DeckManagerPresenter` + `DeckManagerPanel` and `DeckContentsPresenter` + `DeckContentsPanel` as separate presenter/view pairs. Build a `NavigationController` class to manage the panel-swap stack and replace `wx.Notebook`.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Replace `wx.Notebook` with a home screen pattern. The main window shows a vertical list of feature buttons (Card Library, Deck Manager, etc.). Selecting one replaces the home screen entirely with that feature's panel at full window size.
- **D-02:** Escape AND Backspace both navigate back up the chain (e.g. deck contents -> deck list -> home screen). Two paths to the same "back" action.
- **D-03:** No hotkeys for switching between features. Users always navigate through the home screen menu. Simple mental model -- one way to get places.
- **D-04:** Specific navigation widget pattern (button list, ListBox, etc.) to be researched -- the decision is "home screen with feature buttons," implementation details are researcher/planner territory.
- **D-05:** "Import Deck" is a separate action in the main menu / home screen, not embedded inside the Deck Manager panel. Dedicated import screen with deckstring and name fields.
- **D-06:** Clipboard auto-detection: when the app gains focus, check the clipboard for a valid deckstring. If found, pop a dialog offering to import it (like Hearthstone's deck paste behavior). Clear the deckstring from clipboard after successful import.
- **D-07:** Validation errors (invalid deckstring, missing cards) shown via `wx.MessageBox` error dialog. Screen readers auto-read dialog content.
- **D-08:** Deck list speech format: "Name, Class, Format, N of M" (e.g. "Aggro Paladin, Paladin, Standard, 1 of 5").
- **D-09:** Deck list sorted by most recently added first (newest at top). Uses the `created_at` column already in the database.
- **D-10:** Card list zone only -- no separate summary zone. Deck metadata (class, format, card count) is conveyed elsewhere (spoken when entering deck view, or available in the deck list itself).
- **D-11:** Enter on a deck in the list opens its card contents. Escape/Backspace returns to the deck list. Cursor position in the deck list is preserved across enter/exit.
- **D-12:** Card list uses standard zone navigation with detail inspection (down arrow reads card details line by line), same as CardBrowser.
- **D-13:** Delete confirmation via `wx.MessageDialog` with Yes/No buttons. "Delete 'Deck Name'? This cannot be undone." After deletion, cursor moves to next deck (or previous if it was the last).
- **D-14:** After deletion, speak "Deck Name deleted" as confirmation.
- **D-15:** Export (copy deckstring to clipboard) confirmed via speech announcement only: "Deckstring copied to clipboard." No dialog to dismiss.

### Claude's Discretion

- Specific hotkey assignments for delete, export, and import actions
- Layout details of the import screen (field order, button placement)
- How the home screen buttons are announced to screen readers
- Whether to announce deck metadata (card count, class) when first entering a deck's card list

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DECK-01 | User can import a deck by pasting a deckstring and naming it | `Deck.from_deckstring()` exists, `db.py` needs CRUD functions, ImportDeckPanel/Presenter needed, deckstring validation patterns documented |
| DECK-02 | User can browse saved decks in a navigable list | DeckManagerPresenter with ZoneNavigationMixin, custom `_format_item_speech()` for D-08 speech format, SQLite query ordered by `created_at DESC` |
| DECK-03 | User can view deck contents with card details via zone navigation | DeckContentsPresenter with ZoneNavigationMixin, `Deck.cards` tuples work directly with existing `_format_item_speech()` for `(Card, count)` tuples |
| DECK-04 | User can delete a saved deck with confirmation | `wx.MessageDialog` with `wx.YES_NO`, DELETE SQL, cursor repositioning logic, `WXK_DELETE` must be added to InputLayer `_KEY_NAMES` |
| DECK-05 | User can export a deck's deckstring to clipboard | `wx.TheClipboard` write pattern (already used in CardBrowser `_on_copy_card_name`), speech confirmation only |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deck persistence (CRUD) | Database / Storage | -- | SQLite `decks` table already exists; need query functions in `db.py` |
| Deck import/validation | Presenter | -- | `Deck.from_deckstring()` in model, validation logic in presenter, error display in view |
| Deck list navigation | Presenter | -- | ZoneNavigationMixin handles cursor state, speech; view renders ListCtrl passively |
| Deck contents inspection | Presenter | -- | Same pattern as CardBrowser -- presenter owns zone navigation and detail lines |
| Panel-swap navigation | Infrastructure | -- | New NavigationController in `app.py` replaces wx.Notebook; manages Show/Hide/Layout |
| Clipboard auto-detection | Infrastructure | Presenter | EVT_ACTIVATE handler in MainWindow checks clipboard, delegates to import flow |
| Speech output | Presenter | -- | All speech through `self._speech.speak()` per project rule |
| Delete confirmation | View (modal dialog) | Presenter | wx.MessageDialog is modal (blocks); presenter handles result and state update |
| Export to clipboard | View (clipboard API) | Presenter | Presenter provides deckstring, view handles wx.TheClipboard write (same as CardBrowser) |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| wxPython | 4.2.5 | GUI framework -- panels, sizers, dialogs, clipboard, events | Already installed and used throughout [VERIFIED: `uv run python -c "import wx; print(wx.__version__)"` returns 4.2.5] |
| hearthstone | 9.17.0 | Deckstring parsing via `deckstrings.parse_deckstring()` | Already installed, `Deck.from_deckstring()` wraps it [VERIFIED: installed in uv.lock] |
| sqlite3 | stdlib | Deck CRUD persistence | Already used in `db.py`, `decks` table schema exists [VERIFIED: codebase inspection] |
| accessible-output2 | 0.17 | Screen reader speech output | Already used via `SpeechService` wrapper [VERIFIED: installed in uv.lock] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 | Test framework for presenter and db tests | All new code needs tests [VERIFIED: 57 tests currently passing] |
| pyright | 1.1.402 | Static type checking | Run on all new files [VERIFIED: in pyproject.toml] |
| ruff | 0.12.2 | Linting and formatting | Run on all new files [VERIFIED: in pyproject.toml] |

### Alternatives Considered

No alternatives needed. This phase uses the established stack entirely. No new dependencies required.

**Installation:** No new packages needed. `uv sync` is sufficient.

## Architecture Patterns

### System Architecture Diagram

```
User Input (keyboard)
    |
    v
[InputLayer] -- EVT_CHAR_HOOK at frame level
    |
    |-- text mode? --> pass through to TextCtrl
    |-- Ctrl/Alt? --> pass through to OS/screen reader
    |-- key in active map? --> call presenter callback
    |-- "escape"/"back"? --> NavigationController.go_back()
    |-- "delete"? --> DeckManagerPresenter.delete_current_deck()
    |
    v
[Active Presenter] -- owns state, speech, key_map
    |
    |-- DeckManagerPresenter: deck list state, CRUD coordination
    |-- DeckContentsPresenter: card list for selected deck
    |-- HomePresenter: menu item selection
    |-- ImportDeckPresenter: validation, import flow
    |
    v
[SpeechService] -- announces to screen reader
    |
    v
[db.py CRUD] -- SQLite queries
    |
    v
[~/.stonereader/stonereader.db] -- persisted deck data
```

**Navigation flow (panel swap stack):**
```
Home Screen
    |-- Enter on "Card Library" --> CardBrowserPanel (Escape -> Home)
    |-- Enter on "Deck Manager" --> DeckManagerPanel (Escape -> Home)
    |       |-- Enter on deck --> DeckContentsPanel (Escape -> DeckManager)
    |-- Enter on "Import Deck" --> ImportDeckPanel (Escape -> Home, Success -> DeckManager)
```

### Recommended Project Structure

```
stonereader/
  presenters/
    deck_manager.py      # DeckManagerPresenter (deck list navigation, delete, export)
    deck_contents.py     # DeckContentsPresenter (card list for a single deck)
    import_deck.py       # ImportDeckPresenter (validation, import flow)
    home.py              # HomePresenter (menu navigation)
  views/
    deck_manager.py      # DeckManagerPanel (deck ListCtrl)
    deck_contents.py     # DeckContentsPanel (card ListCtrl)
    import_deck.py       # ImportDeckPanel (TextCtrl fields, buttons)
    home.py              # HomePanel (ListBox menu)
  app.py                 # MainWindow refactored: NavigationController replaces wx.Notebook
  db.py                  # Add CRUD functions: save_deck, get_all_decks, delete_deck
  input_layer.py         # Add WXK_DELETE to _KEY_NAMES
tests/
  test_deck_manager.py   # DeckManagerPresenter tests
  test_deck_contents.py  # DeckContentsPresenter tests (or combined)
  test_import_deck.py    # Import validation tests
  test_home.py           # Home navigation tests
  test_db_crud.py        # CRUD function tests (or extend test_db.py)
  test_navigation.py     # NavigationController tests
```

### Pattern 1: Panel-Swap Navigation (replaces wx.Notebook)

**What:** A `NavigationController` manages a stack of panel names. It shows/hides panels, calls `InputLayer.activate_view()`, and manages focus.

**When to use:** Whenever replacing the current wx.Notebook approach (D-01).

**Example:**
```python
# Source: wxPython panel swap pattern [CITED: docs.wxpython.org/wx.Sizer.html]
# Adapted to project conventions [VERIFIED: codebase inspection]

class NavigationController:
    """Manages panel visibility and navigation stack."""

    def __init__(
        self,
        frame: wx.Frame,
        sizer: wx.BoxSizer,
        input_layer: InputLayer,
    ) -> None:
        self._frame = frame
        self._sizer = sizer
        self._input_layer = input_layer
        self._panels: Dict[str, wx.Panel] = {}
        self._presenters: Dict[str, object] = {}
        self._focus_targets: Dict[str, wx.Window] = {}
        self._stack: list[str] = []

    def register_panel(
        self,
        name: str,
        panel: wx.Panel,
        presenter: object,
        focus_target: wx.Window,
    ) -> None:
        self._panels[name] = panel
        self._presenters[name] = presenter
        self._focus_targets[name] = focus_target
        self._sizer.Add(panel, 1, wx.EXPAND)
        panel.Hide()

    def show_panel(self, name: str) -> None:
        # Hide current
        if self._stack:
            current = self._stack[-1]
            self._panels[current].Hide()
        # Show new
        self._stack.append(name)
        self._panels[name].Show()
        self._sizer.Layout()
        # Activate key map
        presenter = self._presenters[name]
        get_map = getattr(presenter, "get_key_map", None)
        key_map = get_map() if get_map else {}
        self._input_layer.activate_view(name, key_map)
        # Set focus
        wx.CallAfter(self._focus_targets[name].SetFocus)

    def go_back(self) -> None:
        if len(self._stack) <= 1:
            return  # Already at home, nowhere to go
        self._panels[self._stack.pop()].Hide()
        current = self._stack[-1]
        self._panels[current].Show()
        self._sizer.Layout()
        presenter = self._presenters[current]
        get_map = getattr(presenter, "get_key_map", None)
        key_map = get_map() if get_map else {}
        self._input_layer.activate_view(current, key_map)
        wx.CallAfter(self._focus_targets[current].SetFocus)
```

### Pattern 2: DeckManagerPresenter (ZoneNavigationMixin)

**What:** Follows the exact same pattern as `CardBrowserPresenter` -- inherits `ZoneNavigationMixin` and `BasePresenter`, implements `get_zone_items()` and `get_key_map()`.

**When to use:** For the deck list browsing screen.

**Example:**
```python
# Source: CardBrowserPresenter pattern [VERIFIED: codebase inspection]

@dataclass(frozen=True)
class DeckSummary:
    """Lightweight deck info for list display."""
    deck_id: int
    name: str
    hero_class: str
    format: str
    deckstring: str
    created_at: str

class DeckManagerPresenter(ZoneNavigationMixin, BasePresenter):
    def __init__(
        self,
        speech: SpeechService,
        db_conn: sqlite3.Connection,
        card_db: CardDatabase,
    ) -> None:
        super().__init__(speech)
        self._db_conn = db_conn
        self._card_db = card_db
        self._decks: list[DeckSummary] = []
        self._init_navigation(["decks"])
        self._load_decks()

    def _load_decks(self) -> None:
        """Reload decks from database, sorted by created_at DESC (D-09)."""
        self._decks = get_all_decks(self._db_conn)
        # Reset cursor if out of bounds
        cursor = self._zone_cursors.get("decks", 0)
        if self._decks:
            self._zone_cursors["decks"] = min(cursor, len(self._decks) - 1)

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == "decks":
            return self._decks
        return []

    def _format_item_speech(self, item: Any, position: int, total: int) -> str:
        """Override for D-08 speech format."""
        if isinstance(item, DeckSummary):
            return f"{item.name}, {item.hero_class}, {item.format}, {position} of {total}"
        return super()._format_item_speech(item, position, total)
```

### Pattern 3: SQLite CRUD Functions

**What:** Pure functions in `db.py` that operate on a `sqlite3.Connection`. Follow existing pattern (no ORM, direct SQL).

**Example:**
```python
# Source: existing db.py patterns [VERIFIED: codebase inspection]

def save_deck(
    conn: sqlite3.Connection,
    name: str,
    hero_class: str,
    format_name: str,
    deckstring: str,
) -> int:
    """Insert a deck and return its id."""
    cursor = conn.execute(
        "INSERT INTO decks (name, hero_class, format, deckstring) VALUES (?, ?, ?, ?)",
        (name, hero_class, format_name, deckstring),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]

def get_all_decks(conn: sqlite3.Connection) -> list[DeckSummary]:
    """Return all decks ordered by newest first (D-09)."""
    rows = conn.execute(
        "SELECT id, name, hero_class, format, deckstring, created_at "
        "FROM decks ORDER BY created_at DESC"
    ).fetchall()
    return [
        DeckSummary(
            deck_id=row[0],
            name=row[1],
            hero_class=row[2],
            format=row[3],
            deckstring=row[4],
            created_at=row[5],
        )
        for row in rows
    ]

def delete_deck(conn: sqlite3.Connection, deck_id: int) -> None:
    """Delete a deck by id."""
    conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    conn.commit()
```

### Pattern 4: Clipboard Read for Auto-Detection (D-06)

**What:** On `EVT_ACTIVATE`, read clipboard text and try to parse as deckstring.

**Example:**
```python
# Source: wx.Clipboard docs [CITED: docs.wxpython.org/wx.Clipboard.html]
# Combined with hearthstone.deckstrings [VERIFIED: codebase inspection]

def _check_clipboard_for_deckstring(self) -> Optional[str]:
    """Return clipboard text if it looks like a valid deckstring."""
    if not wx.TheClipboard.Open():
        return None
    try:
        data = wx.TextDataObject()
        if not wx.TheClipboard.GetData(data):
            return None
        text = data.GetText().strip()
        if not text:
            return None
        # Try parsing -- catches ValueError, TypeError for invalid strings
        try:
            from hearthstone.deckstrings import parse_deckstring
            parse_deckstring(text)
            return text
        except (ValueError, TypeError, Exception):
            return None
    finally:
        wx.TheClipboard.Close()
```

### Pattern 5: Import Validation with Error Dialogs (D-07)

**What:** Validate deckstring and name before import, show `wx.MessageBox` on error.

**Example:**
```python
# Source: D-07, error copy from UI-SPEC [VERIFIED: 01-UI-SPEC.md]

def _validate_and_import(self, deckstring: str, name: str) -> bool:
    """Validate inputs and import deck. Returns True on success."""
    if not deckstring.strip():
        wx.MessageBox(
            "Enter a deck code to import.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False
    if not name.strip():
        wx.MessageBox(
            "Enter a name for this deck.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False
    try:
        deck = Deck.from_deckstring(deckstring.strip(), self._card_db, name.strip())
    except ValueError:
        wx.MessageBox(
            "Some cards in this deck were not found in the card database. "
            "The deck code may be from a newer expansion.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False
    except (TypeError, Exception):
        wx.MessageBox(
            "Invalid deck code. Check that you copied the full code from "
            "Hearthstone and try again.",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False
    # Save to database
    save_deck(self._db_conn, deck.name, deck.hero_class, deck.format, deckstring.strip())
    self._speech.speak(f"{deck.name} imported")
    return True
```

### Anti-Patterns to Avoid

- **Views calling SpeechService:** Views never call `self._speech` directly. Only presenters speak. This is a project invariant. [VERIFIED: CLAUDE.md]
- **Mutating frozen dataclasses:** `Deck` is frozen. Never try `deck.name = "new"`. Construct new instances. [VERIFIED: CLAUDE.md]
- **Using EVT_KEY_DOWN instead of EVT_CHAR_HOOK:** EVT_KEY_DOWN is intercepted by NVDA/JAWS hooks. Must use EVT_CHAR_HOOK for screen reader compatibility. [VERIFIED: input_layer.py comments]
- **Relative imports:** Project uses absolute imports only (`from stonereader.models.card import Card`). [VERIFIED: CLAUDE.md conventions]
- **Keeping wx.Notebook:** D-01 explicitly replaces it. Do not add tabs -- use the NavigationController panel-swap pattern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deckstring parsing | Custom base64 decoder | `hearthstone.deckstrings.parse_deckstring()` | Handles sideboard, format detection, hero extraction [VERIFIED: already used in `Deck.from_deckstring()`] |
| Screen reader output | Platform-specific NVDA/JAWS APIs | `SpeechService` wrapping `accessible_output2` | Cross-reader compatibility with fallback [VERIFIED: existing infrastructure] |
| Clipboard access | ctypes/win32clipboard | `wx.TheClipboard` | Cross-platform, wxPython native, already used in CardBrowser [VERIFIED: `views/card_browser.py`] |
| Zone navigation | Custom cursor logic | `ZoneNavigationMixin` | Cursor persistence, diminishing messages, detail inspection all built in [VERIFIED: `presenters/base.py`] |
| Dialog boxes | Custom panels for confirmations | `wx.MessageDialog` / `wx.MessageBox` | Screen readers auto-read modal dialog content [ASSUMED] |
| Labeled text inputs | Manual MSAA configuration | `make_labeled_text_ctrl()` | Places StaticText before TextCtrl for MSAA sibling order [VERIFIED: `views/base.py`] |

**Key insight:** This phase requires zero new libraries. Every capability needed already exists in the codebase or in wxPython's standard toolkit. The work is wiring existing pieces together following established patterns.

## Common Pitfalls

### Pitfall 1: WXK_DELETE Not Mapped in InputLayer

**What goes wrong:** The Delete key won't fire any callback because `_KEY_NAMES` in `input_layer.py` doesn't include `wx.WXK_DELETE`.
**Why it happens:** The current feature (CardBrowser) doesn't need Delete, so it was never added.
**How to avoid:** Add `wx.WXK_DELETE: "delete"` to the `_KEY_NAMES` dictionary before implementing the deck delete feature.
**Warning signs:** Delete key presses are silently ignored (event passes through via `event.Skip()`). [VERIFIED: `input_layer.py` inspection -- WXK_DELETE absent from `_KEY_NAMES`]

### Pitfall 2: Deckstring Parsing Raises Multiple Exception Types

**What goes wrong:** Catching only `ValueError` misses `TypeError` from malformed base64 input.
**Why it happens:** `hearthstone.deckstrings.parse_deckstring()` raises `ValueError` for empty/invalid format but `TypeError` for truncated base64 data.
**How to avoid:** Catch `(ValueError, TypeError, Exception)` as a broad safety net around `parse_deckstring()`.
**Warning signs:** Unhandled exception crash when user pastes garbage text. [VERIFIED: tested `parse_deckstring()` with multiple invalid inputs]

### Pitfall 3: Sizer Layout Not Called After Panel Show/Hide

**What goes wrong:** Panel appears with wrong size or doesn't appear at all after `Show()`/`Hide()`.
**Why it happens:** wxPython sizers don't automatically recalculate when child visibility changes.
**How to avoid:** Always call `self._sizer.Layout()` after changing panel visibility. Consider `Freeze()`/`Thaw()` on the frame to prevent flicker. [CITED: docs.wxpython.org/wx.Sizer.html]
**Warning signs:** Panel visually glitches or remains invisible despite `IsShown()` returning True.

### Pitfall 4: Focus Not Set After Panel Swap

**What goes wrong:** After navigating to a new panel, keyboard focus stays on the old (now hidden) panel. Screen reader goes silent.
**Why it happens:** `Show()`/`Hide()` don't move focus. Focus must be explicitly set.
**How to avoid:** Use `wx.CallAfter(target.SetFocus)` after `Layout()` to ensure focus moves after the event loop completes. [VERIFIED: existing pattern in `app.py:_on_page_changed`]
**Warning signs:** First keypress after navigation does nothing or goes to wrong handler.

### Pitfall 5: Clipboard Auto-Detection Firing Repeatedly

**What goes wrong:** Every time the window gains focus (clicking between apps), the deckstring dialog pops up even though the user already dismissed it.
**Why it happens:** `EVT_ACTIVATE` fires on every focus gain. Clipboard content persists.
**How to avoid:** Track the last detected deckstring. Only show dialog if clipboard content differs from the last checked value. Clear clipboard after successful import (D-06). Also suppress during initial app launch. [ASSUMED]
**Warning signs:** Dialog keeps appearing every time user alt-tabs back to the app.

### Pitfall 6: Text Mode Not Toggling on Import Screen TextCtrls

**What goes wrong:** Typing in the deckstring or name field triggers hotkey callbacks (e.g., "c" for copy) instead of text input.
**Why it happens:** Forgot to call `bind_text_mode(ctrl, input_layer)` on the import screen's TextCtrl widgets.
**How to avoid:** Use `make_labeled_text_ctrl()` which calls `bind_text_mode()` internally, matching the CardBrowser pattern. [VERIFIED: `views/base.py:make_labeled_text_ctrl()` calls `bind_text_mode()`]
**Warning signs:** Typing letters triggers deck operations instead of filling text fields.

### Pitfall 7: Cursor Position After Deck Deletion

**What goes wrong:** After deleting a deck, the cursor position is invalid (points past end of list, or shows wrong deck).
**Why it happens:** The deck list is reloaded from database but cursor isn't adjusted.
**How to avoid:** After deletion, if cursor >= new list length, set cursor to `len(decks) - 1`. If list is empty, announce "no saved decks". Per D-13, cursor moves to next deck (or previous if last). [VERIFIED: D-13 from CONTEXT.md]
**Warning signs:** Index out of range errors or silent failures when navigating after delete.

### Pitfall 8: Deck.from_deckstring() Uses format_data as Integer

**What goes wrong:** The `Deck` model stores format as a string ("Standard"/"Wild") but `parse_deckstring` returns a `FormatType` enum.
**Why it happens:** `Deck.from_deckstring()` already handles this conversion correctly: `"Standard" if format_data == 2 else "Wild"`.
**How to avoid:** Always use `Deck.from_deckstring()` rather than calling `parse_deckstring()` directly for import -- the model handles conversion. The `format` column in the database stores the string ("Standard"/"Wild"). [VERIFIED: `models/deck.py` line 68-69]
**Warning signs:** Format shows as "2" or "FT_STANDARD" instead of "Standard" in the deck list.

## Code Examples

### Verified: Existing Clipboard Write Pattern
```python
# Source: stonereader/views/card_browser.py line 112-116 [VERIFIED: codebase]
def _on_copy_card_name(self, event: wx.CommandEvent) -> None:
    name = self._presenter.copy_current_card_name()
    if name is not None and wx.TheClipboard.Open():
        wx.TheClipboard.SetData(wx.TextDataObject(name))
        wx.TheClipboard.Close()
```

### Verified: Existing Tab Registration Pattern (will be replaced)
```python
# Source: stonereader/app.py line 63-78 [VERIFIED: codebase]
# This pattern will be replaced by NavigationController.register_panel()
def add_tab(self, panel, name, presenter, focus_target):
    self._notebook.AddPage(panel, name)
    self._tab_presenters.append(presenter)
    self._tab_focus_targets.append(focus_target)
    self._tab_names.append(name)
    if len(self._tab_presenters) == 1:
        get_map = getattr(presenter, "get_key_map", None)
        key_map = get_map() if get_map is not None else {}
        self._input_layer.activate_view(name, key_map)
```

### Verified: Existing ZoneNavigationMixin Usage
```python
# Source: stonereader/presenters/card_browser.py [VERIFIED: codebase]
class CardBrowserPresenter(ZoneNavigationMixin, BasePresenter):
    def __init__(self, speech: SpeechService, card_db: CardDatabase) -> None:
        super().__init__(speech)
        self._card_db = card_db
        self._results: list[Card] = sorted(card_db.collectible_cards, key=lambda c: c.name)
        self._init_navigation([_RESULTS_ZONE])
        # Callbacks for view sync
        self._on_state_changed: Callable[[list[Card], int], None] | None = None
        self._on_status_changed: Callable[[str], None] | None = None
```

### Verified: wx.MessageDialog Pattern
```python
# Source: wxPython standard pattern [CITED: docs.wxpython.org/wx.MessageDialog.html]
dialog = wx.MessageDialog(
    parent,
    f"Delete '{deck_name}'? This cannot be undone.",
    "Delete Deck",
    wx.YES_NO | wx.ICON_WARNING,
)
result = dialog.ShowModal()
dialog.Destroy()
if result == wx.ID_YES:
    delete_deck(self._db_conn, deck_id)
    self._speech.speak(f"{deck_name} deleted")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| wx.Notebook tabs | Panel-swap navigation | Phase 1 (now) | Only one tab exists currently, so migration cost is minimal |
| No CRUD in db.py | db.py gains save/get/delete functions | Phase 1 (now) | Schema already exists, just need query functions |
| No home screen | Home screen with ListBox menu | Phase 1 (now) | New entry point for all features |

**Deprecated/outdated:**
- `MainWindow.add_tab()`: Will be replaced by `NavigationController.register_panel()`. The wx.Notebook and all tab-tracking lists (`_tab_presenters`, `_tab_focus_targets`, `_tab_names`) will be removed.
- `wx.Notebook` references in `app.py`: All notebook code will be refactored out.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `wx.MessageDialog` content is auto-read by NVDA/JAWS | Don't Hand-Roll | Dialogs might need explicit screen reader announcements -- but wx modal dialogs are standard MSAA objects, very likely auto-read |
| A2 | Clipboard auto-detection should suppress on initial app launch | Pitfall 5 | If not suppressed, dialog might pop on first launch if clipboard has a deckstring from previous copy |
| A3 | `Freeze()`/`Thaw()` around panel swaps prevents visual flicker | Pitfall 3 | May not be noticeable on this simple UI, but good practice for smooth transitions |

## Open Questions

1. **Home Screen Widget: wx.ListBox vs. wx.ListCtrl**
   - What we know: UI-SPEC specifies `wx.ListBox` for the home screen feature menu. This is simpler than ListCtrl and standard for menu-like selection.
   - What's unclear: Whether a ListBox provides the same MSAA accessibility as ListCtrl for screen readers.
   - Recommendation: Use `wx.ListBox` as specified in the UI-SPEC. It's a standard control and NVDA/JAWS handle it natively. If issues arise during manual testing, can swap to ListCtrl. [ASSUMED: ListBox MSAA support]

2. **DeckContentsPresenter: Separate Class vs. Mode of DeckManagerPresenter**
   - What we know: UI-SPEC suggests either approach is valid. CardBrowser uses a separate presenter per panel.
   - What's unclear: Whether coupling deck-contents into DeckManagerPresenter is simpler or more complex.
   - Recommendation: Use a separate `DeckContentsPresenter` class. Matches the one-presenter-per-panel pattern. DeckManagerPresenter passes the selected `DeckSummary` (with deckstring) to DeckContentsPresenter on enter. Separation keeps each class focused.

3. **Where DeckSummary Model Lives**
   - What we know: Need a lightweight data class for deck list items (id, name, class, format, deckstring, created_at).
   - What's unclear: Whether it belongs in `models/` or `db.py`.
   - Recommendation: Define `DeckSummary` as a frozen dataclass in `stonereader/models/deck.py` alongside `Deck`. It's a domain model. `db.py` imports it for query result mapping.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | pyproject.toml (implicit) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DECK-01 | Import deck from deckstring | unit | `uv run pytest tests/test_import_deck.py -x` | Wave 0 |
| DECK-01 | Invalid deckstring shows error | unit | `uv run pytest tests/test_import_deck.py::test_invalid_deckstring -x` | Wave 0 |
| DECK-01 | Empty name rejected | unit | `uv run pytest tests/test_import_deck.py::test_empty_name_rejected -x` | Wave 0 |
| DECK-02 | Browse saved decks | unit | `uv run pytest tests/test_deck_manager.py -x` | Wave 0 |
| DECK-02 | Deck list speech format "Name, Class, Format, N of M" | unit | `uv run pytest tests/test_deck_manager.py::test_speech_format -x` | Wave 0 |
| DECK-02 | Decks sorted newest first | unit | `uv run pytest tests/test_deck_manager.py::test_sort_order -x` | Wave 0 |
| DECK-03 | View deck contents with detail inspection | unit | `uv run pytest tests/test_deck_contents.py -x` | Wave 0 |
| DECK-03 | Metadata spoken on enter | unit | `uv run pytest tests/test_deck_contents.py::test_metadata_announced -x` | Wave 0 |
| DECK-04 | Delete deck with confirmation | unit | `uv run pytest tests/test_deck_manager.py::test_delete_deck -x` | Wave 0 |
| DECK-04 | Cursor repositions after delete | unit | `uv run pytest tests/test_deck_manager.py::test_cursor_after_delete -x` | Wave 0 |
| DECK-05 | Export deckstring to clipboard | unit | `uv run pytest tests/test_deck_manager.py::test_export_deckstring -x` | Wave 0 |
| N/A | SQLite CRUD (save, get_all, delete) | unit | `uv run pytest tests/test_db.py -x` | Extend existing |
| N/A | NavigationController panel swap | unit | `uv run pytest tests/test_navigation.py -x` | Wave 0 |
| N/A | Home screen navigation | unit | `uv run pytest tests/test_home.py -x` | Wave 0 |
| N/A | Delete key mapped in InputLayer | unit | `uv run pytest tests/test_input_layer.py -x` | Extend existing |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_deck_manager.py` -- covers DECK-02, DECK-04, DECK-05
- [ ] `tests/test_deck_contents.py` -- covers DECK-03
- [ ] `tests/test_import_deck.py` -- covers DECK-01
- [ ] `tests/test_home.py` -- covers home screen navigation
- [ ] `tests/test_navigation.py` -- covers NavigationController panel swap
- [ ] Extend `tests/test_db.py` with CRUD function tests
- [ ] Extend `tests/test_input_layer.py` with WXK_DELETE key spec test

## Security Domain

Security enforcement does not apply to this phase. This is a local desktop application with no network endpoints, no user authentication, no remote data access, and no secrets management. All data is stored locally in `~/.stonereader/stonereader.db` (user-only access via OS permissions).

The only relevant concern is **SQL injection**, which is mitigated by using parameterized queries (`?` placeholders) in all `db.py` functions. [VERIFIED: existing `db.py` uses parameterized queries in `test_db.py`]

## Project Constraints (from CLAUDE.md)

Extracted from project `CLAUDE.md` and root `~/CLAUDE.md`:

- **Frozen dataclasses** for all game state models -- never mutate, construct new instances
- **Views never call SpeechService directly** -- only presenters call `self._speech`
- **Zone keys are always global** -- no enter/exit required
- **Ctrl/Alt combinations always pass through** InputLayer
- **`Card.to_speech_text()` returns name only** -- do not add verbosity parameters
- **EVT_CHAR_HOOK** at frame level (not EVT_KEY_DOWN) -- required for NVDA/JAWS compatibility
- **Absolute imports only** -- `from stonereader.models.card import Card` (no relative imports)
- **Module-level docstrings** on all files
- **Google-style docstrings** on public methods
- **Type hints required** on all function signatures
- **Ruff format + check** must pass
- **Pyright** type checking must pass
- **MVP pattern** -- presenters own state and speech, views are passive widgets
- **`make_labeled_text_ctrl()`** for labeled text inputs (MSAA sibling order)
- **`bind_text_mode()`** on all TextCtrl widgets
- **Accessibility-first**: WCAG AA standards for all web UI (though this is a wxPython desktop app, the principle of screen reader compatibility applies)
- **`uv run pytest tests/ -v`** for running tests
- **`uv run pyright`** for type checking
- **`uv run ruff check .`** for linting
- **`uv run ruff format .`** for formatting

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `stonereader/app.py`, `stonereader/presenters/base.py`, `stonereader/presenters/card_browser.py`, `stonereader/views/card_browser.py`, `stonereader/views/base.py`, `stonereader/models/deck.py`, `stonereader/db.py`, `stonereader/input_layer.py`
- Codebase inspection: `tests/conftest.py`, `tests/test_card_browser.py`, `tests/test_db.py`, `tests/test_zone_navigation.py`
- Phase context: `.planning/phases/01-deck-management/01-CONTEXT.md`
- UI specification: `.planning/phases/01-deck-management/01-UI-SPEC.md`
- Project structure: `.planning/codebase/STRUCTURE.md`
- Runtime verification: `hearthstone.deckstrings.parse_deckstring()` tested with valid and invalid inputs
- Runtime verification: `wx.WXK_DELETE` confirmed as key code 127, not in `_KEY_NAMES`
- Runtime verification: `wxPython 4.2.5` confirmed installed, `pytest 57 tests` passing

### Secondary (MEDIUM confidence)
- [wxPython Sizer docs](https://docs.wxpython.org/wx.Sizer.html) -- Show/Hide/Layout pattern
- [wxPython Clipboard docs](https://docs.wxpython.org/wx.Clipboard.html) -- clipboard read/write
- [wxPython Panel Switching (Mouse vs Python)](https://www.blog.pythonlibrary.org/2010/06/16/wxpython-how-to-switch-between-panels/) -- panel swap pattern
- [Context7: wxwidgets/phoenix](https://github.com/wxwidgets/phoenix) -- sizer flags, visibility

### Tertiary (LOW confidence)
- None -- all findings verified against codebase or official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all verified as installed
- Architecture: HIGH -- follows exact patterns already in codebase (CardBrowser reference implementation)
- Pitfalls: HIGH -- verified through runtime testing (deckstring exceptions, missing key mapping) and codebase inspection
- Navigation refactor: MEDIUM -- panel-swap pattern is well-documented but the NavigationController is new code; the specific interaction with InputLayer.activate_view() and focus management needs careful implementation

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable stack, no fast-moving dependencies)
