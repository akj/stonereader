---
phase: 01-deck-management
verified: 2026-04-25T19:19:42Z
status: human_needed
score: 5/5 must-haves verified (automated); 3 UAT gaps closed (Gap 1 / Gap 2 / Gap 3)
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5 must-haves verified (automated)
  previous_verified: 2026-04-15T07:00:00Z
  gaps_closed:
    - "UAT Gap 1 (Test 2, DECK-01): Importing a current-meta deckstring with unknown DBF IDs no longer dead-ends; graceful-degrade builds placeholder Cards and announces unknown count."
    - "UAT Gap 2 (Test 8, D-02): Import Deck is now a transient panel; back-navigation never lands the user on it after a successful import."
    - "UAT Gap 3 (Test 8, D-06): Declining the clipboard auto-import dialog now reliably restores focus via NavigationController.restore_focus()."
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Import a current-meta deckstring (Gap 1 re-test, DECK-01)"
    expected: "Paste a deckstring whose card data is newer than the bundled hearthstone-data wheel. Import succeeds; success speech announces 'Name imported, N unknown cards' (or singular form for N=1). Deck appears in Deck Manager and persists across restart."
    why_human: "Requires running the wxPython app, real clipboard interaction, and screen reader speech verification."
  - test: "Browse saved decks (DECK-02)"
    expected: "Arrow through deck list; each deck announced as 'Name, Class, Format, N of M' with newest first."
    why_human: "Speech output and wxPython ListCtrl rendering require a live app + screen reader."
  - test: "View deck contents with detail inspection (DECK-03)"
    expected: "Select a deck, hear header announcement, arrow through cards, press down to hear card details line by line."
    why_human: "Zone navigation and detail inspection require live app interaction to confirm speech output."
  - test: "Delete a deck with confirmation (DECK-04)"
    expected: "Press Delete on a deck, confirm in dialog, hear '{Name} deleted', deck removed from list."
    why_human: "Confirmation dialog and cursor repositioning require live app interaction."
  - test: "Export deckstring to clipboard (DECK-05)"
    expected: "Press C on a deck, hear 'Deck code copied to clipboard', paste elsewhere confirms valid deckstring."
    why_human: "Clipboard write and screen reader announcement require live app verification."
  - test: "Back-navigation skips Import Deck (Gap 2 re-test, D-02)"
    expected: "From Home, open Import Deck, import a deck, then navigate around. Pressing Escape/Backspace from any panel never lands the user on Import Deck — Import Deck is bypassed because it is registered as a transient panel."
    why_human: "Panel-swap visual behavior, screen-reader announcement of the panel transition, and EVT_CHAR_HOOK key routing require live app confirmation."
  - test: "Clipboard auto-import dialog focus restoration (Gap 3 re-test, D-06)"
    expected: "Copy a valid deckstring, alt-tab away and back. Dialog asks to import. Press No. Focus reliably returns to the focus target of the panel that was previously visible (the screen reader announces it; subsequent keystrokes route to that control)."
    why_human: "Real EVT_ACTIVATE firing, OS clipboard interaction, modal-dialog focus chain, and screen-reader output require a running app."
  - test: "Card Library regression"
    expected: "Card Library category menu, search and browse work exactly as before; no regressions from gap-closure changes."
    why_human: "Full feature regression requires human walkthrough."
---

# Phase 1: Deck Management Verification Report (Re-verification post gap-closure)

