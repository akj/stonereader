---
status: partial
phase: 01-deck-management
source: [01-VERIFICATION.md]
started: 2026-04-25T19:20:00Z
updated: 2026-04-25T19:20:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Import a current-meta deckstring (Gap 1 re-test, DECK-01)
expected: Paste a deckstring whose card data is newer than the bundled hearthstone-data wheel. Import succeeds; success speech announces "Name imported, N unknown cards" (or singular form for N=1). Deck appears in Deck Manager and persists across restart.
result: [pending]

### 2. Browse saved decks (DECK-02)
expected: Arrow through deck list; each deck announced as "Name, Class, Format, N of M" with newest first.
result: [pending]

### 3. View deck contents with detail inspection (DECK-03)
expected: Select a deck, hear header announcement, arrow through cards, press down to hear card details line by line.
result: [pending]

### 4. Delete a deck with confirmation (DECK-04)
expected: Press Delete on a deck, confirm in dialog, hear "{Name} deleted", deck removed from list.
result: [pending]

### 5. Export deckstring to clipboard (DECK-05)
expected: Press C on a deck, hear "Deck code copied to clipboard", paste elsewhere confirms valid deckstring.
result: [pending]

### 6. Back-navigation skips Import Deck (Gap 2 re-test, D-02)
expected: From Home, open Import Deck, import a deck, then navigate around. Pressing Escape/Backspace from any panel never lands the user on Import Deck — Import Deck is bypassed because it is registered as a transient panel.
result: [pending]

### 7. Clipboard auto-import dialog focus restoration (Gap 3 re-test, D-06)
expected: Copy a valid deckstring, alt-tab away and back. Dialog asks to import. Press No. Focus reliably returns to the focus target of the panel that was previously visible (the screen reader announces it; subsequent keystrokes route to that control).
result: [pending]

### 8. Card Library regression
expected: Card Library category menu, search and browse work exactly as before; no regressions from gap-closure changes.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps
