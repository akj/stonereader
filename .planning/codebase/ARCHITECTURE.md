# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview

**Overall:** MVP (Model-View-Presenter) with accessibility-first design and zone-based keyboard navigation.

**Key Characteristics:**
- Models are immutable frozen dataclasses — never mutated, only reconstructed
- Presenters manage state, speech announcements, and keyboard navigation
- Views are passive wxPython widgets that bind to presenter callbacks
- Keyboard routing via EVT_CHAR_HOOK (required for NVDA/JAWS compatibility)
- Screen reader output via accessible_output2 with stdout fallback

## Layers

**Models Layer:**
- Purpose: Domain entities representing Hearthstone game concepts
- Location: `stonereader/models/`
- Contains: `Card`, `CardDatabase`, `Deck`, `Hero`, `GameEntity`, `GameState`, `ReplayState`
- Depends on: hearthstone library for enums and card XML loading
- Used by: Presenters and Views
- All models use `@dataclass(frozen=True)` to enforce immutability

**Presenter Layer:**
- Purpose: State management, zone-based navigation logic, speech announcements
- Location: `stonereader/presenters/`
- Contains: `BasePresenter`, `ZoneNavigationMixin`, `CardBrowserPresenter`
- Depends on: Models, SpeechService, InputLayer (indirectly through views)
- Used by: Views to handle state changes and key events
- Presenters expose `get_key_map()` returning dict of hotkey → callback

**View Layer:**
- Purpose: Render wxPython widgets and display state visually
- Location: `stonereader/views/`
- Contains: `CardBrowserPanel`, `_CardListCtrl`, view helper functions
- Depends on: Presenters (via callbacks), InputLayer, wx
- Used by: MainWindow (adds tabs)
- Views never call SpeechService directly — only presenters speak

**Infrastructure Layer:**
- Location: `stonereader/`
- Contains: `app.py` (MainWindow, StoneReaderApp), `speech_service.py`, `input_layer.py`, `db.py`
- Responsibilities:
  - **app.py**: wx.Frame shell, Notebook (tabs), tab registration, database initialization
  - **input_layer.py**: EVT_CHAR_HOOK routing, text mode lifecycle, hotkey dispatch
  - **speech_service.py**: Screen reader abstraction (accessible_output2 with stdout fallback)
  - **db.py**: SQLite schema, connection pooling, migrations

**Database Layer:**
- Location: `stonereader/db.py`
- Purpose: Persist decks and game history
- Tables: `schema_version`, `decks`, `games`
- Connection: `~/.stonereader/stonereader.db` (created on first run)

## Data Flow

**Application Startup:**

1. `__main__.py` calls `StoneReaderApp().MainLoop()`
2. `StoneReaderApp.OnInit()`:
   - Creates `MainWindow` (wx.Frame)
   - MainWindow initializes: SpeechService, InputLayer, SQLite connection
   - Card Library tab instantiated:
     - `CardDatabase.load()` parses hearthstone library
     - `CardBrowserPresenter` created with speech and card_db
     - `CardBrowserPanel` created with presenter and input_layer
     - Panel added to notebook via `MainWindow.add_tab()`
   - MainWindow shown, event loop starts

**Keyboard Input → Action:**

1. User presses key
2. wxPython fires `EVT_CHAR_HOOK` at MainWindow (before native handlers)
3. InputLayer dispatches:
   - If in text mode → event.Skip() (keys go to TextCtrl)
   - If Ctrl/Alt held → event.Skip() (pass through)
   - If key in presenter's key_map → call callback, consume event
   - Otherwise → event.Skip()
4. Callback (e.g., `move_in_zone(-1)`) updates presenter state
5. Presenter calls `_notify_view()` to sync visual ListCtrl
6. Presenter calls `self._speech.speak()` for announcement
7. View receives callback, updates display

**Tab Switch:**

1. User clicks Notebook tab
2. MainWindow._on_page_changed():
   - Gets presenter from tab index
   - Calls InputLayer.activate_view() with new presenter's key_map
   - Sets focus to tab's focus_target (e.g., CardBrowserPanel)
3. New presenter's hotkeys now active

**Card Search:**

1. User types in CardBrowserPanel search TextCtrl
2. EVT_SET_FOCUS fires → InputLayer.enter_text_mode()
3. Keys bypass hotkey dispatch, reach TextCtrl
4. User presses Enter
5. EVT_TEXT_ENTER fires → CardBrowserPanel._on_search()
6. CardBrowserPanel calls CardBrowserPresenter.search(query)
7. Presenter:
   - Calls CardDatabase.search_cards(query)
   - Updates self._results
   - Announces result count via self._speech.speak()
   - Calls self._notify_view()