**Phase Goal:** Users can manage a library of Hearthstone decks entirely through keyboard and screen reader
**Verified:** 2026-04-25T19:19:42Z
**Status:** human_needed
**Re-verification:** Yes — initial verification 2026-04-15 was human_needed; UAT 2026-04-25 surfaced 3 major gaps (Gaps 1/2/3); plans 01-05, 01-06, 01-07 were authored and executed to close them. This re-verification confirms all 3 gaps are programmatically closed and prepares the phase for human re-test of the affected flows plus the original 5 DECK requirements.

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| #   | Truth                                                                                                                  | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                  |
| --- | ---------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | User can paste a deckstring, name the deck, and find it persisted after restarting                                     | VERIFIED   | `ImportDeckPresenter.validate_and_import` (`stonereader/presenters/import_deck.py:55-100`) calls `Deck.from_deckstring(..., allow_unknown=True)` then `save_deck` to SQLite; `tests/test_import_deck.py` `test_successful_import_saves_to_db`, `test_import_success_fires_callback`, `test_missing_cards_imports_with_placeholders` (graceful-degrade) all PASS.       |
| 2   | User can arrow through a list of saved decks and hear each deck's name and class                                       | VERIFIED   | `DeckManagerPresenter._format_item_speech` overrides D-08 format; `get_all_decks` loads from DB ordered newest-first; `test_speech_format_matches_d08` passes (16 deck_manager tests).                                                                                                                                                                                  |
| 3   | User can select a deck and navigate its card list with detail inspection (down arrow reads card details)               | VERIFIED   | `DeckContentsPresenter` navigates `(Card, int)` tuples; down arrow delegates to `read_detail_lines(item, direction=1)`; 13 deck_contents tests pass; data flows from `_on_open_deck` → DeckContentsPresenter init.                                                                                                                                                       |
| 4   | User can delete a deck and is prompted for confirmation before removal                                                 | VERIFIED   | `DeckManagerPresenter._on_request_delete_confirm` callback wired; `DeckManagerPanel._on_delete_confirm` shows `wx.MessageDialog(YES_NO)`; `test_delete_current_deck_with_confirmation` and `test_delete_rejected_does_not_remove` pass.                                                                                                                                |
| 5   | User can copy a deck's deckstring to clipboard for sharing                                                              | VERIFIED   | `DeckManagerPanel._on_export` calls `wx.TheClipboard.SetData`; presenter announces "Deck code copied to clipboard"; `test_export_deckstring_returns_string` passes.                                                                                                                                                                                                       |

**Score:** 5/5 truths verified (automated). All 5 require live human testing for full closure (see Human Verification Required).

### Gap-Closure Truths (UAT 2026-04-25 → Plans 01-05/06/07)

| #   | Truth                                                                                                                                                                  | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                                                |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | A deckstring referencing DBF IDs not present in the bundled card database imports successfully via graceful-degrade with placeholder Card entries (DECK-01, Gap 1)     | VERIFIED   | `Deck.from_deckstring(..., allow_unknown=True)` (`stonereader/models/deck.py:90-130`) builds `_make_placeholder_card(dbf_id)` for each unresolved DBF; `count_unknown_cards` totals placeholders; presenter announces `"{name} imported, N unknown card[s]"`. Live behavioral spot-check confirms `MissingCardsError(99999,)` raised in strict mode; graceful mode returns Deck with `total_cards()==2`. |
| G2  | The error dialog for strict-mode missing-cards path includes the specific missing DBF IDs                                                                             | VERIFIED   | `ImportDeckPresenter._format_missing_cards_message` (`stonereader/presenters/import_deck.py:110-125`) interpolates each ID; `test_format_missing_cards_message_includes_dbf_ids` PASS; empty fallback handled by `test_format_missing_cards_message_empty_falls_back`.                                                                                                                                |
| G3  | `Card.to_speech_text()` contract preserved on placeholder Cards (returns name only)                                                                                    | VERIFIED   | `test_placeholder_to_speech_text_returns_name` PASS; live spot-check returned `"Unknown card #99999"`.                                                                                                                                                                                                                                                                                                |
| G4  | Import Deck is registered as a transient panel; back-navigation skips it (D-02, Gap 2)                                                                                 | VERIFIED   | `stonereader/app.py:399-405` registers Import Deck with `transient=True`; multi-line regex match confirmed; `_transient_panels` set populated; `test_oninit_registers_import_deck_as_transient` PASS.                                                                                                                                                                                                  |
| G5  | A transient panel is never pushed onto `_stack`; `go_back` walks only non-transient ancestry                                                                            | VERIFIED   | `NavigationController.show_panel` (lines 78-104) gates `_stack.append(name)` on `name not in self._transient_panels`; `go_back` (lines 116-156) hides transient and re-shows `_stack[-1]`; 10 transient navigation tests PASS.                                                                                                                                                                       |
| G6  | `current_panel_name` reads from `_current_visible` so callers correctly delegate to a visible transient                                                                | VERIFIED   | `stonereader/app.py:188-191` returns `self._current_visible`; introduced as separate state from `_stack`; verified by `test_show_transient_does_not_push_onto_stack` (`current_panel_name == "T"` while `_stack == ["Home"]`).                                                                                                                                                                       |
| G7  | NavigationController exposes a public `restore_focus()` helper (D-06, Gap 3)                                                                                            | VERIFIED   | `stonereader/app.py:193-207` defines `restore_focus`; calls `wx.CallAfter(target.SetFocus)` on `_focus_targets[_current_visible]`; defensive `.get()` lookup no-ops on destroyed panels; 4 behavioral tests PASS (`test_restore_focus_*`).                                                                                                                                                          |
| G8  | The clipboard auto-import dialog No path routes through `restore_focus()`                                                                                              | VERIFIED   | `stonereader/app.py:333-337` adds `else: self._nav.restore_focus()` after `dialog.Destroy()`; static regex `if result == wx.ID_YES: ... else: ... restore_focus()` matches; `test_check_clipboard_no_path_calls_restore_focus_static` PASS.                                                                                                                                                          |

