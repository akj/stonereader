# Feature Landscape

**Domain:** Accessible Hearthstone deck tracker, deck manager, and replay viewer for screen reader users
**Researched:** 2026-04-14

## Table Stakes

Features users expect from any Hearthstone companion tool. Missing = product feels incomplete for competitive play.

### Live Game Tracking (Constructed)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Remaining deck list with card counts | Core deck tracker purpose. Every tracker (HDT, Firestone) shows this. Without it there's no reason to use the tool. | Medium | Parse Power.log zone changes (DECK zone). Deck model exists; need live-updating remaining-cards view. Speech: navigate list with up/down, announce "Card Name, 1 remaining" or "Card Name, 2 remaining". |
| Cards drawn this game | Knowing what you've already drawn is essential for probability thinking. | Low | Track zone changes from DECK to HAND. Display as separate zone or toggle. |
| Opponent played cards | Every tracker shows this. Critical for predicting opponent's remaining threats and answers. | Medium | Track opponent zone changes to PLAY/GRAVEYARD. Speech: list of cards with mana cost, in play order. |
| Opponent hand count | Knowing how many cards opponent holds informs aggression decisions. | Low | Count entities in opponent HAND zone. Announce on demand via hotkey. |
| Deck count (both players) | Fatigue awareness, knowing how deep into the deck each player is. | Low | Simple counter from Power.log. Already modeled in GameState.player_deck_count / opponent_deck_count. |
| Mana tracking (both players) | Knowing current/max mana for both players. Essential for predicting what opponent can play. | Low | Already modeled in GameState. Announce on demand. |
| Automatic deck detection | HDT and Firestone auto-detect which deck you're playing at game start. Manual selection is friction. | Medium | Match cards drawn against saved decks in SQLite. Use hero class + early draws to identify. |
| Game start/end detection | Must know when a game begins and ends to activate/deactivate tracking. | Medium | Power.log game start/end events are well-documented. Triggers state transitions. |
| Global hotkeys for in-game queries | THE critical accessibility adaptation. Sighted users glance at an overlay; blind users need hotkeys that speak information while Hearthstone has focus. | High | Requires Windows global hotkey registration (pywin32/ctypes). Hotkeys trigger SpeechService announcements without leaving game. This is the primary UX differentiator. |

### Deck Management

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Import deck from deckstring | Every tracker supports this. Deckstrings are the universal deck exchange format. | Low | Deck.from_deckstring() already exists. Need UI: paste deckstring, name deck, save to SQLite. |
| Browse saved decks | Users need to see their collection of decks and select one for tracking. | Low | List decks from SQLite, navigate with zone navigation pattern, show deck contents. |
| View deck contents with card details | Must be able to inspect every card in a deck before and during play. | Low | Reuse card detail inspection (down arrow) from card browser. Zone navigation over deck cards. |
| Delete saved decks | Basic CRUD. Users accumulate outdated decks. | Low | Confirm dialog, delete from SQLite. |
| Export deckstring to clipboard | Round-trip: import and export. Sharing decks with others. | Low | CardBrowserPanel already has clipboard logic. Apply same pattern. |

### Game History

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Win/loss recording per game | HDT and Firestone both track this automatically. Users expect it. | Low | Games table exists in SQLite schema. Record result, opponent class, turns, timestamp. |
| Match history browsing | Must be able to look back at recent games. | Low | Zone navigation over game list. Announce: "vs Mage, Won, 12 turns, 5 minutes ago". |
| Win rate by class matchup | Basic stat that every tracker shows. Answers "how do I do against Warrior?" | Low | SQL aggregation over games table, grouped by opponent_class. |
| Win rate by deck | Answers "is this deck working for me?" Core tracker value. | Low | SQL aggregation grouped by deck_name. |

## Differentiators

