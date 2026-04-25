---
status: complete
phase: 01-deck-management
source:
  - 01-01-SUMMARY.md
  - 01-02-SUMMARY.md
  - 01-03-SUMMARY.md
  - 01-04-SUMMARY.md
started: 2026-04-24T21:42:00Z
updated: 2026-04-25T01:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: |
  Kill any running StoneReader process. Optionally clear ~/.stonereader/stonereader.db
  to test fresh-DB initialization. Launch via `uv run python -m stonereader`. The main
  window opens, the home screen shows "StoneReader" heading and a "Features:" list
  with 3 items (Card Library, Deck Manager, Import Deck). Screen reader announces
  the first item with position. No tracebacks in terminal.
result: pass

### 2. Import a deck end-to-end (DECK-01)
expected: |
  From the home screen, navigate to "Import Deck" and press Enter. Paste a valid
  Hearthstone deckstring into the deck-code field, type a name into the name field,
  press Import. Hear "{Name} imported". Navigate to "Deck Manager" — the new deck
  appears in the list. Quit the app, relaunch, navigate to Deck Manager — the deck
  is still there.
result: pass
note: |
  First attempt with hearthstone-data 223542.1 surfaced an "unknown cards" error
  on a current-meta deckstring (1/17 cards from a newer patch). Ran
  `uv lock --upgrade && uv sync`, bumping hearthstone-data to 240818.1; deck
  fully resolved on re-run and import succeeded. Independent gap (no in-app
  refresh affordance) remains logged below for post-UAT fix pass.

### 3. Browse saved decks (DECK-02)
expected: |
  From home, open Deck Manager. Hear the deck list focus. Arrow up/down through
  the list — each deck announces as "Name, Class, Format, N of M" with newest
  decks first.
result: pass

### 4. View deck contents with card detail inspection (DECK-03)
expected: |
  From Deck Manager, select a deck and press Enter. Hear the deck header
  (e.g. "{Name}: {N} cards, {Class}, {Format}"). Arrow through cards — each
  announces as "CardName x{count}, N of M". Press Down arrow on a card and
  hear card details read line by line (cost, type, text, etc.).
result: pass

### 5. Delete a deck with confirmation (DECK-04)
expected: |
  From Deck Manager, select a deck and press Delete. A confirmation dialog
  appears (Yes/No). Choose Yes — hear "{Name} deleted", deck is removed from
  the list, cursor lands on a sensible neighboring deck. Choose No on a different
  deck — the deck remains.
result: pass

### 6. Export deckstring to clipboard (DECK-05)
expected: |
  From Deck Manager, select a deck and press C. Hear "Deck code copied to clipboard."
  Paste into another app — the pasted text is a valid Hearthstone deckstring
  (starts with "AAEC..." or similar base64).
result: pass

### 7. Clipboard auto-detection (D-06)
expected: |
  Copy a valid Hearthstone deckstring from another app (e.g. a website). Switch
  back to StoneReader (alt-tab or click). The app detects the deckstring on focus
  and prompts (dialog or speech) asking whether to import it. The initial app
  launch does NOT trigger this prompt with a stale clipboard.
result: pass

### 8. Escape/Backspace back navigation (D-02)
expected: |
  From any feature panel (Card Library, Deck Manager, Import Deck, Deck Contents),
  press Escape or Backspace and return to the home screen. From the home screen,
  Escape/Backspace do nothing (or do not navigate away). Going deep
  (Home -> Deck Manager -> Deck Contents) and pressing Escape twice returns to
  Home, restoring each previous panel's key map.
result: issue
reported: |
  Couple odd behaviors to flag:
  1. If I click "import a deck" and subsequently go somewhere after importing,
     "import a deck" is one of the places I head on backwards navigation with
     escape. Importing a deck isn't a menu item in the same sense that the card
     library and deck manager are; I think of it like a modal that gets opened
     to perform an operation.
  2. When in the deck import dialog, if I press no to auto-import a clipboard
     deckstring, focus doesn't reliably return to the app.
severity: major

### 9. Card Library unchanged (regression)
expected: |
  From home, open Card Library. Search and browse work exactly as before the
  NavigationController refactor — search returns results, arrow navigation through
  zones works, detail inspection on cards works, no missing/broken behaviors.
result: pass

## Summary