### Required Artifacts

| Artifact                                          | Expected                                                                                                              | Status     | Details                                                                                                                                                                                                          |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stonereader/models/deck.py`                      | DeckSummary frozen dataclass; Deck.from_deckstring; MissingCardsError; \_make\_placeholder\_card; count\_unknown\_cards | VERIFIED   | All 5 symbols present; `MissingCardsError(ValueError)` exposes `missing_dbf_ids` tuple; `allow_unknown` is keyword-only; placeholder fields match Card frozen-dataclass invariants.                          |
| `stonereader/models/__init__.py`                  | Re-exports MissingCardsError alongside Deck/DeckSummary                                                              | VERIFIED   | Line 4: `from stonereader.models.deck import Deck, DeckSummary, MissingCardsError`; `__all__` includes `"MissingCardsError"`.                                                                                |
| `stonereader/presenters/import_deck.py`           | Graceful-degrade default; singular/plural unknown-cards announcement; \_format\_missing\_cards\_message helper       | VERIFIED   | Imports `MissingCardsError, count_unknown_cards`; `validate_and_import` passes `allow_unknown=True`; pluralization branch at lines 91-95; helper at line 110 lists DBF IDs.                                  |
| `stonereader/app.py` NavigationController          | \_transient\_panels set; \_current\_visible field; transient-aware show\_panel/go\_back/replace\_panel; restore\_focus  | VERIFIED   | All 5 features present; signatures use `*, transient: bool = False` keyword-only; `restore_focus` defensive against destroyed panels.                                                                          |
| `stonereader/app.py` MainWindow                    | Clipboard No path routes through restore\_focus                                                                       | VERIFIED   | Lines 333-337 contain the `else: ... self._nav.restore_focus()` branch; pattern is the documented modal-callsite recovery pattern.                                                                              |
| `stonereader/app.py` OnInit                        | Import Deck registered with transient=True                                                                              | VERIFIED   | Lines 399-405 register `"Import Deck"` with `transient=True`; static regex match confirmed.                                                                                                                      |
| `tests/test_deck.py`                              | Tests for graceful-degrade & MissingCardsError (created in 01-05)                                                    | VERIFIED   | 8 tests covering strict path, lenient path, partial resolution, count helper, keyword-only enforcement, to\_speech\_text preservation; all PASS.                                                            |
| `tests/test_import_deck.py`                       | Updated tests reflecting graceful-degrade defaults; 4 new tests                                                       | VERIFIED   | `test_missing_cards_imports_with_placeholders` replaces deprecated `test_missing_cards_shows_error`; 4 new tests for known-only suffix, singular form, dialog DBF inclusion, empty-tuple fallback; all PASS. |
| `tests/test_navigation.py`                        | 10 transient-panel tests + 5 restore\_focus tests                                                                     | VERIFIED   | 31 total navigation tests (16 baseline + 10 transient + 5 restore\_focus); all PASS.                                                                                                                          |

### Key Link Verification

| From                                                  | To                                                                  | Via                                                                                  | Status | Details                                                                                                                                              |
| ----------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stonereader/presenters/import_deck.py`               | `stonereader/models/deck.py`                                        | `Deck.from_deckstring(..., allow_unknown=True)` (line 62)                            | WIRED  | The graceful-degrade flag flows from presenter → model; `count_unknown_cards(deck)` then drives the speech suffix.                                  |
| `stonereader/presenters/import_deck.py`               | `stonereader/speech_service.py`                                     | `self._speech.speak(announcement)` with optional `, N unknown card[s]` suffix          | WIRED  | Both singular and plural branches produce a non-empty `announcement` and call `speak`.                                                              |
| `stonereader/app.py StoneReaderApp.OnInit`            | `stonereader/app.py NavigationController.register_panel`            | `transient=True` kwarg on the Import Deck registration (lines 399-405)               | WIRED  | Multi-line regex match confirms structural placement.                                                                                              |
| `stonereader/app.py NavigationController.show_panel`  | `_transient_panels`                                                 | `if name not in self._transient_panels: self._stack.append(name)`                    | WIRED  | Verified by `test_show_transient_does_not_push_onto_stack`.                                                                                        |
| `stonereader/app.py NavigationController.go_back`     | `_transient_panels` + `_stack`                                      | `if self._current_visible in self._transient_panels: ... target = self._stack[-1]`   | WIRED  | Verified by `test_go_back_from_transient_skips_it_returning_to_previous_non_transient`.                                                            |
| `stonereader/app.py MainWindow._check_clipboard_*`    | `stonereader/app.py NavigationController.restore_focus`              | `else: self._nav.restore_focus()` after `dialog.Destroy()`                            | WIRED  | Static regex enforces YES/else pair; behavioral tests confirm the helper schedules `wx.CallAfter` on the correct focus target.                      |
| `stonereader/app.py NavigationController.restore_focus` | `wx.CallAfter`                                                      | `wx.CallAfter(target.SetFocus)` on `_focus_targets[_current_visible]`                | WIRED  | `test_restore_focus_schedules_setfocus_on_current_panel` patches `stonereader.app.wx.CallAfter` and asserts the bound method matches.              |

