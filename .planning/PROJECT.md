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
- ✓ Log infrastructure — Hearthstone Power.log watcher (150ms wx.Timer tail with rotation/process-gone detection), hslog parser wrapper (D-10 isolation), GameEngine with frozen GameState reducer + 11 typed events, GameTracker facade with subscriber bus, log.config bootstrap (D-11), stdlib logging (D-16) — Validated in Phase 02
- ✓ Live game tracking — WR-02 friendly-player resolution (AI fast-path + SHOW_ENTITY fallback, no hslog leak), D-19 opponent-hand creation lineage with INNERMOST POWER subject + sticky guard + reset-on-CREATE_GAME, opponent_hand reconstruction in `_refresh_state`, GlobalHotkeyService (MOD_NOREPEAT default, failure accumulation, callback isolation, idempotent clear_all), LiveGamePresenter (4 zones — remaining_deck/opponent_hand/opponent_played/cards_drawn, auto-deck-detection on CREATE_GAME, public hotkey-callable accessors, wx-free, D-07 silent-during-event), LiveGamePanel (passive view, no SpeechService import, AcceptsFocus(False) ListCtrls + sibling-order MSAA labels), `Ctrl+Shift+R/O/D/H` chord wiring, `_on_close` continue-on-failure cleanup ordering — Validated in Phase 03 (manual NVDA/JAWS smoke test deferred to 03-HUMAN-UAT.md)

### Active

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
| Power.log parsing for game data | Proven approach (HDT, Firestone use it), stable across patches, no injection risk | ✓ Validated in Phase 02 — hslog wrapper isolated behind D-10; reducer-style GameEngine over frozen GameState |
| Background window + global hotkeys | Overlays are useless for screen readers; global hotkeys bridge the gap | ✓ Validated in Phase 03 — `Ctrl+Shift+R/O` browse-open, `Ctrl+Shift+D/H` speak-only via `wx.Frame.RegisterHotKey` + MOD_NOREPEAT |
| Windows-only platform target | NVDA/JAWS are Windows; simplifies global hotkey implementation | ✓ Validated in Phase 03 — RegisterHotKey is Win32; engine deliberately portable for Phase 4 replay reuse |
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
*Last updated: 2026-04-27 after Phase 03 (Live Game Tracking) completion — manual NVDA/JAWS smoke test pending in 03-HUMAN-UAT.md*
