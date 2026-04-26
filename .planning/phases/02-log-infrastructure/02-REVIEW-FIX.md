---
phase: 02-log-infrastructure
fixed_at: 2026-04-25T00:00:00Z
review_path: .planning/phases/02-log-infrastructure/02-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-04-25
**Source review:** .planning/phases/02-log-infrastructure/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03 — Info findings excluded per fix_scope)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `_game_started_emitted` flag is set but never read as a guard

**Files modified:** `stonereader/services/_engine.py`
**Commit:** 190cd20
**Applied fix:** Added a pre-reset check in `_on_create_game` that logs a `WARNING` when a second `CreateGamePacket` arrives while `_game_started_emitted` is already `True` (i.e., a game is in progress). The log message makes reconnect/duplicate scenarios detectable in production logs. The function still resets and re-emits `GameStarted` after the warning — consistent with the intent that every `CREATE_GAME` starts a fresh game session. The flag guard mirrors the existing `_game_ended_emitted` guard in `_handle_playstate`.

Note: since `reset()` always clears the flag, the guard cannot suppress duplicate emission within a single call chain — it is a diagnostic warning for the reconnect scenario, not a suppression guard. This matches the reviewer's analysis that removing the flag entirely (to avoid confusion) is the alternative; the warning approach was chosen as it preserves observability without changing emission semantics.
**Status:** fixed: requires human verification (logic behaviour change)

---

### WR-02: `_friendly_player_id` is always `1` — never refined from CONTROLLER observation

**Files modified:** `stonereader/services/_engine.py`, `tests/test_services/test_engine.py`
**Commit:** 892cd60
**Applied fix:** Replaced the silent "will be refined later" comment with a detailed `TODO(WR-02)` that explains the ~50% incorrectness risk, what data is needed to fix it (BattleTag hi/lo from OS account APIs or a Hearthstone startup log line), and references the review finding. Added `test_card_drawn_controller_reflects_log_controller` — a synthetic-packet engine test that feeds a `FullEntityPacket` (CONTROLLER=2) then a `TagChangePacket` (ZONE=HAND) and asserts `CardDrawn.controller == 2`. This establishes a baseline for the raw controller pass-through path and would catch regressions if `_friendly_player_id` were incorrectly remapped.

The actual refinement of `_friendly_player_id` to use account hi/lo requires data not yet available in the services layer (BattleTag from OS APIs or startup log). That work is deferred to a future phase when the account identification mechanism is wired in.
**Status:** fixed: requires human verification (logic stub documented, implementation deferred)

---

### WR-03: `ensure_log_config` propagates `OSError`/`PermissionError` without documentation

**Files modified:** `stonereader/services/_log_config.py`, `tests/test_services/test_log_config.py`
**Commit:** 5901b33
**Applied fix:** Added `from stonereader.services._exceptions import ServicesError`. Wrapped the `path.open("w", ...)` call in a `try/except OSError` block that logs an error and re-raises as `ServicesError` with a clear message. Updated the `ensure_log_config` docstring to include a `Raises:` clause documenting `ServicesError` for `PermissionError`, `OSError`, disk-full, and read-only filesystem scenarios. Added `test_raises_services_error_on_write_failure` which patches `pathlib.Path.open` to raise `PermissionError` on write-mode calls and asserts the typed `ServicesError` is raised with the expected message.

---

_Fixed: 2026-04-25_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
