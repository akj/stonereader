# Phase 1: Deck Management - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can manage a library of Hearthstone decks entirely through keyboard and screen reader. This includes importing deckstrings, browsing saved decks, inspecting deck contents, deleting decks, and exporting deckstrings to clipboard.

**This phase also includes refactoring the app shell** from `wx.Notebook` tabs to a home-screen-based navigation pattern. This is the right time — only one tab (Card Library) exists today, so migration cost is minimal.

</domain>

<decisions>
## Implementation Decisions

### App Shell / Navigation

- **D-01:** Replace `wx.Notebook` with a home screen pattern. The main window shows a vertical list of feature buttons (Card Library, Deck Manager, etc.). Selecting one replaces the home screen entirely with that feature's panel at full window size.
- **D-02:** Escape AND Backspace both navigate back up the chain (e.g. deck contents → deck list → home screen). Two paths to the same "back" action.
- **D-03:** No hotkeys for switching between features. Users always navigate through the home screen menu. Simple mental model — one way to get places.
- **D-04:** Specific navigation widget pattern (button list, ListBox, etc.) to be researched — the decision is "home screen with feature buttons," implementation details are researcher/planner territory.

### Import Workflow

- **D-05:** "Import Deck" is a separate action in the main menu / home screen, not embedded inside the Deck Manager panel. Dedicated import screen with deckstring and name fields.
- **D-06:** Clipboard auto-detection: when the app gains focus, check the clipboard for a valid deckstring. If found, pop a dialog offering to import it (like Hearthstone's deck paste behavior). Clear the deckstring from clipboard after successful import.
- **D-07:** Validation errors (invalid deckstring, missing cards) shown via `wx.MessageBox` error dialog. Screen readers auto-read dialog content.

### Deck List Display

- **D-08:** Deck list speech format: "Name, Class, Format, N of M" (e.g. "Aggro Paladin, Paladin, Standard, 1 of 5").
- **D-09:** Deck list sorted by most recently added first (newest at top). Uses the `created_at` column already in the database.

### Deck Contents Navigation

- **D-10:** Card list zone only — no separate summary zone. Deck metadata (class, format, card count) is conveyed elsewhere (spoken when entering deck view, or available in the deck list itself).
- **D-11:** Enter on a deck in the list opens its card contents. Escape/Backspace returns to the deck list. Cursor position in the deck list is preserved across enter/exit.
- **D-12:** Card list uses standard zone navigation with detail inspection (down arrow reads card details line by line), same as CardBrowser.

### Delete and Export

- **D-13:** Delete confirmation via `wx.MessageDialog` with Yes/No buttons. "Delete 'Deck Name'? This cannot be undone." After deletion, cursor moves to next deck (or previous if it was the last).
- **D-14:** After deletion, speak "Deck Name deleted" as confirmation.
- **D-15:** Export (copy deckstring to clipboard) confirmed via speech announcement only: "Deckstring copied to clipboard." No dialog to dismiss.

### Claude's Discretion

- Specific hotkey assignments for delete, export, and import actions
- Layout details of the import screen (field order, button placement)
- How the home screen buttons are announced to screen readers
- Whether to announce deck metadata (card count, class) when first entering a deck's card list

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Code (required reading)
- `stonereader/app.py` — Current `MainWindow` and `StoneReaderApp.OnInit()` — must be refactored for new navigation
- `stonereader/presenters/base.py` — `BasePresenter` and `ZoneNavigationMixin` — all new presenters inherit these
- `stonereader/presenters/card_browser.py` — Reference implementation for zone navigation presenter
- `stonereader/views/card_browser.py` — Reference implementation for view panel
- `stonereader/views/base.py` — `make_labeled_text_ctrl()` and `bind_text_mode()` helpers
- `stonereader/models/deck.py` — Existing `Deck` model with `from_deckstring()`, card list, stats
- `stonereader/db.py` — SQLite schema with `decks` table, `get_connection()`, `init_db()`
- `stonereader/input_layer.py` — `InputLayer` key routing — `activate_view()` must work with new navigation

### Architecture Maps
- `.planning/codebase/STRUCTURE.md` — "Where to Add New Code" section has the exact pattern for new features
- `.planning/codebase/CONVENTIONS.md` — Naming, code style, import organization

### Requirements
- `.planning/REQUIREMENTS.md` §Deck Management — DECK-01 through DECK-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Deck.from_deckstring()` — Already parses deckstrings, resolves cards, detects hero class and format
- `ZoneNavigationMixin` — Cursor-per-zone, detail inspection, diminishing messages — deck card list navigation
- `make_labeled_text_ctrl()` — Creates NVDA/JAWS-compatible labeled text inputs for import screen
- `bind_text_mode()` — Text mode toggle for TextCtrl fields
- `MainWindow.add_tab()` — Will be replaced, but the key_map swap pattern it demonstrates carries over
- `db.py` `decks` table — Schema already has name, hero_class, format, deckstring, created_at columns
- `_format_item_speech()` — Handles (Card, count) tuples — reusable for deck card list

### Established Patterns
- MVP: Presenters own state + speech, views are passive widgets
- `get_key_map()` returns `Dict[str, Callable[[], None]]` — InputLayer swaps on view change
- `_notify_view()` callback pattern syncs presenter state → view display
- Frozen dataclasses for all models — Deck is already frozen
- Text mode guard on EVT_CHAR_HOOK — import fields need this

### Integration Points
- `StoneReaderApp.OnInit()` — Currently creates CardBrowser and adds tab; needs refactor to create home screen + register all features
- `InputLayer.activate_view()` — Currently called on page change; needs to be called on panel show/hide instead
- `db.py` — Need CRUD functions for decks (currently only schema + init, no query functions)

</code_context>

<specifics>
## Specific Ideas

- Clipboard auto-detection should work like Hearthstone's deck paste: app gains focus → detects deckstring on clipboard → pops dialog to import → clears clipboard after import
- Navigation back chain: Escape and Backspace both go up one level (deck contents → deck list → home screen)
- Home screen is the "hub" — no shortcut keys between features, always navigate through home

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-deck-management*
*Context gathered: 2026-04-15*
