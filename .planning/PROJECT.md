# StoneReader

## What This Is

An accessible Hearthstone deck tracker, deck manager, and replay viewer for screen reader users on Windows. It provides the same live game information as Firestone or HsReplay — remaining deck, opponent tracking, mulligan guidance — but through speech output and keyboard navigation instead of visual overlays. Built with wxPython and accessible_output2 for NVDA/JAWS compatibility.

## Core Value

Screen reader users can access live game tracking information (remaining deck, opponent plays, hand tracking) during a Hearthstone match without leaving the game window, via global hotkeys that announce through the screen reader.

## Requirements

### Validated

- ✓ Card browser with search and zone navigation — existing
- ✓ Card detail inspection via down arrow — existing
- ✓ Screen reader speech output with stdout fallback — existing
- ✓ Zone-based keyboard navigation with persistent cursors — existing
- ✓ Text mode for search input — existing
- ✓ Tab-based UI shell — existing
- ✓ SQLite database for decks and games — existing
- ✓ Deck model with deckstring import/export — existing
- ✓ Game state and replay state models — existing
- ✓ Deck management — import deckstrings (with graceful-degrade for unknown DBF IDs), browse saved decks, view deck contents with detail inspection, delete with confirmation, export to clipboard — Validated in Phase 01

### Active

- [ ] Live game tracking via Power.log file parsing
- [ ] Remaining deck display with card counts and copy tracking
- [ ] Opponent played cards tracking
- [ ] Opponent hand tracking (cards held since which turn)
- [ ] Mulligan guidance (stats-based suggestions)
- [ ] Global hotkeys that announce info while Hearthstone has focus
- [ ] Background window with full zone navigation for live game state
- [ ] Replay viewer — turn-by-turn navigation with board/hand/log zones
- [ ] Replay viewer — action-by-action drill-down within turns
- [ ] Game history storage (basic win/loss, matchups)

### Out of Scope

- Visual overlay on game window — useless for screen reader users, adds complexity
- Deck builder from scratch — import-only workflow covers the need
- macOS/Linux support — targeting Windows + NVDA/JAWS only
- Deep analytics/stats dashboard — basic history is enough, not building HsReplay's analytics
- Memory reading for game state — Power.log parsing is proven and stable across patches
- Cloud sync or online accounts — local-only application
- Streaming/OBS integration — not the target audience

## Context

**Existing codebase:** StoneReader already has a working card browser tab with search, zone navigation, detail inspection, and screen reader output. The MVP architecture (Model-View-Presenter), InputLayer (EVT_CHAR_HOOK routing), and SpeechService are established patterns. Models for Deck, GameState, and ReplayState exist but have no presenter or view yet.

**Hearthstone log file:** Hearthstone writes game events to `Power.log` in its install directory. This is the same data source HDT and Firestone use. The `hearthstone` Python library provides card enums and deckstring parsing. Log parsing is a well-understood problem with existing open-source implementations as reference.

**Screen reader landscape:** NVDA and JAWS are the primary screen readers on Windows. accessible_output2 abstracts the differences. Global hotkeys require Windows-specific APIs (pywin32 or ctypes) to register system-wide keyboard shortcuts that work even when StoneReader doesn't have focus.

**Known tech debt:** Text mode state can leak between windows, zone cursor can desync during rapid navigation, SpeechService has overly broad exception handling. These should be addressed as part of building new features.

## Constraints

- **Tech stack**: wxPython + accessible_output2 + hearthstone library — already established, no framework changes
- **Platform**: Windows only — global hotkeys and screen reader APIs are Windows-specific
- **Input method**: EVT_CHAR_HOOK for in-app hotkeys (NVDA/JAWS compatibility), Windows API for global hotkeys
- **Architecture**: MVP pattern — presenters own state and speech, views are passive widgets
- **Immutability**: Frozen dataclasses for all game state — construct new instances, never mutate
- **Speech rule**: Views never call SpeechService directly — only presenters call `self._speech`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Power.log parsing for game data | Proven approach (HDT, Firestone use it), stable across patches, no injection risk | — Pending |
| Background window + global hotkeys | Overlays are useless for screen readers; global hotkeys bridge the gap | — Pending |
| Windows-only platform target | NVDA/JAWS are Windows; simplifies global hotkey implementation | — Pending |
| Import-only deck management | Building decks from scratch is complex and low-value when deckstrings exist | ✓ Validated in Phase 01 — deckstring import (with graceful-degrade for unknown DBF IDs) is the sole path |
| Basic game history, not deep analytics | Stats are nice-to-have, not the core value; avoids scope creep | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-25 after Phase 01 (Deck Management) completion*