### Data-Flow Trace (Level 4)

| Artifact                         | Data Variable                            | Source                                                                                                  | Produces Real Data | Status   |
| -------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------ | -------- |
| `DeckManagerPresenter`           | `self._decks`                            | `get_all_decks(self._db_conn)` via SQLite `SELECT ... ORDER BY created_at DESC, id DESC`                | Yes (real DB query)  | FLOWING  |
| `ImportDeckPresenter` (post 01-05) | `deck` (from from\_deckstring + allow\_unknown=True) | `Deck.from_deckstring(deckstring, card_db, name, allow_unknown=True)` then `save_deck(...)`           | Yes (real parse + DB insert; placeholders preserve original deckstring for future refresh) | FLOWING  |
| `DeckContentsPresenter`          | `self._cards`                            | `list(deck.cards)` from Deck passed at construction (deck source = DeckManagerPresenter `_on_open_deck`) | Yes (real Card or placeholder Card)                              | FLOWING  |
| `NavigationController` (post 01-06)  | `_current_visible`                       | `show_panel`/`go_back`/`replace_panel` write the field as authoritative source for `current_panel_name` | Yes (drives `_on_find` and `restore_focus`)                      | FLOWING  |
| `restore_focus` (post 01-07)         | `target` (focus widget)                  | `_focus_targets.get(_current_visible)` → `wx.CallAfter(target.SetFocus)`                                | Yes (real wx widget bound method)                                | FLOWING  |

### Behavioral Spot-Checks

