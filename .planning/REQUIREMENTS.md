# Requirements: StoneReader

**Defined:** 2026-04-15
**Core Value:** Screen reader users can access live game tracking information during a Hearthstone match without leaving the game window, via global hotkeys that announce through the screen reader.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Deck Management

- [ ] **DECK-01**: User can import a deck by pasting a deckstring and naming it
- [ ] **DECK-02**: User can browse saved decks in a navigable list
- [ ] **DECK-03**: User can view deck contents with card details via zone navigation
- [ ] **DECK-04**: User can delete a saved deck with confirmation
- [ ] **DECK-05**: User can export a deck's deckstring to clipboard

### Log Infrastructure

- [ ] **LOG-01**: App watches Hearthstone's Power.log file for changes in real time
- [ ] **LOG-02**: App filters PowerTaskList duplicate lines to prevent double-counting
- [ ] **LOG-03**: App detects Power.log file reset on Hearthstone restart and resets parser state
- [ ] **LOG-04**: App auto-creates or verifies log.config so Power.log is enabled
- [ ] **LOG-05**: Log watcher runs in a background thread without blocking the UI

### Live Game Tracking

- [ ] **LIVE-01**: App detects game start and end events from Power.log
- [ ] **LIVE-02**: User can see remaining cards in their deck with counts
- [ ] **LIVE-03**: User can see cards drawn this game
- [ ] **LIVE-04**: User can see opponent's played cards in play order
- [ ] **LIVE-05**: User can query opponent hand count
- [ ] **LIVE-06**: User can query deck count for both players
- [ ] **LIVE-07**: User can query current and max mana for both players
- [ ] **LIVE-08**: App auto-detects which saved deck the user is playing
- [ ] **LIVE-09**: User can query live game state via global hotkeys while Hearthstone has focus

### Replay Viewer

- [ ] **REPLAY-01**: User can load a replay file (HSReplay XML format)
- [ ] **REPLAY-02**: User can navigate forward and back by turn
- [ ] **REPLAY-03**: User can view board state (minions on each side) at any turn
- [ ] **REPLAY-04**: User can view hand contents at any turn
- [ ] **REPLAY-05**: User can drill down into individual actions within a turn
- [ ] **REPLAY-06**: User hears narrative summaries of state changes between turns

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Live Tracking Differentiators

- **DIFF-01**: Opponent hand age tracking — announce which turn each card was drawn or kept from mulligan
- **DIFF-02**: Draw probability announcements — "1 in 14 chance to draw Reno"
- **DIFF-03**: Secret tracker with speech elimination of impossible secrets
- **DIFF-04**: Play history log — navigable action-by-action log of game events
- **DIFF-05**: Full game state browser — multi-zone (board, hand, deck, graveyard) alt-tab browser

### Game History

- **HIST-01**: Automatic win/loss recording per game
- **HIST-02**: Match history browsing with zone navigation
- **HIST-03**: Win rate by class matchup
- **HIST-04**: Win rate by deck

### Quality of Life

- **QOL-01**: Deck comparison — compare two decks side by side before queuing
- **QOL-02**: Diminishing verbosity for repeated global hotkey queries

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Visual overlay on game window | Useless for screen reader users — all information through speech |
| Battlegrounds mode | Entirely different game mode, doubles scope |
| Arena draft helper | Low demand from blind players, complex tier-list maintenance |
| Mulligan win rate stats (HSReplay API) | Requires premium API integration, enormous complexity |
| Cloud sync / online accounts | Local-only app, no infrastructure burden |
| Streaming/OBS integration | Not the target audience |
| Deck builder from scratch | Import-only workflow — deckstrings are the standard |
| Collection tracking | Firestone does this, low strategic value, huge feature surface |
| Meta tier lists / archetype win rates | Requires aggregated data from thousands of players |
| Opponent deck prediction | Requires maintained archetype database, high maintenance |
| macOS / Linux support | Targeting Windows + NVDA/JAWS only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DECK-01 | Phase 1 | Pending |
| DECK-02 | Phase 1 | Pending |
| DECK-03 | Phase 1 | Pending |
| DECK-04 | Phase 1 | Pending |
| DECK-05 | Phase 1 | Pending |
| LOG-01 | Phase 2 | Pending |
| LOG-02 | Phase 2 | Pending |
| LOG-03 | Phase 2 | Pending |
| LOG-04 | Phase 2 | Pending |
| LOG-05 | Phase 2 | Pending |
| LIVE-01 | Phase 3 | Pending |
| LIVE-02 | Phase 3 | Pending |
| LIVE-03 | Phase 3 | Pending |
| LIVE-04 | Phase 3 | Pending |
| LIVE-05 | Phase 3 | Pending |
| LIVE-06 | Phase 3 | Pending |
| LIVE-07 | Phase 3 | Pending |
| LIVE-08 | Phase 3 | Pending |
| LIVE-09 | Phase 3 | Pending |
| REPLAY-01 | Phase 4 | Pending |
| REPLAY-02 | Phase 4 | Pending |
| REPLAY-03 | Phase 4 | Pending |
| REPLAY-04 | Phase 4 | Pending |
| REPLAY-05 | Phase 4 | Pending |
| REPLAY-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-04-15*
*Last updated: 2026-04-14 after roadmap creation*
