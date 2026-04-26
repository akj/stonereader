---
phase: 02-log-infrastructure
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 31
files_reviewed_list:
  - pyproject.toml
  - stonereader/__main__.py
  - stonereader/app.py
  - stonereader/models/game_state.py
  - stonereader/services/__init__.py
  - stonereader/services/_engine.py
  - stonereader/services/_events.py
  - stonereader/services/_exceptions.py
  - stonereader/services/_line_reader.py
  - stonereader/services/_log_config.py
  - stonereader/services/_log_path.py
  - stonereader/services/_logging_config.py
  - stonereader/services/_packets.py
  - stonereader/services/_parser.py
  - stonereader/services/_process_detect.py
  - stonereader/services/_tracker.py
  - stonereader/services/_watcher.py
  - tests/test_services/conftest.py
  - tests/test_services/test_engine.py
  - tests/test_services/test_events.py
  - tests/test_services/test_exceptions_packets.py
  - tests/test_services/test_game_state_extension.py
  - tests/test_services/test_line_reader.py
  - tests/test_services/test_log_config.py
  - tests/test_services/test_log_path.py
  - tests/test_services/test_logging_config.py
  - tests/test_services/test_parser.py
  - tests/test_services/test_process_detect.py
  - tests/test_services/test_tracker.py
  - tests/test_services/test_watcher.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-25
**Depth:** standard
**Files Reviewed:** 31
**Status:** issues_found

## Summary

Phase 2 delivers the full log-infrastructure stack: `_logging_config`, `_log_config`, `_log_path`, `_line_reader`, `_parser`, `_packets`, `_engine`, `_tracker`, `_watcher`, and the `GameState` extension. The architecture is well-designed — the D-10 hslog isolation boundary holds, the broad-exception resilience pattern is applied consistently and intentionally, and the test coverage is solid across all modules.

Three warnings require attention before Phase 3 builds on top of this layer:

1. `_game_started_emitted` is set but never checked — `GameStarted` can be emitted more than once per logical game if the log contains two `CREATE_GAME` blocks without a process restart.
2. `_friendly_player_id` is hardcoded to `1` and is never updated from observed `CONTROLLER` tags. The comment promises refinement but the refinement was never implemented, causing player-vs-opponent classification to be incorrect for the player who draws first (player 2 in Hearthstone's entity numbering).
3. `ensure_log_config` has no exception handling around the file write — a `PermissionError` or `OSError` (e.g., read-only filesystem, full disk) propagates to the caller uncaught; the caller in `app.py` does wrap it, but the function itself advertises no such requirement.

Four info items are noted for future cleanup.

## Warnings

### WR-01: `_game_started_emitted` flag is set but never read as a guard

**File:** `stonereader/services/_engine.py:74,188`
**Issue:** `_game_started_emitted` is initialized to `False`, set to `True` after emitting `GameStarted`, and reset on `reset()`. However, `_on_create_game` is called every time a `CreateGamePacket` arrives and always emits `GameStarted` unconditionally — the flag is never checked before emitting. If Hearthstone writes a second `CREATE_GAME` block within the same session (e.g., reconnect to an in-progress game, which does happen), `GameStarted` will be emitted twice to subscribers.

The `_game_ended_emitted` flag (line 326-328) is checked with `if not self._game_ended_emitted` before emitting — the same guard is missing for `_game_started_emitted`.

**Fix:**
```python
def _on_create_game(self, p: CreateGamePacket) -> List[GameEvent]:
    self.reset()
    # ... existing init code ...
    if not self._game_started_emitted:
        self._game_started_emitted = True
        return [GameStarted(...)]
    return []
```
Note: `reset()` is called at the top of `_on_create_game`, so `_game_started_emitted` will always be `False` at that point after a reset — this guard would only help if emitting `GameStarted` is desired only on the *first* `CREATE_GAME` seen after initialization. If the intent is to emit on every `CREATE_GAME` (re-emit on reconnect), the flag and its reset-clearing should both be removed to avoid confusion.

---

### WR-02: `_friendly_player_id` is always `1` — never refined from CONTROLLER observation

**File:** `stonereader/services/_engine.py:77-78`
**Issue:** The comment says `# Default friendly player_id is 1 (refined when CONTROLLER on hero is observed)` but there is no code anywhere in `_engine.py` that actually refines `_friendly_player_id`. The value stays `1` for the entire game.

In Hearthstone, "player 1" and "player 2" are assigned by server order (coin flip), not by who is the local player. When the local player is assigned entity 2, all card-drawn, card-played, and playstate discrimination (`controller == self._friendly_player_id`) will treat the local player's cards as the opponent's and vice versa — silently producing inverted event payloads for half of all games.

**Fix:** Implement the promised refinement. The standard approach (used by HDT and Firestone) is to observe the `CONTROLLER` tag on the local player's hero entity and use that player ID as the friendly one. The local player can be identified from the `PLAYER_ID` of the entity whose name matches the logged-in BattleTag (available from the `CreateGamePacket.players` tuple). A simpler heuristic: the first `CURRENT_PLAYER=1` tag change on a PLAY_ENTITY block for a card from the local player. The exact mechanism depends on what is available in Power.log, but the current stub is a known-incorrect default.

```python
# In _on_create_game or when observing initial CONTROLLER tags:
for entity_id, name, hi, lo in p.players:
    # If this player's hi/lo matches the logged-in account (or use other
    # heuristics), set _friendly_player_id = entity_id.
    pass
```

At minimum, add a test that plays through a game where the local player is entity 2 and assert that `CardDrawn.controller == 1` for that player's cards.

---

### WR-03: `ensure_log_config` propagates `OSError`/`PermissionError` without documentation

**File:** `stonereader/services/_log_config.py:41-70`
**Issue:** The write path (`path.open("w", ...)` at line 67) has no exception handling. A `PermissionError` (e.g., the Hearthstone directory is owned by another user or is on a locked network share) or a disk-full `OSError` will propagate to the caller as an unhandled exception. The caller in `app.py` (line 380-388) does wrap the call in a broad `except Exception`, so the application will not crash, but `ensure_log_config`'s docstring claims "idempotently ensures" without documenting this failure mode.

The issue is minor in practice — `app.py` handles it — but callers that use this function outside `app.py` (e.g., in tests or a future CLI) would get an unexpected exception. The `mkdir(parents=True, exist_ok=True)` at line 50 can also raise `PermissionError` on non-Windows test runners.

**Fix:** Wrap the write with explicit error handling and either re-raise as `ServicesError` or document the exception in the docstring:
```python
try:
    with path.open("w", encoding="utf-8") as f:
        parser.write(f)
except OSError as exc:
    logger.error("Failed to write log.config at %s: %s", path, exc)
    raise ServicesError(f"Cannot write log.config: {exc}") from exc
```

---

## Info

### IN-01: `_ = GameEntity` suppression pattern is fragile dead code

**File:** `stonereader/services/_engine.py:424`
**Issue:** `GameEntity` is imported at line 13 but only used in a comment at line 158. The `_ = GameEntity` sentinel at the bottom suppresses linter "unused import" warnings but `GameEntity` is not exported in `services/__init__.py.__all__` and is not needed by the engine for any runtime purpose. The comment says "re-exported via type hints" but that re-export does not exist.

**Fix:** Either remove the import (and the sentinel) if `GameEntity` is not needed by the engine, or add it to `__all__` in `services/__init__.py` if it is intentionally exposed for Phase 3 consumers.

---

### IN-02: `GameTracker.start()` missing type annotation on `parent` parameter

**File:** `stonereader/services/_tracker.py:69`
**Issue:** `def start(self, parent) -> None:` has no type annotation on `parent`. The corresponding `PowerLogWatcher.start()` at `_watcher.py:46` annotates it as `"wx.EvtHandler"` (forward-ref string). The tracker should match.

**Fix:**
```python
def start(self, parent: "wx.EvtHandler") -> None:
```
This requires adding `import wx` under `TYPE_CHECKING` to avoid a hard wx dependency in the module at import time:
```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import wx
```

---

### IN-03: `_parser.py` accesses `_parsing_state` — a private hslog attribute

**File:** `stonereader/services/_parser.py:89`
**Issue:** `self._hslog._parsing_state.packet_tree` accesses a private attribute of the hslog `LogParser`. The existing `AttributeError` guard at lines 90-92 (`except AttributeError: return []`) handles version drift, but the approach is fragile. If hslog renames or restructures `_parsing_state` the parser silently returns no packets for every line — the watcher keeps running, the tracker receives nothing, and the user sees no error.

The `AttributeError` soft-fail is the right behavior per D-04, but there is no log warning when it fires. A first-time silent fallback could be promoted to a one-time warning (similar to `_missing_enums_logged`) to make version drift detectable.

**Fix:** Add a one-time warning log when the `AttributeError` fires:
```python
try:
    tree = self._hslog._parsing_state.packet_tree
except AttributeError:
    if not hasattr(self, "_parsing_state_warned"):
        self._parsing_state_warned = True
        logger.warning("hslog._parsing_state unavailable — parser disabled (version mismatch?)")
    return []
```

---

### IN-04: `test_engine.py` fixture-dependent tests skip silently — no coverage baseline

**File:** `tests/test_services/test_engine.py:38-87`
**Issue:** Three of the four engine tests (`test_mid_game_fixture_emits_expected_events`, `test_dual_source_fixture_no_duplicates`, `test_tick_under_50ms`) call `power_log_fixture("mid_game.log")` which calls `pytest.skip()` if the fixture is absent. With no fixture captured yet (per the `conftest.py` comment "Wave 5 task"), the engine's core event-emission logic has zero test coverage from synthetic packets beyond `test_emits_frozen_gamestate_snapshots`.

The logic in `_handle_zone_change`, `_handle_playstate`, `_on_block_start`, `_on_show_entity`, and `_on_hide_entity` is entirely untested by synthetic packet sequences. WR-01 and WR-02 above are undetected by the current test suite for exactly this reason.

**Fix:** Add at minimum one synthetic-packet engine test that feeds a `TagChangePacket(tag="ZONE", ...)` sequence and asserts `CardDrawn` is emitted with the correct `controller`. This would have caught WR-02. The fixture-based tests are valuable for integration coverage but should not be the only engine tests.

---

_Reviewed: 2026-04-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
