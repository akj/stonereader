# StoneReader Design Spec

Accessible Hearthstone deck tracking application built with wxPython. Windows-first, targeting NVDA and JAWS screen readers. Built for daily use by screen reader users, designed for distribution to the blind/low-vision Hearthstone community.

## Architecture

### Pattern: MVP (Model-View-Presenter)

- **Models**: frozen dataclasses holding game data. Immutable snapshots.
- **Presenters**: own navigation state, key maps, speech output. Coordinate between models and views.
- **Views**: passive wxPython widgets. Never call SpeechService directly. Never own navigation state.

### Project Structure

```
stonereader/
├── __main__.py              # App entry point
├── app.py                   # wx.App, MainWindow, wx.Notebook shell
├── speech_service.py        # Screen reader abstraction (accessible_output2)
├── input_layer.py           # EVT_CHAR_HOOK key routing, text mode
├── db.py                    # SQLite connection, schema, migrations
│
├── models/
│   ├── card.py              # Card, CardDatabase
│   ├── deck.py              # Deck
│   ├── game_state.py        # GameEntity, GameState, Hero
│   ├── replay.py            # ReplayState
│   └── stats.py             # GameRecord, MatchHistory, StatsSummary
│
├── presenters/
│   ├── base.py              # ZoneNavigationMixin, BasePresenter
│   ├── card_browser.py      # CardBrowserPresenter
│   ├── deck_manager.py      # DeckManagerPresenter
│   ├── game_view.py         # GameViewMixin (shared zones for live + replay)
│   ├── live_tracker.py      # LiveTrackerPresenter
│   ├── replay_viewer.py     # ReplayViewerPresenter
│   └── stats.py             # StatsPresenter
│
├── views/
│   ├── base.py              # Shared widgets, panel helpers
│   ├── card_browser.py      # CardBrowserPanel
│   ├── deck_manager.py      # DeckViewPanel
│   ├── live_tracker.py      # LiveTrackerPanel
│   ├── replay_viewer.py     # ReplayViewerPanel
│   └── stats.py             # StatsPanel
│
├── log_parser/
│   ├── watcher.py           # File watcher for Power.log
│   ├── parser.py            # Line-by-line Power.log parser
│   └── engine.py            # Running GameState from parsed events
│
└── tests/
    ├── test_models/
    ├── test_presenters/
    ├── test_log_parser/
    └── test_db.py
```

### Migration from Current State

The current `models.py` (364 lines) is split into the `models/` package. A `models/__init__.py` re-exports all public classes so existing imports (`from stonereader.models import Card, Deck`) continue to work. The current `presenters.py` and `views.py` stubs are replaced by their respective packages.

### Data Flow

```
Power.log → watcher.py → parser.py → engine.py → GameState snapshots
                                                       │
                                          ┌────────────┼────────────┐
                                          ▼            ▼            ▼
                                   LiveTrackerP   db.py (save)   SpeechService
                                                       │
                                                       ▼
                                                  StatsPresenter
                                                  ReplayViewerP
```

## Foundation Layer

### Speech Service (`speech_service.py`)

Wraps `accessible_output2` for screen reader output.

- `speak(text, interrupt=True)` — send to active screen reader, interrupting current speech
- `speak_queued(text)` — append without interrupting
- Stdout fallback when no screen reader detected (development/CI)
- Based on the fix-speech branch implementation, which is clean and correct

### Input Layer (`input_layer.py`)

Binds `EVT_CHAR_HOOK` on MainWindow. This event fires within wxWidgets' own event processing before native control handlers run — critical because NVDA/JAWS install `WH_KEYBOARD_LL` hooks that intercept `WM_KEYDOWN` before it reaches the app, causing `EVT_KEY_DOWN` and `EVT_CHAR` to silently fail.

Key routing rules, in priority order:

1. **Text mode** (TextCtrl focused) → `event.Skip()`, pass through all keys
2. **Ctrl or Alt held** → `event.Skip()`, never intercept system shortcuts
3. **Key in active map** → call the callback, consume the key
4. **Everything else** → `event.Skip()`

Additional rules:
- Never bind Insert or CapsLock (screen reader modifier keys)
- Tab key always passes through (not in key map)
- One active key map at a time, swapped on Notebook tab change
- Text mode entered on `EVT_SET_FOCUS` for TextCtrl, exited on `EVT_KILL_FOCUS`
- `EVT_ACTIVATE` guard to unstick text mode on alt-tab (Windows `EVT_KILL_FOCUS` is unreliable on alt-tab)
- Escape added to `_KEY_NAMES` for dialog close and mode exit

### App Shell (`app.py` + `__main__.py`)

- `wx.App` subclass, MainWindow extends `wx.Frame`
- `wx.Notebook` with tabs: Card Library, Deck Viewer, Live Tracker, Replay Viewer, Statistics
- `wx.AcceleratorTable` on MainWindow for standard shortcuts (Ctrl+Q quit, Ctrl+O open replay, etc.)
- `self.CreateStatusBar()` — persistent state display ("Turn 5 of 12", "47 results"). NVDA reads with NVDA+End, JAWS with Insert+B.
- Tab change (`EVT_NOTEBOOK_PAGE_CHANGED`) swaps active key map and moves focus to primary widget on the new tab via `wx.CallAfter(target.SetFocus)`