Features that set StoneReader apart. Not expected from a generic deck tracker, but uniquely valuable for screen reader users.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Keyboard-first live game state browser | When not in a critical turn, alt-tab to StoneReader and browse full game state with zone navigation (board, hand, deck, opponent played, graveyard). No sighted tracker offers this depth of non-visual inspection. | High | Full presenter with multiple zones, each populated from live GameState. Reuses ZoneNavigationMixin pattern. Zones: remaining deck, opponent played, player hand, player board, opponent board, graveyard. |
| Opponent hand age tracking with speech | HDT shows turn numbers visually next to cards. For screen reader users, announcing "Card held since turn 3, kept from mulligan" is extremely valuable strategic information that has no visual equivalent in HearthstoneAccess. | Medium | Track per-entity metadata: turn drawn, mulligan-kept flag, created-by source. Announce as part of opponent hand zone navigation. |
| Contextual draw probability announcements | Instead of visual percentage overlays, announce on demand: "14 cards remaining. 1 in 14 chance to draw Reno next turn." Natural speech phrasing rather than visual percentage. | Medium | Calculate probability from remaining deck composition. Announce via global hotkey or during deck zone navigation. Express as "1 in N" fractions (more natural for speech than percentages). |
| Secret tracker with speech elimination | When opponent plays a secret, announce possible secrets for their class. As game actions eliminate possibilities, announce remaining candidates. Sighted trackers show this visually; speech-based elimination is uniquely useful. | High | Maintain secret candidate list per class. Hook into game events that trigger/fail secrets. Announce on demand: "Possible secrets: Counterspell, Ice Block. 2 remaining." |
| Replay viewer with turn-by-turn narration | Navigate replays by turn, hearing board state changes as narrated summaries rather than visual animations. "Turn 5: Opponent played Fireball on your Azure Drake. Your Azure Drake died. Opponent has 3 cards in hand." | High | ReplayState model exists. Need ReplayViewerPresenter with zones: turn list, actions within turn, board snapshot, hand snapshot. Narrative generation from GameState diffs. |
| Diminishing verbosity for repeated queries | StoneReader's existing diminishing message pattern applied to live tracking: first query gets full context, repeated queries get terse updates. Reduces cognitive load during rapid play. | Low | Already implemented in base presenter. Apply same pattern to tracker hotkey responses. |
| Play history log (action-by-action) | Scrollable log of every action this game: "Turn 3: You played Frostbolt on opponent hero for 3 damage." HearthstoneAccess has 'y' for play history; StoneReader can offer a persistent, navigable version. | Medium | Build from Power.log events. Zone with action entries. Navigate with up/down. Critical for blind users who may miss announcements. |
| Deck comparison (pre-game) | Before queuing, compare two decks side by side. Announce shared cards, unique cards, mana curve differences. Useful for deciding which deck to play. | Medium | Pure data operation on two Deck objects. New presenter with comparison zones. |

## Anti-Features

Features to explicitly NOT build. These would add complexity without serving the target audience.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Visual overlay on game window | Useless for screen reader users. Core architectural mistake would be adding visual rendering. Every pixel of UI effort is wasted on this audience. | Global hotkeys + alt-tab browser window. All information through speech. |
| Battlegrounds mode tracking | Entirely different game mode with different information needs (tavern tier, minion tribes, warband composition). Doubles scope for a niche audience. HearthstoneAccess already provides BG-specific commands. | Focus on Constructed mode only. Battlegrounds can be a separate future project if demand exists. |
| Arena draft helper / tier list overlay | Arena drafting requires card-by-card tier scoring and synergy analysis. Large feature surface that few blind players would use vs. importing a pre-built deck. | Not needed. Arena players can use HearthstoneAccess commands during draft. |
| Mulligan win rate statistics (HSReplay-style) | Requires API integration with HSReplay.net (paid premium), maintaining card-level win rate databases, or scraping. Enormous complexity for marginal benefit. | Simpler alternative: announce which cards you were offered in mulligan. Let user decide based on game knowledge. Could add basic personal mulligan stats later. |
| Cloud sync or online accounts | Local-only app for a niche audience. Server infrastructure adds cost and maintenance for zero user benefit. | SQLite local storage. Users can backup database file manually. |
| Streaming/OBS integration | Target audience is blind screen reader users, not content creators. | Not applicable. |
| Deep analytics dashboard | HSReplay already does this with a web interface. Replicating their analytics in a desktop app is scope creep. | Basic win/loss stats per deck and per matchup. Link to HSReplay.net for deep analysis. |
| Deck builder from scratch | Building decks card-by-card is complex UI. Deckstrings exist and are the standard exchange format. Every deck guide publishes a deckstring. | Import-only workflow. Paste deckstring, name it, save it. |
| Collection tracking / pack opening tracker | Firestone does this well. Low strategic value. Enormous feature surface (track every card owned, dust calculations, missing cards). | Out of scope entirely. |
| Meta tier list / archetype winrates | Requires aggregated game data from thousands of players or API access to HSReplay/VS. Cannot generate locally. | Out of scope. Users can check tier lists on the web. |
| Opponent deck prediction (archetype guessing) | HDT plugin predicts full opponent decklist from early plays using meta data. Requires maintained archetype database. High maintenance burden. | Instead, simply track what opponent has played. Let user's game knowledge fill in predictions. |

