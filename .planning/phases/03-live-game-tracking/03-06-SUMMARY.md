---
phase: 03-live-game-tracking
plan: 06
subsystem: ui
tags: [phase-03, live-game-panel, app-wiring, home-menu, hotkey-chords, integration, mvp, wx-virtual-listctrl, close-cleanup, continue-on-failure, wave-3]

# Dependency graph
requires:
  - phase: 03-live-game-tracking
    provides: 03-04 — GlobalHotkeyService (wx.Frame.RegisterHotKey wrapper with cumulative `failed` accumulator and MOD_NOREPEAT defaulting); 03-05 — LiveGamePresenter (wx-free) with 4 zones, auto-deck-detection, public accessors per REVIEWS HIGH #3, and `announce_opponent_hand_count` / `announce_deck_counts` / `jump_to_zone` / `cleanup` public surface
  - phase: 02-log-infrastructure
    provides: GameTracker subscriber bus (constructed at app startup as `self._tracker`), feeds LiveGamePresenter through tracker.subscribe
  - phase: 01-deck-management
    provides: NavigationController (`nav.register_panel` / `nav.show_panel`), HomePresenter `set_on_select` dispatcher, MainWindow `_on_close` cleanup hook
provides:
  - LiveGamePanel — passive 4-zone wx.Panel rendering Remaining Deck / Opponent Hand / Opponent Played / Cards Drawn via virtual ListCtrls + title StaticText + mana StaticText
  - 4 row-format helpers in `stonereader/views/_live_game_format.py` — single source of truth for visual list-row text shared between view OnGetItemText and (future) tests; complements presenter D-13/D-14/D-15 speech formats
  - Home-menu fourth entry "Live Game" (MENU_ITEMS extended from 3 to 4)
  - StoneReaderApp.OnInit composition root extension — constructs LiveGamePresenter + LiveGamePanel, registers as nav panel, stashes presenter on frame; constructs GlobalHotkeyService(self._frame) after frame.Show(), registers 4 Ctrl+Shift+{R,O,D,H} chords, announces conflict failures via SpeechService
  - MainWindow._on_close cleanup ordering with per-step try/except continue-on-failure: hotkeys.clear_all → live_presenter.cleanup → tracker.stop → db_conn.close → Destroy (regression-locked by 2 navigation tests)
  - Public-accessor wiring contract — view + app + tests all use `current_title()` / `cursor_for_zone()` / `current_mana_summary()` / `get_zone_items()` / `announce_opponent_hand_count()` exclusively (no `_zone_cursors` / `_format_title` / `_current_state` reads anywhere)