| Behavior                                                                                                          | Command                                                                                                                                              | Result                                                                                  | Status |
| ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------ |
| Full test suite                                                                                                   | `uv run pytest tests/ -v`                                                                                                                            | 169 passed in 0.80s                                                                     | PASS   |
| `register_panel(transient=...)` is keyword-only and accepted                                                       | `inspect.signature(NavigationController.register_panel).parameters['transient'].kind == KEYWORD_ONLY`                                                | OK                                                                                      | PASS   |
| `NavigationController` exposes `restore_focus` callable                                                            | `hasattr(NavigationController, 'restore_focus')`                                                                                                     | OK                                                                                      | PASS   |
| `Deck.from_deckstring(..., allow_unknown=...)` keyword-only                                                        | `inspect.signature(Deck.from_deckstring).parameters['allow_unknown'].kind == KEYWORD_ONLY`                                                           | OK                                                                                      | PASS   |
| Strict mode raises MissingCardsError exposing missing DBF IDs                                                      | `Deck.from_deckstring(<99999 deckstring>, empty_db, "X")` → `MissingCardsError(missing_dbf_ids=(99999,))`                                            | Raised with `(99999,)`                                                                  | PASS   |
| Graceful-degrade mode produces a Deck with placeholders                                                            | `Deck.from_deckstring(<99999 deckstring>, empty_db, "X", allow_unknown=True)` → `count_unknown_cards == 2`, placeholder.id starts with `UNKNOWN_`     | OK; placeholder name `"Unknown card #99999"`                                            | PASS   |
| Card.to\_speech\_text contract preserved on placeholders                                                           | `placeholder.to_speech_text() == "Unknown card #99999"`                                                                                              | OK                                                                                      | PASS   |
| Multi-line regex confirms Import Deck transient registration                                                       | regex `register_panel(...Import Deck...transient=True...)` against `stonereader/app.py`                                                              | match                                                                                   | PASS   |
| Multi-line regex confirms YES/else pair calling restore\_focus                                                     | regex `if result == wx.ID_YES: ... else: ... self._nav.restore_focus()` against `stonereader/app.py`                                                 | match                                                                                   | PASS   |
| Ruff lint on touched files                                                                                         | `uv run ruff check stonereader/app.py stonereader/models/deck.py stonereader/presenters/import_deck.py tests/test_navigation.py tests/test_deck.py tests/test_import_deck.py` | All checks passed!                                                              | PASS   |
| Pyright on touched source files                                                                                    | `uv run pyright stonereader/app.py stonereader/models/deck.py stonereader/presenters/import_deck.py`                                                 | 0 errors, 0 warnings, 0 informations                                                    | PASS   |
| Smoke imports                                                                                                      | `uv run python -c "from stonereader.models.deck import Deck, MissingCardsError, count_unknown_cards, _make_placeholder_card; ..."`                  | OK                                                                                      | PASS   |

### Requirements Coverage

| Requirement | Source Plan(s)               | Description                                                       | Status    | Evidence                                                                                                                                                     |
| ----------- | ---------------------------- | ----------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| DECK-01     | 01-03, 01-04, 01-05, 01-07   | User can import a deck by pasting a deckstring and naming it      | SATISFIED | `ImportDeckPresenter.validate_and_import` + graceful-degrade Deck.from\_deckstring + restore\_focus on dialog cancel; 16 import tests + clipboard tests pass.   |
| DECK-02     | 01-01, 01-03, 01-04, 01-06   | User can browse saved decks in a navigable list                   | SATISFIED | `DeckManagerPresenter` loads from DB; D-08 speech format; back-navigation correctly bypasses Import Deck (transient).                                         |
| DECK-03     | 01-02, 01-04                 | User can view deck contents with card details via zone navigation | SATISFIED | `DeckContentsPresenter` navigates card tuples; down arrow reads detail lines; wired via `set_on_open_deck` → `replace_panel("Deck Contents")`.            |
| DECK-04     | 01-01, 01-03, 01-04          | User can delete a saved deck with confirmation                    | SATISFIED | `delete_deck` SQL; `DeckManagerPanel` MessageDialog; cursor repositioning tested.                                                                            |
| DECK-05     | 01-01, 01-03, 01-04          | User can export a deck's deckstring to clipboard                  | SATISFIED | `DeckManagerPanel._on_export` writes to `wx.TheClipboard`; presenter announces speech.                                                                      |

