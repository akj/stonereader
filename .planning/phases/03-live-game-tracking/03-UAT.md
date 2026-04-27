---
status: diagnosed
phase: 03-live-game-tracking
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05-SUMMARY.md, 03-06-SUMMARY.md]
started: 2026-04-27T15:04:36Z
updated: 2026-04-27T15:13:00Z
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
  root_cause: |
    No production code defect. (a) The source label is verifiably 'Cards Drawn:' at stonereader/views/live_game.py:190 — OCR truncated. (b) The mana StaticText IS present (constructed at line 168, sizer-added at 169, label-bound at 260 to presenter.current_mana_summary() which returns "" when _current_state is None) — empty StaticText collapses to ~0px and renders no glyphs for OCR; this is exactly the LIVE-07 spec ("populates when game starts"). (c) MSAA sibling order is correct (all 4 label+list pairs are flat children of LiveGamePanel's outer wx.BoxSizer(wx.VERTICAL); no nested sub-panels). AcceptsFocus chain is correct (panel has wx.WANTS_CHARS, all 4 ListCtrls override AcceptsFocus()->False). The user's "remaining_deck: empty" is a paraphrase of the spec speech "Remaining deck zone: empty" (presenters/live_game.py:323). One-announcement-on-focus-enter is expected NVDA semantics — full-structure walk requires NVDA+Down (Say All) or browse mode, exactly as documented in 03-UI-SPEC.md:251 and tested by HUMAN-UAT B2/B4.
  artifacts:
    - path: "stonereader/views/live_game.py:190"
      issue: "label='Cards Drawn:' verified — OCR observation was a measurement artifact"
    - path: "stonereader/views/live_game.py:168-169, 260"
      issue: "mana StaticText present-and-empty by spec when _current_state is None (LIVE-07)"
    - path: "stonereader/views/live_game.py:161-195"
      issue: "MSAA sibling order correct; no regression"
    - path: ".planning/phases/03-live-game-tracking/03-HUMAN-UAT.md"
      issue: "B2/B4 prerequisites about NVDA Say-All / browse mode could be made more explicit so testers don't mistake spec behavior for a regression"
  missing:
    - "Add HUMAN-UAT prerequisite note: mana line is intentionally blank when no game is in progress; populates when a Constructed match starts (LIVE-07)."
    - "Add HUMAN-UAT prerequisite note: on panel entry NVDA announces only the zone-entry speech; full-structure walk requires NVDA+Down (Say All) or browse mode (matches 03-UI-SPEC.md:251 and B2/B4 expectations)."
    - "Optional: confirm with user that they actually heard 'Remaining deck zone: empty' (paraphrased as 'remaining_deck: empty')."
  debug_session: ".planning/debug/live-game-panel-layout.md"

- truth: "When Hearthstone is running and a match is in progress, the LiveGamePanel reflects live game state — title updates to '<Class> vs <Class>', Remaining Deck count decrements, Opponent Hand and Cards Drawn zones populate from real Power.log events."
  status: failed
  reason: "User reported: 'this isn't working vs the innkeeper'. The phase's core deliverable (LIVE-01..05 — live game tracking via Power.log tail → tracker → presenter → view) does not engage against Hearthstone's practice-mode Innkeeper AI."
  severity: major
  test: 8
  root_cause: |
    GameEngine._refresh_state() at stonereader/services/_engine.py:562-609 only republishes 5 of ~15 GameState fields (player_played, opponent_played, player_drawn, opponent_drawn, opponent_hand). It never populates state.player_deck, player_deck_count, opponent_deck_count, player_mana, player_max_mana, opponent_mana, opponent_max_mana, player_hero, opponent_hero, player_hand, player_board, or opponent_board from the _entities dict — those fields stay at their _on_create_game defaults (empty_hero with hero_class="", (), 0) for the entire game. This is independent of game type (Innkeeper / GT_VS_AI is a normal Power.log match). The presenter consumes state.player_deck (LIVE-02), state.player_hero.hero_class (LIVE-08 title), state.player_mana (LIVE-07 mana surface), state.player_deck_count (LIVE-06) — all permanently empty, so the UI cannot reflect anything. Auto-deck-detection is also gated on revealed_count = sum(1 for e in state.player_deck if e.card_id) >= 30, and since player_deck is permanently (), detection never fires.
    Test gap that masked it: tests/test_live_game_presenter.py uses _make_state(player_deck=..., player_mana=...) helper to construct fully-populated synthetic GameState. Presenter unit tests pass against synthetic state; engine unit tests pass against synthetic packets; no integration test runs real Power.log through parser → engine → presenter to verify the engine publishes what the presenter consumes.
    Confirmed working links in the chain: tracker.start() IS called at app.py:573; ensure_log_config() runs at app.py:402 so Hearthstone Power logging is auto-enabled; LiveGamePresenter subscribes synchronously in __init__ before tracker.start; LiveGamePanel wires set_on_state_changed / set_on_title_changed; threading is fine (wx.Timer on main thread).
  artifacts:
    - path: "stonereader/services/_engine.py:562-609"
      issue: "_refresh_state rebuilds 5 fields, leaves ~10 untouched (player_deck, player_deck_count, opponent_deck_count, player_mana, player_max_mana, opponent_mana, opponent_max_mana, player_hero, opponent_hero, player_hand, player_board, opponent_board)"
    - path: "stonereader/services/_engine.py:311-334"
      issue: "_on_create_game constructs GameState with empty_hero (hero_class=''), no player_deck, all mana/deck-count fields at 0 — never updated thereafter"
    - path: "stonereader/services/_engine.py:347-395"
      issue: "_on_tag_change handles TURN/CURRENT_PLAYER/ZONE/PLAYSTATE/DAMAGE/MULLIGAN_STATE but NOT RESOURCES, RESOURCES_USED, NUM_CARDS_IN_DECK; no hero-resolution path reads HERO_ENTITY/HERO_CLASS"
    - path: "stonereader/presenters/live_game.py:134-138, 187-210, 282-291, 305-313, 331-340"
      issue: "Consumes state fields the engine never publishes — no defect in presenter, but it cannot do anything with empty data"
    - path: "tests/test_live_game_presenter.py:87-127"
      issue: "_make_state synthetic-state helper masks the engine-publication gap; no integration test feeds real Power.log through the chain"
  missing:
    - "Hero resolution: identify each player's HERO_ENTITY (CARDTYPE==HERO controlled by player N) at CREATE_GAME and on subsequent FullEntity/SHOW_ENTITY packets; look up via card_db; populate player_hero / opponent_hero with real name/health/armor/hero_class. Unblocks LIVE-08 title and feeds auto-deck-detection's class filter."
    - "player_deck rebuild in _refresh_state: iterate _entities for entities with ZONE==DECK and CONTROLLER==_friendly_player_id; build the GameEntity tuple the same way opponent_hand is rebuilt at engine.py:572-600. Unblocks LIVE-02 (Remaining Deck) and auto-deck-detection."
    - "Deck counts + mana via _on_tag_change: add cases for NUM_CARDS_IN_DECK (per controller → player_deck_count / opponent_deck_count) and RESOURCES + RESOURCES_USED (per controller → player_mana = RESOURCES − RESOURCES_USED, player_max_mana = RESOURCES). Unblocks LIVE-06 / LIVE-07."
    - "Integration test: feed a captured Power.log fixture through real parser + engine (no MockGameTracker shortcut); assert tracker.current_state.player_deck has 30 entities, player_hero.hero_class is non-empty, player_max_mana advances on TURN tags. Closes the test-coverage gap that let this slip."
  debug_session: ".planning/debug/live-tracking-not-engaging-vs-innkeeper.md"