### Database (`db.py`)

- SQLite via Python's built-in `sqlite3`
- Schema created on first run, versioned with a simple integer migration table
- Initial tables: `games` (game records), `decks` (saved decks), `schema_version`
- Single connection, no concurrency concerns in a desktop app

### Base Presenter (`presenters/base.py`)

- `BasePresenter` — holds reference to SpeechService, provides `announce()` helper
- `ZoneNavigationMixin` — zone cursors, navigate-then-inspect pattern, diminishing orienting messages

### Base View Helpers (`views/base.py`)

- Text mode lifecycle helpers (bind `EVT_SET_FOCUS`/`EVT_KILL_FOCUS` to enter/exit text mode)
- Panel factory with `wx.WANTS_CHARS` style for speech-driven panels

## Interaction Model

### Unified Card Navigation

All card-bearing features use the same speech-driven interaction model:

- **Left/Right**: move between cards, speech announces card name and position ("Fireball, 3 of 47")
- **Up/Down**: cycle through detail lines on the current card (cost, attack/health, type, class, text, set, rarity). Only lines meaningful to the card type are shown (no attack/health for spells, no durability for non-weapons).
- **Letter keys**: zone jumps and feature-specific actions
- **Context menu** (Applications key or Shift+F10): card-specific actions (copy name, etc.)

Detail line order: name → cost → attack/health (if applicable) → type → class → text → set → rarity → durability (if applicable).

### Widget Strategy: Speech-Driven with Visual Companion

Focus lives on the parent panel (`wx.WANTS_CHARS`), not on list widgets. A `wx.ListCtrl` (virtual report mode) exists as a visual companion — updated programmatically when the presenter moves the cursor, but never focused. Since it's unfocused, NVDA won't double-announce selection changes.

```
User presses Right →
  EVT_CHAR_HOOK →
    presenter.navigate_right() →
      cursor advances →
      speech: "Fireball, 3 of 47" →
      view callback: list_ctrl.Select(3)  # visual sync, no NVDA speech
```

`wx.Accessible` subclass on speech-driven panels exposes current zone and item to NVDA's object navigator.

### Focus Management

| Event | Focus Target |
|-------|-------------|
| Tab switch (Ctrl+Tab) | Primary widget on new tab via `wx.CallAfter` |
| Dialog close | Return to the control that opened the dialog |
| Search results appear | Back to the panel for browsing |
| Zone jump | Stay on panel, speech announces zone |

### Labeling

Every TextCtrl and ListCtrl must have a `wx.StaticText` immediately before it in the sizer. This is how NVDA/JAWS discover labels on Windows — MSAA sibling order determines the association.

```python
label = wx.StaticText(panel, label="Search cards:")
ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
sizer.Add(label, 0, wx.ALL, 4)
sizer.Add(ctrl, 0, wx.EXPAND | wx.ALL, 4)
```

`wx.Window.SetName()` does NOT work for screen reader labels — it only affects `FindWindowByName()`.

## Features

### Card Library

Browse and search the Hearthstone card database.

- **Panel**: search TextCtrl (labeled "Search cards:") + visual-only ListCtrl
- **Search**: typing triggers `CardDatabase.search_cards()`. Speech announces result count. Focus returns to panel for browsing.
- **Navigation**: single "results" zone. Left/Right through results, Up/Down through detail lines.
- **Context menu**: copy card name.
- **Data source**: `hearthstone-data` card database via `CardDatabase.load()`

### Deck Viewer

Import, browse, and manage decks.

- **Panel**: TextCtrl for deckstring input (labeled "Deck code:") + visual-only ListCtrl
- **Import**: paste deckstring, press Enter. `Deck.from_deckstring()` parses it. Speech announces deck name, class, card count.
- **Navigation**: Left/Right through cards (sorted by cost), Up/Down for detail lines. Additional deck-specific detail line: "2 copies" or "1 copy".
- **Zones**: "cards" (C) for the deck list, "stats" (S) for summary (total cards, average cost, dust cost)
- **Persistence**: saved decks in SQLite. A "saved decks" zone to browse between decks.
- **Context menu**: export deckstring to clipboard, delete saved deck.

### Log Parser + Live Tracker

Real-time game state tracking via Power.log parsing.

**Log Parser (`log_parser/`):**

- `watcher.py`: monitors Power.log using file polling via `wx.Timer` (stays on GUI thread, no threading needed). Checks file size/mtime on interval.
- `parser.py`: processes new lines from Power.log. Uses `hearthstone.hslog` if viable, or custom line parser for `POWER_TASK_LIST` block format. Outputs game events (card played, card drawn, turn change, etc.).
- `engine.py`: consumes events, maintains running GameState. Emits new GameState snapshots on each meaningful change.

Research phase (agent team): before implementation, 3 teammates investigate `hslog` capabilities, Power.log format/edge cases, and how HDT/Firestone approach parsing. Findings inform whether to use `hslog` or build a custom parser.