total: 9
passed: 8
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "User can import a current-meta deckstring without first manually upgrading a Python dependency"
  status: failed
  reason: |
    User reported: "Got this error dialog: 'Some cards in this deck were not
    found in the card database. The deck code may be from a newer expansion.'
    Code: AAEBAR8EnvgC/fgDwbkEzZ4GDYAH6asCudADqZ8Eqp8EnbAEmpIFjp4G6qUG5OoGr5IH15cHu8AHAAA="
    Investigation: 16/17 cards present, 1 from newer patch (DBF 122939). Local
    hearthstone-data was 223542.1; upgrading to 240818.1 resolved this specific
    deck, but no in-app mechanism exists to refresh card data. Card data is
    pinned in uv.lock and only updates when the developer rebuilds.
  severity: major
  test: 2
  root_cause: |
    `CardDatabase.load()` (stonereader/models/card.py:175) calls
    `hearthstone.cardxml.load()`, which reads CardDefs.xml from the bundled
    hearthstone-data wheel. Card data is pinned per release. There is no
    affordance to:
      - check for a newer hearthstone-data on startup or on demand
      - download a fresh CardDefs.xml from HearthSim's mirror
      - gracefully degrade by importing the deck with placeholder names for
        unknown DBF IDs (so users can still use partial decks)
  artifacts:
    - path: stonereader/models/card.py
      issue: "CardDatabase.load() has no refresh path; data baked into pinned wheel"
    - path: stonereader/models/deck.py
      issue: "Deck.from_deckstring raises 'Missing cards' on any unknown DBF, no graceful-degrade option"
    - path: stonereader/presenters/import_deck.py
      issue: "ValueError handler shows generic message; no path to retry after refresh, no diagnostic of which cards are missing"
  missing:
    - "Refresh affordance (menu item, hotkey, or startup check) to update CardDefs.xml"
    - "Graceful-degrade import path (placeholder for unknown cards) OR on-demand fetch from HearthSim mirror"
    - "Surfacing missing DBF IDs in the error dialog so user/dev can diagnose"
  debug_session: ""

- truth: "Import Deck behaves as a transient operation, not a navigable destination — back navigation skips it after success"
  status: failed
  reason: |
    User reported: "If I click 'import a deck' and subsequently go somewhere
    after importing, 'import a deck' is one of the places I head on backwards
    navigation with escape. Importing a deck isn't a menu item in the same
    sense that the card library and deck manager are; I think of it like a
    modal that gets opened to perform an operation."
  severity: major
  test: 8
  root_cause: |
    `Import Deck` is registered with `NavigationController.register_panel`
    (stonereader/app.py:306) like any other destination, so it gets pushed onto
    `_history` whenever shown. On import success, the import-success callback
    navigates forward to "Deck Manager" via `nav.show_panel`, which pushes
    Deck Manager but does NOT pop Import Deck. Subsequent `go_back` walks the
    full stack, so the user lands back on Import Deck.
    Mental model mismatch: user expects Import Deck to be modal/transient
    (a one-shot operation) while the implementation treats it as a peer-level
    panel.
  artifacts:
    - path: stonereader/app.py
      issue: "NavigationController has no notion of 'modal/transient' panels — every show_panel pushes onto _history"
    - path: stonereader/app.py:306
      issue: "Import Deck registered as regular panel; success path navigates forward without popping origin"
    - path: stonereader/presenters/import_deck.py
      issue: "Import success callback is forward-navigation only; doesn't tell nav controller to remove itself"
  missing:
    - "Modal/transient panel concept in NavigationController (e.g. show_modal_panel that doesn't push)"
    - "OR: import-success path that calls go_back before forward-navigating to Deck Manager"
    - "OR: explicit pop_self affordance for transient panels"
  debug_session: ""

- truth: "Declining the clipboard auto-import dialog returns focus reliably to the active panel"
  status: failed
  reason: |
    User reported: "When in the deck import dialog, if I press no to
    auto-import a clipboard deckstring, focus doesn't reliably return to the
    app."
  severity: major
  test: 8
  root_cause: |
    In `MainWindow._check_clipboard_for_deckstring` (stonereader/app.py:226-244),
    the Yes path explicitly calls `wx.CallAfter(import_panel.name_ctrl.SetFocus)`,
    but the No path falls through with no focus restoration. After
    `dialog.Destroy()`, wx may leave focus on the destroyed dialog's parent
    chain or hand it back unpredictably — particularly bad for screen reader
    users who lose their place silently.
  artifacts:
    - path: stonereader/app.py
      issue: "_check_clipboard_for_deckstring No-path lacks SetFocus on the current panel's focus target after dialog dismissal"
  missing:
    - "Explicit `wx.CallAfter(<current_panel_focus_target>.SetFocus)` after dialog.Destroy() on the No path"
    - "Or: NavigationController exposes 'restore focus to current panel' helper that any modal callsite can invoke"
  debug_session: ""