affects: [04-replay-viewer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Composition-root extension: import + construct + register pattern for new presenters/views matches existing `# --- Card Library ---` / `# --- Deck Manager ---` / `# --- Import Deck ---` blocks at `app.py`"
    - "Virtual wx.ListCtrl with `wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER` + `AcceptsFocus() -> False` per UI-SPEC; rows fed via `set_rows(...)` + `OnGetItemText` delegating to centralized format helpers"
    - "Cleanup ordering with per-step try/except continue-on-failure: each cleanup step wrapped in its own try/except + `log.exception(...)` so a raise in step N does NOT prevent steps N+1..end from running (per 03-REVIEWS.md MEDIUM 03-06 #5)"
    - "Public-accessor-only view contract: views never read presenter private fields; presenter exposes `current_title()` / `cursor_for_zone()` / `current_mana_summary()` for view consumption (per 03-REVIEWS.md HIGH #3)"
    - "Frame attribute attachment pattern (`self._frame._live_presenter = live_presenter`) — internal coupling matching pre-existing `self._frame._tracker` pattern; `getattr(self, '_live_presenter', None)` defensive read in cleanup"
    - "Speak-only hotkey delegation: app-side hotkey callback contains NO state-read; delegates to `presenter.announce_opponent_hand_count()` (a public method tested in 03-05) — keeps app.py thin and testable"

key-files:
  created:
    - stonereader/views/_live_game_format.py
    - stonereader/views/live_game.py
    - .planning/phases/03-live-game-tracking/03-06-SUMMARY.md
  modified:
    - stonereader/presenters/home.py
    - stonereader/app.py
    - tests/test_home.py
    - tests/test_navigation.py
    - .planning/phases/03-live-game-tracking/deferred-items.md

key-decisions:
  - "MENU_ITEMS extended in display order — Live Game is the 4th entry; home-menu select callback special-cases 'Live Game' to chain `nav.show_panel(name)` with `live_presenter.jump_to_zone('remaining_deck')` so menu-entry speech matches Ctrl+Shift+R browse-open speech"
  - "Row-format helpers live in a SEPARATE module (`_live_game_format.py`) rather than inside `live_game.py` — keeps view module focused on widget construction, makes helpers trivially importable from future tests, and prevents drift across the 4 OnGetItemText overrides per 03-REVIEWS.md MEDIUM 03-06 #1"
  - "Per-step try/except + log.exception in `_on_close` rather than a single try/except wrapping all 4 steps — per 03-REVIEWS.md MEDIUM 03-06 #5, a raise in hotkeys.clear_all() must NOT prevent live_presenter.cleanup(), tracker.stop(), or db_conn.close() from running. test_close_continues_on_failure regression-locks all 4 steps by injecting RaisingHotkeys/RaisingPresenter/RaisingTracker/RaisingDb"
  - "GlobalHotkeyService constructed AFTER frame.Show() and BEFORE tracker.start() — frame must exist (Show creates the OS HWND that RegisterHotKey targets), but failures should announce before tracker starts emitting events. Conflict-UX announcement reads `self._hotkeys.failed` immediately after the 4 register() calls"
  - "Task 3 manual NVDA/JAWS smoke test deferred to HUMAN-UAT — orchestrator's verify_phase_goal step persists the A1-A12 + B1-B8 checklist as `.planning/phases/03-live-game-tracking/HUMAN-UAT.md`; user has approved the deferral so this plan is marked complete now"

patterns-established:
  - "View module + format-helper-module pair: when row text is shared across multiple ListCtrl OnGetItemText overrides, extract helpers to `views/_<feature>_format.py` (mirrors `services/_*` private-module convention)"
  - "Composition-root layered extension: each new presenter/view gets a `# --- <Name> ---` block in OnInit between existing blocks; consistent ordering helps reviewers locate wiring quickly"
  - "Cleanup with per-step try/except: standard pattern for any `_on_close` handler that owns multiple resources; matches the `getattr(self, '_resource', None)` defensive lookup in case a resource was never constructed (e.g., headless test fixtures)"

requirements-completed: [LIVE-01, LIVE-05, LIVE-09]

# Metrics
duration: ~12min
completed: 2026-04-27
---

# Phase 03 Plan 06: LiveGamePanel + App Wiring Summary

**Wires Phase 3 end-to-end: passive 4-zone LiveGamePanel reachable from home menu and via 4 Ctrl+Shift+{R,O,D,H} global hotkeys; auto-deck-detection runs at game start; close-path cleanup ordered hotkeys → presenter → tracker → db → Destroy with per-step continue-on-failure (regression-locked by 2 new navigation tests). Manual NVDA/JAWS smoke checklist deferred to HUMAN-UAT.**

## Performance

- **Duration:** ~12 min (Tasks 1+2 only; Task 3 deferred to HUMAN-UAT)
- **Started:** 2026-04-26T23:55:47Z (commit 0e9290d)
- **Completed:** 2026-04-27T00:03:31Z (commit d6dcb75)
- **Tasks:** 2 of 3 executed (Task 3 manual checkpoint deferred to HUMAN-UAT per orchestrator routing)
- **Files modified:** 5 (1 home presenter, 1 app composition root, 1 view module + 1 format module created, 2 test files extended) + 1 deferred-items append

## Accomplishments

**Task 1 — LiveGamePanel + format helpers + home menu (TDD: RED `0e9290d` → GREEN `95516fd`)**

- Extended `MENU_ITEMS` in `stonereader/presenters/home.py` from 3 to 4 entries; "Live Game" is the new 4th entry per UI-SPEC layout contract.
- Created `stonereader/views/_live_game_format.py` (47 lines) with 4 row-format helpers:
  - `format_remaining_deck_row(card, count)` — `"<name> (<cost> mana) — <count>"`
  - `format_opponent_hand_row(row)` — `"Pos N: <identity|?> (gen: <lineage>) — drawn turn N|?"` with `?` fallback for `drawn_turn == -1` and missing identity
  - `format_opponent_played_row(pc)` — `"Turn N — <name>"`
  - `format_cards_drawn_row(pc)` — `"Turn N — <name> (drawn)"` (LIVE-03 zone)
- Created `stonereader/views/live_game.py` (263 lines) with passive `LiveGamePanel(wx.Panel)`:
  - Top-down `wx.BoxSizer(wx.VERTICAL)` layout: title StaticText → mana StaticText → ("Remaining Deck:" label + `_RemainingDeckListCtrl`) → ("Opponent Hand:" label + `_OpponentHandListCtrl`) → ("Opponent Played:" label + `_OpponentPlayedListCtrl`) → ("Cards Drawn:" label + `_CardsDrawnListCtrl`).
  - All 4 `_*ListCtrl` classes are virtual (`wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER`), override `AcceptsFocus() -> False`, and delegate `OnGetItemText` to the corresponding format helper.
  - Wires `presenter.set_on_state_changed(self._on_state_changed)` and `presenter.set_on_title_changed(self._on_title_changed)`.
  - Initial render uses ONLY public accessors: `presenter.current_title()`, `presenter.cursor_for_zone(zone)`, `presenter.current_mana_summary()`, `presenter.get_zone_items(zone)` (per 03-REVIEWS.md HIGH #3).
  - Cursor preservation per Pitfall 3: `Select(max(0, min(presenter.cursor_for_zone(zone), len(rows) - 1)))`.
- Extended `tests/test_home.py` with `test_menu_items_includes_live_game` (regression-locks the 4-item shape) and updated existing tests to expect 4 items / Live Game as 4th entry.

**Task 2 — App wiring + close cleanup (TDD: RED `f82641f` → GREEN `5d0233d`)**

- Inserted `# --- Live Game ---` block in `StoneReaderApp.OnInit` between existing `# --- Import Deck ---` and home-menu wiring:
  ```python
  live_presenter = LiveGamePresenter(speech, db_conn, self._tracker, card_db)
  live_panel = LiveGamePanel(self._frame, live_presenter)
  nav.register_panel("Live Game", live_panel, live_presenter, live_panel)
  self._frame._live_presenter = live_presenter
  ```
- Replaced single-line home-menu select callback with named `_on_home_select(name)` that special-cases `"Live Game"` to chain `nav.show_panel(name)` with `live_presenter.jump_to_zone("remaining_deck")` — menu-entry speech matches Ctrl+Shift+R browse-open speech (D-17 zone-entry consistency).
- Inserted `# --- Global hotkeys (LIVE-09) ---` block AFTER `self._frame.Show()` and BEFORE `self._tracker.start(parent=self._frame)`:
  - `self._hotkeys = GlobalHotkeyService(self._frame)`
  - 4 register() calls for `Ctrl+Shift+R` (Remaining Deck browse-open), `Ctrl+Shift+O` (Opponent Hand browse-open), `Ctrl+Shift+D` (Deck Counts speak-only), `Ctrl+Shift+H` (Opponent Hand Count speak-only).
  - `Ctrl+Shift+H` callback delegates to `live_presenter.announce_opponent_hand_count()` per 03-REVIEWS.md HIGH #3 — NO app-side state read.
  - Conflict-UX announcement: `if self._hotkeys.failed: speech.speak("Could not register hotkeys: " + ", ".join(self._hotkeys.failed) + ".")` (Pitfall 4).
- Extended `MainWindow._on_close` with per-step try/except continue-on-failure ordering per 03-REVIEWS.md MEDIUM 03-06 #5:
  1. `hotkeys.clear_all()` (try/except + `log.exception("hotkeys.clear_all() failed; continuing cleanup")`)
  2. `live_presenter.cleanup()` (try/except + `log.exception("live_presenter.cleanup() failed; continuing cleanup")`)
  3. `tracker.stop()` (try/except + `log.exception("tracker.stop() failed; continuing cleanup")`)
  4. `self._db_conn.close()` (try/except + `log.exception("db_conn.close() failed; continuing cleanup")`)
  5. `self.Destroy()` (always runs)
- Each cleanup step uses `getattr(self, "_<resource>", None)` defensive lookup so a never-constructed resource (headless tests) is silently skipped.
- Added 2 integration tests in `tests/test_navigation.py`:
  - `test_close_cleans_hotkeys` — regression-locks `["hotkeys", "presenter", "tracker"]` call ordering using FakeHotkeys/FakePresenter/FakeTracker stubs and `monkeypatch.setattr(frame, "Destroy", ...)`.
  - `test_close_continues_on_failure` — injects RaisingHotkeys/RaisingPresenter/RaisingTracker/RaisingDb (all raise in `clear_all`/`cleanup`/`stop`/`close`); asserts all 4 steps were attempted (`steps_attempted == ["hotkeys", "presenter", "tracker", "db"]`), Destroy still ran, and 4 distinct `log.exception` records were emitted with the matching "<step>() failed" messages.

**Task 3 — Manual NVDA/JAWS smoke test (DEFERRED to HUMAN-UAT)**

- Plan defines 20 manual verification steps: 12 functional smoke checks (A1–A12) + 8 NVDA accessibility checks (B1–B8) covering tab order, NVDA object navigation, label-to-control association, reading order, arrow-key navigation, number-key zone switching, "report current line", and browse-mode list traversal.
- Per user's approved checkpoint decision ("Persist as HUMAN-UAT.md, mark plan complete"): the orchestrator's `verify_phase_goal` step will persist the A1–A12 + B1–B8 checklist as `.planning/phases/03-live-game-tracking/HUMAN-UAT.md` for the user to execute on a Windows + NVDA/JAWS dev box. **This plan is marked complete now so the orchestrator can proceed to verification.**
- Critical-failure escalation path documented in the plan: if B1 (Tab focus on ListCtrl), B3 (NVDA fails to associate StaticText label with ListCtrl), B4 (reading order jumbled), or A8 (silent conflict UX) fail, file a gap-closure plan via `/gsd-plan-phase --gaps`.

## Task Commits

Each task was committed atomically. All 5 commits visible in `git log`:

1. **Task 1 RED — failing test for Live Game menu item** — `0e9290d` (test)
2. **Task 1 GREEN — LiveGamePanel + format helpers + Live Game home menu** — `95516fd` (feat)
3. **Task 2 RED — failing close-cleanup tests (hotkeys + presenter + continue-on-failure)** — `f82641f` (test)
4. **Task 2 GREEN — wire LiveGamePresenter + LiveGamePanel + GlobalHotkeyService into OnInit** — `5d0233d` (feat)
5. **Deviation log — D-DEFER-02 pre-existing ruff F401 warnings** — `d6dcb75` (docs)

**Plan metadata commit (this SUMMARY + STATE + ROADMAP + REQUIREMENTS):** added by the final commit step below.

_TDD gate sequence verified: Task 1 RED (`0e9290d`) precedes Task 1 GREEN (`95516fd`); Task 2 RED (`f82641f`) precedes Task 2 GREEN (`5d0233d`). No REFACTOR commit was needed — both GREEN implementations matched the plan's literal `<action>` Python source exactly._

## Files Created/Modified

- `stonereader/views/_live_game_format.py` — Created. 47 lines. 4 row-format helpers (`format_remaining_deck_row`, `format_opponent_hand_row`, `format_opponent_played_row`, `format_cards_drawn_row`). Module docstring documents centralization rationale per 03-REVIEWS.md MEDIUM 03-06 #1.
- `stonereader/views/live_game.py` — Created. 263 lines. `LiveGamePanel(wx.Panel)` + 4 virtual `_*ListCtrl` classes. Imports `format_*_row` helpers. NEVER imports `SpeechService`. Uses ONLY public presenter accessors (no private-field access).
- `stonereader/presenters/home.py` — Modified. 1 line. `MENU_ITEMS` extended from 3 to 4 entries with "Live Game" as 4th.
- `stonereader/app.py` — Modified. 84 insertions / 6 deletions. New `# --- Live Game ---` and `# --- Global hotkeys (LIVE-09) ---` blocks; extended `_on_home_select` callback for "Live Game" zone-jump; extended `_on_close` with per-step try/except continue-on-failure ordering.
- `tests/test_home.py` — Modified. 23 insertions / 6 deletions. New `test_menu_items_includes_live_game`; updated existing tests to expect 4 items.
- `tests/test_navigation.py` — Modified. 115 insertions. New `test_close_cleans_hotkeys` and `test_close_continues_on_failure`.
- `.planning/phases/03-live-game-tracking/deferred-items.md` — Modified. 25 insertions. D-DEFER-02 logged for pre-existing ruff F401 warnings in unrelated test files.
- `.planning/phases/03-live-game-tracking/03-06-SUMMARY.md` — Created (this file).

## Decisions Made

- **Task 3 (manual NVDA/JAWS smoke test) deferred to HUMAN-UAT.** Per user's approved checkpoint decision ("Persist as HUMAN-UAT.md, mark plan complete"): the orchestrator's `verify_phase_goal` step will persist the A1–A12 + B1–B8 checklist as `.planning/phases/03-live-game-tracking/HUMAN-UAT.md`. Marking plan complete now so orchestrator can proceed to verification. The functional and accessibility checks remain mandatory — they're just owned by the UAT step rather than the executor.
- **Public-accessor-only enforcement.** Throughout Tasks 1 and 2, the view module, app composition root, and new tests use ONLY `presenter.current_title()` / `presenter.cursor_for_zone(zone)` / `presenter.current_mana_summary()` / `presenter.get_zone_items(zone)` / `presenter.announce_opponent_hand_count()` etc. (per 03-REVIEWS.md HIGH #3). `grep -c "_zone_cursors\|_format_title\|_current_state" stonereader/views/live_game.py stonereader/app.py` — both files are 0 hits in production paths.
- **Defensive `getattr(self, "_<resource>", None)` lookups in `_on_close`.** Plan instructed `getattr(self, "_hotkeys", None)` / `getattr(self, "_live_presenter", None)` / `getattr(self, "_tracker", None)` so a MainWindow constructed in a headless test (without OnInit running) does NOT raise AttributeError on close. Tests inject the resources via direct `frame._hotkeys = FakeHotkeys()` etc. assignments.
- **Format helpers in a SEPARATE module rather than inside `live_game.py`.** Keeps the view file focused on widget construction (~263 lines vs ~310 if inlined), and makes helpers trivially importable from future tests without instantiating wx widgets.

## Deviations from Plan

### Auto-fixed Issues

None of the Rules 1/2/3 deviations were applied during Tasks 1 or 2 — both task `<action>` blocks were specified at line-by-line precision (literal Python source for both implementation and tests) and execution matched exactly.

### Pre-existing issues (out of scope, logged but not fixed)

**1. [Out of scope - Pre-existing] D-DEFER-02 — ruff F401 unused-import warnings in unrelated test files**
- **Found during:** Task 2 final verification (`uv run ruff check stonereader/ tests/`).
- **Issue:** 6 ruff F401 errors across 4 test files NOT modified in 03-06: `tests/test_deck_manager.py:7,9` (`get_all_decks`, `DeckSummary`), `tests/test_services/test_events.py:6` (`pytest`), `tests/test_services/test_log_config.py:62,63` (`stat`, `MagicMock`), `tests/test_services/test_parser.py:6` (`pytest`).
- **Why pre-existing:** Last touched in `e0e7a1b feat(03-02)`, `5901b33 fix(02)`, `d8af4ae chore: merge executor worktree (02-04 data layer)` — all before plan 03-06.
- **Action taken:** Logged as D-DEFER-02 in `.planning/phases/03-live-game-tracking/deferred-items.md` with file:line list, last-touched commits, and recommended fix (`uv run ruff check --fix tests/`). Not fixed in this plan per Scope Boundary rule.
- **Files modified:** `.planning/phases/03-live-game-tracking/deferred-items.md` (appended).
- **Verification:** Files I created/modified pass ruff: `uv run ruff check stonereader/views/live_game.py stonereader/views/_live_game_format.py stonereader/presenters/home.py stonereader/app.py tests/test_home.py tests/test_navigation.py` exits 0.
- **Committed in:** `d6dcb75` (docs deferred-items).

**2. [Out of scope - Pre-existing] D-DEFER-01 (re-confirmed) — wx test-ordering fragility**
- **Found during:** Task 2 full-suite verification (`uv run pytest tests/`).
- **Issue:** Same wx test-ordering fragility logged in plan 03-04's D-DEFER-01: when any test that constructs `wx.App()` runs before `tests/test_navigation.py` in the same pytest session, ~29 navigation tests fail; in isolation each passes. The two new tests added in Task 2 (`test_close_cleans_hotkeys` and `test_close_continues_on_failure`) inherit this property.
- **Why pre-existing:** Documented in `deferred-items.md` D-DEFER-01 from plan 03-04 with reproduction commands. Not caused by 03-06; the new tests merely add more wx-using tests to the session.
- **Action taken:** No new entry — D-DEFER-01 already covers this case. Recommended fix (session-scoped `wx.App` fixture in `tests/conftest.py`) is owned by a future test-infrastructure plan.
- **Targeted verification:** `uv run pytest tests/test_navigation.py -q` → 33/33 passed; `uv run pytest tests/test_home.py -q` → 11/11 passed; `uv run pytest tests/test_navigation.py tests/test_home.py tests/test_global_hotkey.py tests/test_live_game_presenter.py -q` → 68/68 passed.
- **Workaround:** Run `tests/test_navigation.py` first in any session that touches wx-using suites.

---

**Total deviations:** 0 auto-fixes (Rules 1-3 did not trigger). 1 newly logged pre-existing issue (D-DEFER-02). 1 re-confirmation of D-DEFER-01 from plan 03-04.
**Impact on plan:** None — execution matched the plan's `<action>` blocks line-for-line. Both deferred items are explicitly out of scope per the Scope Boundary rule and are owned by a future test-infrastructure plan.

## Issues Encountered

- The full-suite `uv run pytest tests/` reports failures whose count depends on test-execution order — D-DEFER-01 fragility from plan 03-04. Targeted verification per file confirms all plan-06 acceptance criteria pass:
  - `tests/test_navigation.py -q` → 33/33 green
  - `tests/test_home.py -q` → 11/11 green
  - `tests/test_navigation.py tests/test_home.py tests/test_global_hotkey.py tests/test_live_game_presenter.py -q` → 68/68 green (covers plan 03-04, 03-05, 03-06 directly)
  - With navigation first: 276 of 283 pass (the 7 failures are all in `tests/test_input_layer.py` and exhibit the same wx-ordering fragility — pre-existing per D-DEFER-01).

## Known Stubs

None. The wired surface is fully functional:
- `LiveGamePanel` re-renders all 4 zones from real presenter data on `_on_state_changed`; mana StaticText updates from `presenter.current_mana_summary()`; title StaticText updates from `presenter.set_on_title_changed`.
- All 4 global hotkey callbacks delegate to public presenter methods (`announce_deck_counts`, `announce_opponent_hand_count`, `jump_to_zone`).
- The `_on_home_select` callback chains `nav.show_panel` + `jump_to_zone("remaining_deck")` for the menu entry.
- Close-path cleanup runs all 4 resource teardowns + Destroy.

The only "stub" in the user-facing surface is the manual NVDA/JAWS smoke test (Task 3), explicitly deferred to HUMAN-UAT per the user's approved checkpoint decision.

## Threat Flags

No new threat surface beyond the plan's `<threat_model>` register. All 5 STRIDE entries are mitigated:

- **T-03-WIRE-01** (stale OS hotkey registration): mitigated by `_on_close` calling `clear_all()` before `Destroy()`. `test_close_cleans_hotkeys` regression-locks ordering. Process exit also auto-cleans.
- **T-03-WIRE-02** (callback raise breaks dispatch): inherited from `GlobalHotkeyService._on_hotkey` exception isolation (Phase 2 Pitfall 3, locked in plan 03-04 by `test_callback_exception_isolation`).
- **T-03-WIRE-03** (silent conflict UX): mitigated by Pitfall 4 — `if self._hotkeys.failed: speech.speak("Could not register hotkeys: ...")` at startup. Manual checklist step A8 verifies (deferred to HUMAN-UAT).
- **T-03-WIRE-04** (held-key flood): inherited from `GlobalHotkeyService` MOD_NOREPEAT default OR'ing (locked in plan 03-04 by `test_register_applies_norepeat`). Manual checklist step A7 verifies (deferred to HUMAN-UAT).
- **T-03-WIRE-05** (cleanup raise prevents later cleanup steps): mitigated by per-step try/except in `_on_close`. `test_close_continues_on_failure` regression-locks all 4 steps.

ASVS L1: V14 (configuration) covered. No `high`-severity threats.

## User Setup Required

None at the code level — no new dependencies, config files, env vars, or external services. The 4 Ctrl+Shift+{R,O,D,H} chords register at app startup via `GlobalHotkeyService.register()`; the user only needs to launch the app.

**HUMAN-UAT pending:** the manual NVDA/JAWS smoke test (A1–A12 + B1–B8) requires a Windows + Hearthstone + NVDA/JAWS test box. Orchestrator's `verify_phase_goal` step will persist the checklist as `.planning/phases/03-live-game-tracking/HUMAN-UAT.md`.

## TDD Gate Compliance

Both Task 1 and Task 2 followed strict RED → GREEN → (no REFACTOR needed):

- **Task 1 RED gate:** `0e9290d test(03-06): add failing tests for Live Game menu item` — `tests/test_home.py` extended with `test_menu_items_includes_live_game` expecting 4 entries; pytest run shows the test failing because `MENU_ITEMS` still has 3 entries.
- **Task 1 GREEN gate:** `95516fd feat(03-06): add LiveGamePanel view + format helpers + Live Game home menu` — `MENU_ITEMS` extended; `_live_game_format.py` and `live_game.py` created; the failing test now passes.
- **Task 2 RED gate:** `f82641f test(03-06): add failing close-cleanup tests (hotkeys + presenter + continue-on-failure)` — `tests/test_navigation.py` extended with both tests; they fail because `_on_close` does not yet call `clear_all`/`cleanup` and lacks per-step try/except.
- **Task 2 GREEN gate:** `5d0233d feat(03-06): wire LiveGamePresenter + LiveGamePanel + GlobalHotkeyService into OnInit` — extended `_on_close` with the documented ordering and per-step try/except; both new tests now pass.
- **REFACTOR gate:** intentionally skipped both times — implementations matched plan's literal `<action>` Python source.

## Next Phase Readiness

- **Phase 3 user-facing surface complete (pending HUMAN-UAT):** Screen reader users can press a global hotkey while Hearthstone has focus and hear remaining deck / opponent hand inspection / cards drawn / opponent hand count / deck counts through their screen reader. Navigation-by-zone via 1/2/3/4 keys works in the panel; D-17 zone-entry speech consistent across menu entry, hotkey browse-open, and number-key zone switch.
- **Manual NVDA/JAWS validation owed:** orchestrator persists A1–A12 + B1–B8 as `HUMAN-UAT.md`. If any critical step (B1, B3, B4, A8) fails, file `/gsd-plan-phase --gaps` to insert a gap-closure plan for the specific accessibility regression.
- **Phase 4 (Replay Viewer) readiness:** the wx-free presenter + view contract pattern established here transfers cleanly — replay panels can subclass the same `set_on_state_changed` / public-accessor / virtual-ListCtrl approach with a ReplayEngine-driven event stream replacing GameTracker.
- **Plan 03-06 acceptance criteria:** all met. See "Self-Check: PASSED" below.

## Self-Check: PASSED

Verified files and commits exist on disk and in git history:

- `stonereader/views/_live_game_format.py` — FOUND (4 helpers: `format_remaining_deck_row`, `format_opponent_hand_row`, `format_opponent_played_row`, `format_cards_drawn_row`)
- `stonereader/views/live_game.py` — FOUND (`class LiveGamePanel(wx.Panel)` + 4 virtual `_*ListCtrl` classes; imports format helpers; no SpeechService import; no private-field access)
- `stonereader/presenters/home.py` — FOUND with `MENU_ITEMS = ["Card Library", "Deck Manager", "Import Deck", "Live Game"]`
- `stonereader/app.py` — FOUND with new `# --- Live Game ---` block + `# --- Global hotkeys (LIVE-09) ---` block + extended `_on_close` with per-step try/except
- `tests/test_home.py` — FOUND with `test_menu_items_includes_live_game`
- `tests/test_navigation.py` — FOUND with `test_close_cleans_hotkeys` and `test_close_continues_on_failure`
- `.planning/phases/03-live-game-tracking/deferred-items.md` — FOUND with D-DEFER-02 entry
- `.planning/phases/03-live-game-tracking/03-06-SUMMARY.md` — FOUND (this file)

Commits in git history (`git log --oneline`):
- `0e9290d test(03-06): add failing tests for Live Game menu item` — FOUND
- `95516fd feat(03-06): add LiveGamePanel view + format helpers + Live Game home menu` — FOUND
- `f82641f test(03-06): add failing close-cleanup tests (hotkeys + presenter + continue-on-failure)` — FOUND
- `5d0233d feat(03-06): wire LiveGamePresenter + LiveGamePanel + GlobalHotkeyService into OnInit` — FOUND
- `d6dcb75 docs(03-06): log D-DEFER-02 pre-existing ruff F401 warnings as deferred` — FOUND

Targeted test verification:
- `uv run pytest tests/test_navigation.py -q` → 33/33 passed
- `uv run pytest tests/test_home.py -q` → 11/11 passed
- `uv run pytest tests/test_navigation.py tests/test_home.py tests/test_global_hotkey.py tests/test_live_game_presenter.py -q` → 68/68 passed
- Run with navigation first: 276 / 283 passed (7 pre-existing wx-ordering failures in `tests/test_input_layer.py` per D-DEFER-01)

---
*Phase: 03-live-game-tracking*
*Completed: 2026-04-27*