**Live Tracker (presenter + view):**

- **Zones**: player board (B), opponent board (G), player hand (H), player hero (V), opponent hero (F), player deck (D), opponent deck (O), graveyard (X), secrets (E)
- **Navigation**: letter keys jump zones, Left/Right within a zone, Up/Down for entity detail lines
- **Real-time updates**: when the engine emits a new GameState, the presenter diffs it and announces meaningful changes — "Opponent played Fireball", "Your turn, turn 5"
- **Config**: path to Power.log auto-detected from standard Hearthstone install location, overridable
- **Game persistence**: after each game ends, save a GameRecord to SQLite for statistics

### Replay Viewer

Turn-by-turn review of completed games.

- **Input**: load `.hsreplay` files (XML format) or reconstruct from saved game data
- **Same zones and navigation as Live Tracker** — shares `GameViewMixin` base providing zone layout and navigation for GameState
- **Turn stepping**: T/Shift+T for next/previous turn. Speech announces "Turn 5, your turn" or "Turn 6, opponent's turn"
- **Jump**: J to type a turn number, jump directly
- **Data**: replay is a sequence of GameState snapshots navigated manually instead of streamed live

### Statistics

Per-game and aggregate stats over time.

- **Data source**: SQLite `games` table, populated by the live tracker
- **Per-game stats**: cards drawn, mana curve played, cards remaining, turns played
- **Aggregate stats**: win/loss by deck, matchup winrates by opponent class, performance trends
- **Navigation**: zones for different stat categories. Left/Right through stat entries, Up/Down for details.
- **Timeframe filtering**: all time, last 7 days, last 30 days, current season

## Implementation Plan

### Slice Order

Build vertical slices sequentially using subagent-driven development (SDD). Each slice is model → presenter → view → tests, end-to-end.

1. **Foundation** — speech service, input layer, app shell, DB schema, base presenter/view patterns
2. **Card Library** — first real feature, validates the architecture
3. **Deck Viewer** — builds on card models, adds persistence
4. **Log Parser + Live Tracker** — hardest piece, benefits from stable architecture. Preceded by agent team research phase.
5. **Replay Viewer** — reuses GameState models and GameViewMixin from the tracker
6. **Statistics** — reads from game history DB populated by the tracker

### Agent Delegation

**Subagent-driven development (SDD)** for all implementation slices:
- Fresh subagent per task
- Two-stage review: spec compliance, then code quality
- Sequential execution preserves consistency

**Agent team** for one specific use case:
- Research phase before the Log Parser slice
- 3 teammates: `hslog` library capabilities, Power.log format/edge cases, HDT/Firestone approach analysis
- Findings synthesized before implementation begins

### Dependency Graph

```
Foundation
    │
    ├── Card Library
    │
    ├── Deck Viewer
    │
    └── Log Parser Research (agent team)
            │
            └── Log Parser + Live Tracker
                    │
                    ├── Replay Viewer
                    │
                    └── Statistics
```

Card Library and Deck Viewer are independent of each other but both depend on Foundation. Log Parser research can run after Foundation. Replay Viewer and Statistics both depend on Live Tracker but are independent of each other.

## Accessibility Requirements

### Screen Reader Support

- Primary: NVDA (Windows, free)
- Secondary: JAWS (Windows, commercial)
- Development fallback: stdout when no screen reader detected

### Non-Negotiable Rules

- Every TextCtrl and ListCtrl has a preceding `wx.StaticText` label in the sizer
- `wx.Window.SetName()` is never used for accessible labeling
- All navigation reachable and operable by keyboard
- `EVT_CHAR_HOOK` for all key handling (never `EVT_KEY_DOWN`/`EVT_CHAR` on list/tree controls)
- Ctrl/Alt combos always pass through to the system
- Views never call SpeechService directly
- Focus explicitly managed on tab switch, dialog close, and content updates
- System colors via `wx.SystemSettings.GetColour()`, never hardcoded
- Status bar for persistent state readable via NVDA+End / JAWS Insert+B

### Testing Strategy

**Automated (no screen reader):**
- Presenter unit tests: mock SpeechService, verify speech output and cursor state
- InputLayer tests: wx.App + wx.Frame, simulate key events, verify routing
- Widget labeling tests: walk widget tree, verify StaticText precedes every input control

**Manual (screen reader required):**
- NVDA + Speech Viewer for all interaction flows
- JAWS as secondary verification
- Accessibility Insights for Windows for UIA tree inspection
- Test matrix:

| Scenario | NVDA | JAWS |
|----------|------|------|
| Control labels announced on focus | | |
| Search result count announced | | |
| Left/Right navigation reads card name | | |
| Up/Down reads detail lines | | |
| Tab switch announces tab + focuses content | | |
| Zone jump announces zone name + item | | |
| Text mode: typing in search/input works | | |
| Ctrl+C does not trigger zone key | | |
| Escape closes dialog, returns focus | | |
| Status bar readable | | |
| Context menu opens and reads items | | |
