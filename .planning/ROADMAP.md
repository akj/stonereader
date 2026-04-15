# Roadmap: StoneReader

## Overview

StoneReader already has a working card browser with zone navigation, detail inspection, and screen reader output. The roadmap builds the four remaining capabilities: deck management (leveraging existing models and database), log infrastructure (the headless engine that reads Hearthstone's Power.log), live game tracking (the core value -- speech-announced game state via global hotkeys), and replay viewing (turn-by-turn replay navigation reusing log parsing). Each phase delivers a complete, verifiable feature slice.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Deck Management** - Import, browse, inspect, export, and delete saved decks
- [ ] **Phase 2: Log Infrastructure** - Watch, parse, and filter Hearthstone's Power.log in a background thread
- [ ] **Phase 3: Live Game Tracking** - Track and announce live game state via global hotkeys while Hearthstone has focus
- [ ] **Phase 4: Replay Viewer** - Load and navigate HSReplay XML files turn-by-turn with action drill-down

## Phase Details

### Phase 1: Deck Management
**Goal**: Users can manage a library of Hearthstone decks entirely through keyboard and screen reader
**Depends on**: Nothing (Deck model, SQLite db, and deckstring parsing already exist)
**Requirements**: DECK-01, DECK-02, DECK-03, DECK-04, DECK-05
**Success Criteria** (what must be TRUE):
  1. User can paste a deckstring, name the deck, and find it persisted after restarting the app
  2. User can arrow through a list of saved decks and hear each deck's name and class
  3. User can select a deck and navigate its card list with detail inspection (down arrow reads card details)
  4. User can delete a deck and is prompted for confirmation before removal
  5. User can copy a deck's deckstring to clipboard for sharing
**Plans**: TBD
**UI hint**: yes

### Phase 2: Log Infrastructure
**Goal**: The app can reliably tail Hearthstone's Power.log and produce a clean stream of game events without blocking the UI
**Depends on**: Nothing (headless service, no UI dependency)
**Requirements**: LOG-01, LOG-02, LOG-03, LOG-04, LOG-05
**Success Criteria** (what must be TRUE):
  1. LogWatcher detects new lines appended to Power.log within 1 second and emits parsed events
  2. Duplicate lines from PowerTaskList blocks are filtered so each game action appears exactly once
  3. When Hearthstone restarts and Power.log is truncated/reset, the watcher detects the reset and re-reads from the beginning without crashing or double-emitting old events
  4. On first run, the app creates or verifies log.config in the Hearthstone directory so Power.log output is enabled
  5. The log watcher thread can be started and stopped cleanly without UI freezes or orphaned threads
**Plans**: TBD

### Phase 3: Live Game Tracking
**Goal**: Users can query live game state through speech announcements via global hotkeys while Hearthstone has focus
**Depends on**: Phase 1 (deck auto-detection needs saved decks), Phase 2 (game events come from LogWatcher)
**Requirements**: LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, LIVE-06, LIVE-07, LIVE-08, LIVE-09
**Success Criteria** (what must be TRUE):
  1. When a Hearthstone game starts, the app detects the game start event and begins tracking; when it ends, tracking stops and state resets
  2. User can press a global hotkey while Hearthstone has focus and hear their remaining deck contents with card counts spoken through the screen reader
  3. User can press a global hotkey to hear opponent's played cards in play order
  4. User can press global hotkeys to hear deck counts, hand counts, and mana totals for both players
  5. The app auto-detects which saved deck the user is playing by matching the initial deck list against saved decks
**Plans**: TBD
**UI hint**: yes

### Phase 4: Replay Viewer
**Goal**: Users can load an HSReplay XML file and navigate the game turn-by-turn with full board and hand inspection
**Depends on**: Phase 2 (reuses log parsing infrastructure for replay event interpretation)
**Requirements**: REPLAY-01, REPLAY-02, REPLAY-03, REPLAY-04, REPLAY-05, REPLAY-06
**Success Criteria** (what must be TRUE):
  1. User can open an HSReplay XML file and hear the matchup summary (player classes and names)
  2. User can navigate forward and backward by turn and hear which turn they are on
  3. User can inspect the board state at any turn and hear minions on each side via zone navigation
  4. User can inspect hand contents at any turn via zone navigation
  5. User can drill down into individual actions within a turn and hear what happened (e.g., "Reno Jackson played", "Fireball hits face for 6")
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Deck Management | 0/0 | Not started | - |
| 2. Log Infrastructure | 0/0 | Not started | - |
| 3. Live Game Tracking | 0/0 | Not started | - |
| 4. Replay Viewer | 0/0 | Not started | - |
