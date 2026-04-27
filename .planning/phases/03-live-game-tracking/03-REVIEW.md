---
phase: 03-live-game-tracking
reviewed: 2026-04-26T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - stonereader/app.py
  - stonereader/models/game_state.py
  - stonereader/presenters/home.py
  - stonereader/presenters/live_game.py
  - stonereader/services/_engine.py
  - stonereader/services/_global_hotkey.py
  - stonereader/services/_packets.py
  - stonereader/services/_parser.py
  - stonereader/views/_live_game_format.py
  - stonereader/views/live_game.py
  - tests/conftest.py
  - tests/test_global_hotkey.py
  - tests/test_home.py
  - tests/test_live_game_presenter.py
  - tests/test_navigation.py
  - tests/test_services/test_engine.py
  - tests/test_services/test_engine_friendly_player.py
  - tests/test_services/test_engine_lineage.py
  - tests/test_services/test_parser.py
findings:
  critical: 0
  warning: 2
  info: 6
  total: 8
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-26
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 3 (`live-game-tracking`) implements the GlobalHotkeyService Win32 wrapper, the four-zone LiveGamePresenter, the passive LiveGamePanel view, the engine improvements (WR-02 friendly_player resolution, D-19 creation lineage, and opponent_hand reconstruction), plus the home-menu and `app.py` wiring. The implementation follows the documented invariants well:

- **MVP discipline:** confirmed — `views/live_game.py` does not import `SpeechService` and only consumes public presenter accessors (`current_title`, `cursor_for_zone`, `current_mana_summary`, `get_zone_items`).
- **Frozen-dataclass discipline:** all state mutations in `_engine.py` go through `dataclasses.replace`; `GameEntity` / `GameState` / `Hero` / `PlayedCard` are all `@dataclass(frozen=True)`.
- **Engine boundary:** `services/_engine.py` does not import `hslog` (only `hearthstone.enums` for the public enum values, which is a separate library and is allowed).
- **Wx-free presenter:** `presenters/live_game.py` does not import `wx`.
- **D-07 invariant:** `LiveGamePresenter._on_game_event` does not call `self._speech.speak`; speech only happens via user-driven entrypoints.
- **Cleanup ordering:** `MainWindow._on_close` wraps every step in its own `try/except`, exactly matching the test contract in `test_close_continues_on_failure`.
- **Hotkey isolation:** `GlobalHotkeyService._on_hotkey` catches and logs callback exceptions, isolating one bad chord from the others (Pitfall 3 / `test_callback_exception_isolation`).
- **Sticky lineage:** `_record_entity` sets `creation_lineage` only when the key is absent (`"creation_lineage" not in ent`), so subsequent `TAG_CHANGE` / `SHOW_ENTITY` cannot overwrite it (covered by `test_show_entity_after_lineage`).

Two warnings were found, both in the global-hotkey integration in `app.py`. Six info-level items document smaller improvements.

## Warnings

### WR-01: Global hotkey re-entry duplicates the navigation stack entry for "Live Game"

**File:** `stonereader/app.py:542-548`
**Issue:** Both `_open_remaining_deck` and `_open_opponent_hand` call `nav.show_panel("Live Game")` unconditionally before `live_presenter.jump_to_zone(...)`. `NavigationController.show_panel` always appends the panel name to `_stack` for non-transient panels (lines 90-91), with no guard for "already visible." Pressing a global hotkey while the Live Game panel is already on screen therefore appends a second `"Live Game"` entry to the stack on every press. After N presses the stack contains N+1 copies of `"Live Game"`, and the user has to press Escape/Back N times to return to Home. This affects the LIVE-09 hotkey contract because the same chord is documented as both "open the panel" and "jump to a zone within it."

**Fix:** Either (a) make `show_panel` idempotent for the currently-visible panel:

```python
def show_panel(self, name: str) -> None:
    if self._current_visible == name:
        # Already visible — re-activate keymap + focus, but do not stack-push.
        self._activate_keymap_and_focus(name)
        return
    ...existing body...
```

or (b) guard at the hotkey callsite:

```python
def _open_remaining_deck() -> None:
    if nav.current_panel_name != "Live Game":
        nav.show_panel("Live Game")
    live_presenter.jump_to_zone("remaining_deck")
```

Option (a) is preferable because it also fixes the equivalent footgun for any future hotkey or programmatic navigation.

### WR-02: `LiveGamePresenter.jump_to_zone` skips `_detail_cursor` and `_orienting_counts` reset

**File:** `stonereader/presenters/live_game.py:317-329`
**Issue:** `jump_to_zone` is the dedicated entrypoint for global hotkeys and the home-menu transition into the Live Game panel. It mutates `self._current_zone` directly and re-clamps the cursor, but it does NOT reset `self._detail_cursor` or `self._orienting_counts` the way `ZoneNavigationMixin.navigate_to_zone` does (`base.py:65-66`). Consequences:
1. If the user previously read several detail lines (Down arrow) on a different zone, then triggers a global hotkey (or returns from another panel via the home menu), the next Down/Up press starts from a stale `_detail_cursor` index instead of from line 0 of the newly-focused row.
2. Diminishing-orienting-message counts (`handle_inapplicable_zone`) carry over across zone switches even though the contract is "reset on zone change" (per CLAUDE.md "Diminishing messages" pattern).

**Fix:** Mirror the reset that `navigate_to_zone` performs:

```python
def jump_to_zone(self, zone_name: str) -> None:
    label = _ZONE_LABELS.get(zone_name, zone_name)
    items = self.get_zone_items(zone_name)
    self._current_zone = zone_name
    self._detail_cursor = 0
    self._orienting_counts.clear()
    if not items:
        self._speech.speak(f"{label}: empty")
        return
    ...rest unchanged...
```

## Info

### IN-01: `app.py` reaches into `nav._panels` directly

**File:** `stonereader/app.py:324`
**Issue:** Inside `_check_clipboard_for_deckstring`, the code does `import_panel = self._nav._panels.get("Import Deck")` — direct access to a private attribute of `NavigationController`. The rest of `app.py` accesses panels through public methods (`get_presenter`, `current_panel_name`). This is a small encapsulation breach with no functional impact today, but it makes future refactors of `NavigationController._panels` (e.g., swapping the dict for a registry object) silently break this callsite.
**Fix:** Add a public accessor on `NavigationController`, e.g. `get_panel(name) -> wx.Panel | None`, and call `self._nav.get_panel("Import Deck")` here.

### IN-02: `_on_show_entity` recomputes lineage with stale `_friendly_player_id` before fallback resolution

**File:** `stonereader/services/_engine.py:526-548`
**Issue:** `_on_show_entity` calls `self._record_entity(...)` BEFORE `self._resolve_friendly_player_show_entity_fallback(p)`. `_record_entity` reads `self._friendly_player_id` to decide whether to assign `creation_lineage`. In the rare case that a SHOW_ENTITY into HAND is what triggers the multiplayer fallback (flipping friendly from default 1 to 2), the lineage check inside `_record_entity` ran with the stale value. In practice this is harmless because the fallback's triggering reveal happens during the friendly mulligan reveal (which is not inside a POWER block), so the lineage condition `self._block_stack and self._block_stack[-1] == "POWER"` is False anyway. But the order is a subtle hazard if a future log scenario combines the two.
**Fix:** Either (a) document the ordering invariant in a comment ("`_record_entity` runs before fallback resolution; the lineage check tolerates stale friendly_id because POWER blocks are not open during mulligan reveals"), or (b) flip the order so fallback resolution happens first.

### IN-03: Direct private-state access to `presenter._current_zone` in `tests/test_live_game_presenter.py`

**File:** `tests/test_live_game_presenter.py:756-762`
**Issue:** `test_number_key_zone_switching` reads `presenter._current_zone` to verify the number-key keymap fires the right zone. The rest of the suite uses public accessors (per 03-REVIEWS.md HIGH #3) and a couple of tests explicitly note when they "do read internal state." This test does not have a similar comment, which makes future `_current_zone` rename/refactor risky.
**Fix:** Either (a) add a comment matching the style in `test_detection_resets_per_game` ("This is one of the rare tests that DOES read internal state...") or (b) add a public accessor `current_zone() -> str` on the presenter and use it here.

### IN-04: `_walk` creates a `list(hslog_pkts)` on every recursion

**File:** `stonereader/services/_parser.py:110-111`
**Issue:** `_walk` calls `list(hslog_pkts)` for every block recursion to compute `is_last`. This is O(n) per recursion and is invoked on every `feed_line` call (which can be every Power.log line). For deep block trees this adds avoidable allocation per parse cycle. It is not currently a performance issue (the wider `test_tick_under_50ms` budget passes), but is something to be aware of if Power.log line throughput grows.
**Fix:** Track `is_last` via reverse iteration or by capturing `len(pkts_list) - 1` once and indexing — `pkts_list` is already materialised, so the cost is the materialisation, not the index. The current code is acceptable for v1; consider revisiting if the per-tick budget tightens.

### IN-05: `Parser` uses `self._hslog._parsing_state` (hslog private API)

**File:** `stonereader/services/_parser.py:96, 157`
**Issue:** Both `_collect_new_packets` and `_create_game_still_building` reach into `self._hslog._parsing_state`, which is a private hslog attribute. The code defensively wraps the access in `try/except AttributeError`, but the silent "soft-fail" path (`return []` / `return False`) means a hslog version bump that renames or removes `_parsing_state` will manifest as "engine seems to ignore packets" rather than a loud failure.
**Fix:** Pin the supported hslog version range in `pyproject.toml` more narrowly (e.g., `hslog>=9.17.0,<10.0`) and add a startup-time sanity check that logs a WARNING if `_parsing_state` is missing on the underlying parser.

### IN-06: `_run_auto_detection` sums `revealed.values()` after the caller already enforced 30

**File:** `stonereader/presenters/live_game.py:144-149`
**Issue:** `_on_game_event` already enforces `revealed_count >= 30` (line 137) before calling `_run_auto_detection`. Inside the method, line 148 re-checks `if sum(revealed.values()) != 30: return`. The two counts can disagree if `state.player_deck` contains entities with the same `card_id` filtered differently, but in practice both walks filter the same way (skip empty `card_id`). The defensive double-check is harmless but obscures intent.
**Fix:** Either drop the inner check (rely on the caller's guard) or replace it with an `assert` that documents the invariant. If you keep the check, change `>=` to `==` on the caller side or add a comment explaining why "revealed >= 30" can produce "values sum != 30" (e.g., reshuffle-into-deck increases `player_deck` past 30).

---

_Reviewed: 2026-04-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