8. View:
   - Receives _on_state_changed(results, cursor)
   - Updates ListCtrl display
   - Syncs selection to cursor position

**Detail Inspection (Down Arrow):**

1. User presses Down
2. InputLayer dispatches to presenter.get_key_map()["down"]
3. CardBrowserPresenter._read_detail_down():
   - Gets current item via _current_item()
   - Calls read_detail_lines(item, direction=1)
4. read_detail_lines():
   - Extracts Card from item
   - Gets card.detail_lines() (ordered list of attributes)
   - Moves _detail_cursor forward
   - Speaks lines[_detail_cursor]
5. Screen reader announces next detail line

## State Management

**Zone Navigation State:**
- `_current_zone`: Active zone name (e.g., "results")
- `_zone_cursors`: Dict[zone_name → cursor_position]
- `_detail_cursor`: Position in current card's detail_lines
- `_orienting_counts`: Tracks diminishing message press counts per key

**Text Mode State:**
- `_text_mode`: Boolean flag in InputLayer
- Toggled by TextCtrl focus events via EVT_SET_FOCUS/EVT_KILL_FOCUS
- When True, all keystrokes skip hotkey dispatch

**Search State:**
- `_results`: Current list of Card objects (sorted by name)
- Updated by `CardBrowserPresenter.search(query)`
- Synced to view via `_notify_view()` callback

## Key Abstractions

**ZoneNavigationMixin:**
- Purpose: Reusable keyboard navigation for lists (zones)
- Pattern: Each zone maintains independent cursor position
- Used by: CardBrowserPresenter (and will be used by DeckManagerPresenter, ReplayViewerPresenter)
- Methods: navigate_to_zone(), move_in_zone(), jump_to_position(), read_detail_lines()
- Speech: Announces position via `N of M` suffix

**InputLayer:**
- Purpose: Decouple hotkey routing from view event handling
- Pattern: Single active key_map per view, swapped on tab change
- Text mode: Disables all hotkey processing when TextCtrl focused
- Rules: Text mode > Ctrl/Alt passthrough > key_map lookup > passthrough

**SpeechService:**
- Purpose: Cross-reader speech output abstraction
- Pattern: Wraps accessible_output2.Auto, falls back to stdout
- Methods: speak(text, interrupt=True), speak_queued(text)
- Resilience: Catches all exceptions, prints to stdout as fallback

**CardDatabase:**
- Purpose: In-memory search and lookup of all cards
- Indexes: by_id, by_dbf_id, by_name, by_class, by_type, by_set, by_cost
- Loaded once at startup via hearthstone.cardxml.load()
- Immutable after creation

## Entry Points

**Application Entry:**
- Location: `stonereader/__main__.py`
- Triggers: `python -m stonereader` or `python stonereader/`
- Responsibilities: Creates StoneReaderApp, starts MainLoop

**MainWindow.__init__:**
- Location: `stonereader/app.py`
- Triggers: Called by StoneReaderApp.OnInit()
- Responsibilities: Initialize frame, widgets, database, speech, input routing

**Card Library Tab:**
- Location: `stonereader/app.py` (OnInit)
- Triggers: Application startup
- Responsibilities: Load cards, create presenter, create panel, register tab

## Error Handling

**Strategy:** Fail gracefully with fallback behavior.

**Patterns:**
- SpeechService: Exceptions caught, output falls back to stdout
- CardDatabase: Missing cards raise ValueError with dbf_id list (during deck import)
- Input validation: Card search filters silently ignore non-matching cards (returns empty list)
- Database: Schema migrations idempotent (check version before creating tables)

## Cross-Cutting Concerns

**Logging:** Not implemented. Speech output via SpeechService is primary signal.

**Validation:** Model fields are frozen dataclass attributes — immutability enforces consistency. Card text stripped of HTML at load time.

**Authentication:** Not applicable (local app, no user accounts).

**Accessibility:** Enforced throughout:
- Semantic wx widgets (StaticText, TextCtrl, ListCtrl, Button)
- MSAA labels via wxSizer ordering (label immediately before control)
- EVT_CHAR_HOOK for NVDA/JAWS compatibility (not EVT_KEY_DOWN)
- Zone navigation reduces cognitive load with persistent cursor positions
- Diminishing messages prevent repetitive announcements
- Detail inspection allows granular exploration of card attributes

---

*Architecture analysis: 2026-04-14*
