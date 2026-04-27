---
status: complete
phase: 03-live-game-tracking
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05-SUMMARY.md, 03-06-SUMMARY.md]
started: 2026-04-27T15:04:36Z
updated: 2026-04-27T15:09:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running StoneReader. Launch the app fresh. Main window appears, home menu lists 4 entries, no traceback or ERROR-level console output, and global hotkeys either register silently or speech announces "Could not register hotkeys: ...".
result: pass

### 2. Home Menu Has "Live Game" as 4th Entry
expected: Home menu reads (top-to-bottom): "Card Library", "Deck Manager", "Import Deck", "Live Game". The fourth entry is selectable via Down-arrow + Enter.
result: pass

### 3. Open Live Game Panel from Home Menu
expected: Selecting "Live Game" from the home menu navigates to the LiveGamePanel and the speech service announces the Remaining Deck zone-entry phrase (D-17) — e.g. "Remaining deck zone, 0 cards" when no game is active.
result: pass

### 4. Live Game Panel Layout (Top-Down Order)
expected: Panel shows in vertical order — Title StaticText → Mana StaticText → "Remaining Deck:" label + list → "Opponent Hand:" label + list → "Opponent Played:" label + list → "Cards Drawn:" label + list. With no game, lists are empty but labels and the title placeholder render.
result: issue
reported: "OCR shows: 'No game in progress' / 'Remaining Deck:' / 'Opponent Hand:' / 'Opponent Played:' / 'Drawn:' — last label is 'Drawn:' not 'Cards Drawn:', no mana line visible, and screen reader only announces 'remaining_deck: empty' on panel entry."
severity: major

### 5. Number Keys 1/2/3/4 Switch Zones
expected: With LiveGamePanel focused, pressing 1 → Remaining Deck, 2 → Opponent Played, 3 → Opponent Hand, 4 → Cards Drawn. Each zone switch fires the D-17 zone-entry speech announcement.
result: pass

### 6. Speak-Only Deck Counts (Ctrl+Shift+D)
expected: With the app running and no Hearthstone game, pressing Ctrl+Shift+D from anywhere triggers a speech announcement — either "0 left, opponent 0" / similar empty-state phrasing, or a graceful "No game in progress." No exception in the console.
result: pass

### 7. Speak-Only Opponent Hand Count (Ctrl+Shift+H)
expected: With no Hearthstone game, pressing Ctrl+Shift+H announces "Opponent has 0 cards." or "No game in progress." No exception in the console.
result: pass

### 8. Live Game Tracking with Real Match (LIVE-01..05)
expected: With Hearthstone open and a Constructed match in progress: panel title shows "<Class> vs <Class>" (and the saved-deck name once 30 cards are revealed); Remaining Deck zone counts decrement as you draw; Opponent Hand zone shows entity rows with creation lineage when generated mid-block; Cards Drawn zone updates per draw. Requires a Hearthstone box — block if not available.
result: issue
reported: "this isn't working vs the innkeeper"
severity: major

### 9. Graceful Close (Alt+F4)
expected: Alt+F4 (or window close) shuts the app down cleanly — no traceback in the console, no orphaned hotkey registrations (relaunch can re-register Ctrl+Shift+R/O/D/H without conflicts).
result: pass

## Summary

total: 9
passed: 7
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Live Game panel renders title → mana → 4 labelled zones (Remaining Deck, Opponent Hand, Opponent Played, Cards Drawn) in top-down order, with each label exactly matching the spec text and a screen reader able to walk the structure."
  status: failed
  reason: |
    User reported (OCR + screen reader observation):
      OCR layout: 'No game in progress' / 'Remaining Deck:' / 'Opponent Hand:' / 'Opponent Played:' / 'Drawn:'
      Screen reader on panel entry only announces 'remaining_deck: empty'.
    Three concrete divergences:
      (a) Last zone label reads 'Drawn:' instead of expected 'Cards Drawn:' — direct mismatch with 03-06-SUMMARY (zone block named '("Cards Drawn:" label + _CardsDrawnListCtrl)').
      (b) Mana StaticText line is not visible in OCR — may be blank-by-design with no game, or may be missing from the layout.
      (c) Screen reader only reads the active zone status, not the labels/lists/title — could be expected (NVDA needs say-all / browse mode per HUMAN-UAT B2/B4) or could indicate an MSAA label-association regression (HUMAN-UAT B3 critical-failure path).
  severity: major
  test: 4
  artifacts: []
  missing: []
  debug_session: ""

- truth: "When Hearthstone is running and a match is in progress, the LiveGamePanel reflects live game state — title updates to '<Class> vs <Class>', Remaining Deck count decrements, Opponent Hand and Cards Drawn zones populate from real Power.log events."
  status: failed
  reason: "User reported: 'this isn't working vs the innkeeper'. The phase's core deliverable (LIVE-01..05 — live game tracking via Power.log tail → tracker → presenter → view) does not engage against Hearthstone's practice-mode Innkeeper AI. No specific failure mode given; could be log watcher not tailing, tracker.start() not running in the new wiring, parser not handling practice/tutorial match format, presenter not subscribing, or view not re-rendering on state-change events."
  severity: major
  test: 8
  artifacts: []
  missing: []
  debug_session: ""
