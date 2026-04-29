---
status: partial
phase: 03-live-game-tracking
source: [03-VERIFICATION.md]
started: 2026-04-27T00:00:00Z
updated: 2026-04-27T00:00:00Z
---

## Prerequisites

Before running the B-series accessibility checks, note these EXPECTED behaviors that are NOT defects:

1. **Mana line is intentionally blank when no game is in progress (LIVE-07).**
   The mana StaticText is constructed and present in the layout
   (`stonereader/views/live_game.py:168-169`), but its label is bound
   to `LiveGamePresenter.current_mana_summary()` which returns `""`
   when `_current_state is None`. An empty `wx.StaticText` collapses
   to ~0px and renders no glyphs — OCR will not see the line. This is
   spec behavior. The mana line populates as soon as a Hearthstone
   Constructed match begins (verify via test A9 / A11).

2. **On panel entry, NVDA only reads the active zone — full structure walk requires Say-All or browse mode.**
   The `D-17` zone-entry speech (`"Remaining deck zone: empty"` / similar)
   fires once on focus enter. NVDA does NOT auto-walk siblings. To
   verify the full panel layout (title → mana → 4 zone label/list
   pairs in top-down order), press **NVDA+Down** (Say All) or activate
   **browse mode** and traverse with arrow keys. This is documented in
   `03-UI-SPEC.md:251` as "intentional and benign". Tests B2 / B4
   directly cover the structure walk.

## Current Test

[awaiting human testing]

## Tests

### 1. A1. Launch app: home menu shows 'Live Game' as 4th entry; selection lands on Remaining Deck zone with D-17 entry speech.
expected: NVDA reads 'Remaining deck zone, M cards. <first card>, N copies, 1 of M.'
result: [pending]

### 2. A2. Open Live Game from home menu via Down-arrow + Enter.
expected: NVDA reads remaining deck zone speech; D-17 entry message fires.
result: [pending]

### 3. A3. Browse-open hotkey from outside the app — Alt-Tab away then press Ctrl+Shift+R.
expected: Live Game panel comes to focus; NVDA reads zone-entry speech.
result: [pending]

### 4. A4. Opponent-hand browse-open via Ctrl+Shift+O from outside the app.
expected: Panel focuses on Opponent Hand zone; NVDA reads 'Opponent hand zone: empty' or N-card entry.
result: [pending]

### 5. A5. Speak-only deck counts via Ctrl+Shift+D while Hearthstone has focus.
expected: NVDA speaks 'N left, opponent M.'
result: [pending]

### 6. A6. Speak-only opponent hand count via Ctrl+Shift+H from any focus.
expected: NVDA speaks 'Opponent has N cards.' (or 'No game in progress.')
result: [pending]

### 7. A7. Held-key flood check — hold Ctrl+Shift+R for ~1s.
expected: NVDA speaks the entry phrase EXACTLY ONCE (MOD_NOREPEAT honored).
result: [pending]

### 8. A8. Hotkey conflict UX — pre-register Ctrl+Shift+R via another app, then launch StoneReader.
expected: NVDA speaks 'Could not register hotkeys: Remaining Deck.' at startup.
result: [pending]

### 9. A9. Auto-detection of saved deck.
expected: Panel title shows '<Class> vs <Class> — <Saved deck name>' after mulligan.
result: [pending]

### 10. A10. Silent during arrow-read (D-07) — navigate Remaining Deck while a card-draw event fires.
expected: Each arrowed card name reads; the draw event silently re-renders without interrupting.
result: [pending]

### 11. A11. Cards drawn zone (LIVE-03).
expected: Number key 4 navigates to Cards Drawn zone; NVDA reads 'Turn X, <most recent card>, drawn, 1 of N.'
result: [pending]

### 12. A12. Graceful close (Alt+F4).
expected: App exits cleanly; no console error; relaunch can re-register hotkeys.
result: [pending]

### 13. B1. Tab order — from another widget, Tab repeatedly to LiveGamePanel.
expected: Tab focus reaches LiveGamePanel outer window; none of the 4 ListCtrls receive Tab focus directly.
result: [pending]

### 14. B2. NVDA object navigation walks each child object in top-down order.
expected: NVDA cursor walks: title → mana → 'Remaining Deck:' label → list → 'Opponent Hand:' label → list → 'Opponent Played:' label → list → 'Cards Drawn:' label → list.
result: [pending]

### 15. B3. Label-to-control association (sibling-order MSAA).
expected: Each ListCtrl, when navigated to object-style, NVDA reads its preceding StaticText label.
result: [pending]

### 16. B4. Reading order matches visual layout (NVDA 'say all', NVDA+Down).
expected: Top-to-bottom order: title → mana → remaining label → remaining items → hand label → hand items → played label → played items → drawn label → drawn items.
result: [pending]

### 17. B5. Arrow keys navigate the current zone with per-row format.
expected: Right/left/home/end advance cursor; NVDA reads per-row format (e.g., 'Glacial Shard, 1 copy, 2 of 18').
result: [pending]

### 18. B6. Number keys 1/2/3/4 switch zones.
expected: 1 → remaining_deck, 2 → opponent_played, 3 → opponent_hand, 4 → cards_drawn; D-17 zone-entry speech fires per zone.
result: [pending]

### 19. B7. NVDA 'report current line' (NVDA+Up) reads selected row.
expected: NVDA reads visual list-row text from OnGetItemText (e.g., 'Fireball (4 mana) — 2').
result: [pending]

### 20. B8. Browse-mode list traversal (NVDA+Space then arrow).
expected: Each row read individually; cursor past-end advances to next zone.
result: [pending]

## Summary

total: 20
passed: 0
issues: 0
pending: 20
skipped: 0
blocked: 0

## Gaps

_(None yet — populate as tests are run.)_

## Critical-Failure Routing

If any of these fail, escalate to `/gsd-plan-phase 3 --gaps`:
- B1 (Tab focus reaches a ListCtrl directly — `AcceptsFocus(False)` broken)
- B3 (NVDA fails to associate any StaticText label with its ListCtrl)
- B4 (Reading order is jumbled — sizer order broken)
- A8 (Conflict UX silent at startup)

Non-critical deviations (minor wording, NVDA vs JAWS speech-rate variance) can be accepted.

## Test Environment Required

- Windows 10/11
- Hearthstone installed (Constructed mode for A9–A11; Battlegrounds/Arena for skip-detection check)
- NVDA (preferred) or JAWS running
- Saved Constructed deck in StoneReader matching the deck used in-game