## Feature Dependencies

```
Core Infrastructure (must come first):
  Power.log parser ──────────────────────────┐
  Global hotkey system ──────────────────────┐│
                                             ││
Deck Management (can be independent):        ││
  Import deckstring → Save to DB             ││
  Browse saved decks → View deck contents    ││
  Delete deck                                ││
  Export deckstring                           ││
                                             ││
Live Game Tracking (depends on log parser):  ││
  Game start/end detection ←─────────────────┘│
  Automatic deck detection ←── saved decks    │
  Remaining deck list ←───────────────────────┘
  Cards drawn list ←── remaining deck
  Opponent played cards ←── log parser
  Opponent hand count ←── log parser
  Opponent hand age ←── opponent hand count
  Draw probability ←── remaining deck list
  Secret tracker ←── opponent played cards
  Play history log ←── log parser

Background Window (depends on live tracking):
  Full game state browser ←── all tracking zones
  Global hotkey announcements ←── game state + speech

Game History (depends on game detection):
  Win/loss recording ←── game end detection
  Match history browsing ←── win/loss recording
  Win rate stats ←── match history

Replay Viewer (depends on log parser):
  Parse replay file ←── log parser (same format)
  Turn-by-turn navigation ←── ReplayState model
  Action drill-down ←── turn navigation
  Board/hand snapshots ←── GameState model
```

## MVP Recommendation

### Phase 1: Deck Management
Lowest risk, no external dependencies (no log parsing needed), exercises the existing architecture patterns.

Prioritize:
1. Import deckstring (model exists, add presenter/view)
2. Browse saved decks with zone navigation
3. View deck contents with card detail inspection
4. Delete deck, export deckstring

### Phase 2: Power.log Parser + Basic Live Tracking
The technical foundation everything else depends on.

Prioritize:
1. Power.log file watcher and event parser
2. Game start/end detection
3. Remaining deck list (with automatic deck detection)
4. Opponent played cards list
5. Basic global hotkeys (remaining deck count, opponent hand count)

### Phase 3: Full Live Game State Browser
The primary differentiator for screen reader users.

Prioritize:
1. Background window with zone-navigable game state
2. Full global hotkey set for in-game queries
3. Opponent hand age tracking
4. Draw probability announcements
5. Secret tracker
6. Play history log

### Phase 4: Game History + Replay Viewer
Post-game analysis tools. Lower priority than live tracking.

Prioritize:
1. Automatic win/loss recording
2. Match history with stats
3. Replay file parsing
4. Turn-by-turn replay navigation
5. Action drill-down within turns

Defer:
- Deck comparison: nice-to-have, not essential for competitive play
- Meta stats: out of scope, use web resources
- Battlegrounds: entirely different mode, separate project

## Sources

- [Hearthstone Deck Tracker (HDT) GitHub](https://github.com/HearthSim/Hearthstone-Deck-Tracker) - Feature list, architecture reference
- [HDT Issue #4371: Screen reader accessibility](https://github.com/HearthSim/Hearthstone-Deck-Tracker/issues/4371) - Blind user requesting accessible deck tracker
- [Firestone on Overwolf](https://www.overwolf.com/app/sebastien_tromp-firestone) - Feature comparison
- [Firestone 2025](https://game.overwolf.com/firestone-2025-inf/) - Current feature set
- [HearthstoneAccess Community Version](https://www.hearthstoneaccess.com/) - Existing accessibility mod
- [HearthstoneAccess Keyboard Commands](https://www.hearthstoneaccess.com/commands.html) - Full command reference for blind gameplay
- [HSReplay.net](https://hsreplay.net/) - Mulligan guides, replay viewer, statistics platform
- [HSReplay Card Mulligan Data article](https://articles.hsreplay.net/2020/07/23/card-mulligan-data/) - Premium mulligan feature details
- [AFB Review of Hearthstone Access](https://afb.org/aw/22/10/17720) - Blind user experience assessment
- [HearthSim Fast Log Parsing](https://hearthsim.info/blog/fast-hearthstone-log-parsing/) - Power.log parsing technical reference
- [hearthstone-log-watcher (npm)](https://www.npmjs.com/package/hearthstone-log-watcher) - Reference implementation for log event types