All 5 DECK requirements declared by phase plans are accounted for. Note: REQUIREMENTS.md still lists DECK-02..DECK-05 as `Pending`; the traceability table should be updated to mark them complete after human re-test confirms the live behavior. DECK-01 was already updated to "Complete (01-03, 01-07)" in REQUIREMENTS.md.

No orphaned requirements found.

### Anti-Patterns Found

| File                                          | Line(s) | Pattern                              | Severity | Impact                                                                                                                              |
| --------------------------------------------- | ------- | ------------------------------------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `stonereader/presenters/deck_manager.py`      | ~55     | `return []` for unknown zone names   | Info     | Legitimate fallback for unknown zone names in `get_zone_items`; `self._decks` is populated from real DB query. Documented earlier. |
| `stonereader/presenters/import_deck.py`       | ~106    | `return {}` for `get_key_map`         | Info     | Intentional — ImportDeck uses Tab navigation, not zone hotkeys; documented in docstring.                                            |
| `tests/test_deck_manager.py`                  | 7, 9    | F401 unused imports                   | Info     | Pre-existing (confirmed against base commit `b407306`); documented in `deferred-items.md`. Not introduced by gap-closure plans.    |

No blockers or warnings introduced by gap-closure plans. The repo-wide ruff `Found 2 errors` are the documented pre-existing F401s in `tests/test_deck_manager.py`; touched files are fully clean.

### Gap Closure Recap (UAT 2026-04-25)

**Original UAT result:** 8 passed / 1 issue (Test 8 had two reported behaviors plus the separately-discovered Test 2 hearthstone-data refresh need).

| UAT Issue                                                                                | Plan       | Resolution                                                                                                                                                       | Status |
| ---------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| Gap 1 (Test 2): "Some cards in this deck were not found" with no recovery path           | 01-05      | `Deck.from_deckstring(allow_unknown=True)` builds placeholders; presenter announces unknown count; strict-mode dialog now lists missing DBF IDs                | CLOSED |
| Gap 2 (Test 8): Back-navigation walks back to Import Deck after a successful import       | 01-06      | Import Deck registered transient; `_stack` excludes it; `go_back` skips visible transients to top of `_stack`                                                  | CLOSED |
| Gap 3 (Test 8): Declining clipboard auto-import dialog leaves focus undefined            | 01-07      | `NavigationController.restore_focus()` schedules `wx.CallAfter(focus_target.SetFocus)`; No path now routes through it; pattern reusable for future modals      | CLOSED |

Each closure pairs a RED commit (failing tests) with a GREEN commit (implementation). All commits are present in `git log`:

- 01-05: `4030c71` (RED) → `459922f` (GREEN model) → `5f4ff46` (RED presenter) → `3a30f05` (GREEN presenter)
- 01-06: `9517ab4` (RED) → `19a13f7` (GREEN)
- 01-07: `5d83017` (RED) → `387a3f9` (GREEN)

### Human Verification Required

The phase still requires a live re-test of the original 5 DECK success criteria plus the 3 gap-closure UX behaviors. Programmatic verification confirms the code structure and test contracts are correct; what cannot be verified without the running app:

#### 1. Import a current-meta deckstring (Gap 1 re-test, DECK-01)

**Test:** Run `uv run python -m stonereader`. Open Import Deck. Paste a deckstring whose card data is newer than the bundled hearthstone-data wheel (deliberately older wheel if needed to reproduce). Enter a name. Press Import.
**Expected:** Speech: `"<Name> imported, N unknown cards"` (or `, 1 unknown card` for N=1). Deck appears in Deck Manager. Quit and relaunch — deck still present. No error dialog appears.
**Why human:** Real clipboard interaction, wxPython TextCtrl focus, and screen reader speech verification require a live app.

#### 2. Browse saved decks (DECK-02)

**Test:** From Deck Manager, arrow up/down through saved decks.
**Expected:** Each deck announced as `"Name, Class, Format, N of M"`; newest first.
**Why human:** Speech and ListCtrl rendering require live NVDA/JAWS or stdout fallback.

#### 3. Deck contents and detail inspection (DECK-03)

**Test:** Press Enter on a deck. Arrow through cards. Press Down to read card details line by line.
**Expected:** Header announced; cards as `"CardName x{count}, N of M"`; down arrow reads cost/type/text sequentially.
**Why human:** Zone navigation speech, detail line reading, and panel-swap behavior require a live app.

#### 4. Delete with confirmation (DECK-04)

**Test:** Press Delete on a deck. Cancel; then confirm deletion on a different deck.
**Expected:** Cancel leaves deck intact; confirm removes deck with `"{Name} deleted"` speech and correct cursor repositioning.
**Why human:** wx.MessageDialog rendering and cursor behavior require a live app.

#### 5. Export to clipboard (DECK-05)

**Test:** Press C on a selected deck.
**Expected:** Speech: `"Deck code copied to clipboard"`. Paste into a text editor — text matches the original deckstring.
**Why human:** wx.TheClipboard interaction requires a running wxPython event loop.

#### 6. Back-navigation skips Import Deck (Gap 2 re-test, D-02)

**Test:** From Home, open Import Deck. Import a deck (success). Then navigate to other panels (Deck Manager, Card Library, etc.) and press Escape/Backspace repeatedly.
**Expected:** Back-navigation never lands the user on Import Deck. Going Home → Import Deck → (success) → Deck Manager → Escape lands on Home directly. Pressing Escape from Import Deck itself dismisses the panel back to where it was opened from.
**Why human:** Panel-swap visibility and EVT\_CHAR\_HOOK key routing require a live app.

#### 7. Clipboard auto-import dialog focus restoration (Gap 3 re-test, D-06)

**Test:** Copy a valid deckstring to clipboard. Alt-tab away from StoneReader and back. The dialog asks to import. Press No.
**Expected:** Focus reliably returns to the focus target of the panel that was visible before the dialog popped (typically Home). The screen reader announces the focus restoration; subsequent keystrokes are received by that control.
**Why human:** Real EVT\_ACTIVATE firing, modal dialog focus chain, and screen-reader output require a live app.

#### 8. Card Library regression

**Test:** Navigate to Card Library; pick a category; search and browse cards; use detail inspection.
**Expected:** All Card Library behaviors unchanged from the previous milestone (Card Library category menu refactor).
**Why human:** Full feature regression requires a human walkthrough.

### Gaps Summary

No new automated gaps found. All 3 UAT-reported gaps (Gap 1, Gap 2, Gap 3) are programmatically closed:

- **Gap 1 (Test 2):** Closed by 01-05 — graceful-degrade import + DBF diagnostics. Verified by 8 new tests in `tests/test_deck.py`, 4 new tests in `tests/test_import_deck.py`, and a live behavioral spot-check that exercised `MissingCardsError` in strict mode and placeholder construction in lenient mode.
- **Gap 2 (Test 8):** Closed by 01-06 — transient-panel concept + Import Deck registered transient. Verified by 10 new tests in `tests/test_navigation.py`, including a static regex match on `stonereader/app.py` confirming the OnInit registration uses `transient=True`.
- **Gap 3 (Test 8):** Closed by 01-07 — `NavigationController.restore_focus()` + clipboard No-path routing. Verified by 5 new tests in `tests/test_navigation.py`, including a static regex match on the YES/else structural pair.

The full test suite is now **169 passed** (was 120 at initial verification, 154 after 01-05, 152 effective after 01-06's adjusted count, 169 after 01-07). Lint and type checks are clean on all touched files. The two pre-existing F401 errors in `tests/test_deck_manager.py` remain documented in `deferred-items.md` and are out of scope.

The phase is blocked only by human re-test of the 8 listed end-to-end behaviors. Once those are confirmed, REQUIREMENTS.md should be updated to mark DECK-02 through DECK-05 as Complete (DECK-01 is already marked Complete with reference to plans 01-03 and 01-07).

---

_Re-verified: 2026-04-25T19:19:42Z_
_Verifier: Claude (gsd-verifier)_
_Previous verification: 2026-04-15T07:00:00Z (initial, status human\_needed)_
