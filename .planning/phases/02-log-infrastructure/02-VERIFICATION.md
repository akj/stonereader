---
phase: 02-log-infrastructure
verified: 2026-04-25T00:00:00Z
resolved: 2026-04-26T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `uv run python -m stonereader` on a Windows machine with NVDA or JAWS installed"
    expected: "App launches, ~/.stonereader/stonereader.log contains 'GameTracker started', %LOCALAPPDATA%\\Blizzard\\Hearthstone\\log.config is created/updated with [Power] section, closing the app logs 'GameTracker stopped' with no dangling Timer, re-launch confirms idempotent (no second 'Updated log.config' message)"
    why_human: "Pitfall 9 (Timer before frame.Show race) and T-2-LIFECYCLE (orphaned Timer on close) are only observable on Windows with a real wx event loop."
    resolution: "User explicitly approved during execute-phase Wave 4 human-verify checkpoint (2026-04-26)."
  - test: "Launch StoneReader while Hearthstone is running and start a Casual match"
    expected: "stonereader.log shows tracker activity (GameState lines ingested, engine events emitted). No UI lag during match. Opponent's player class and actions are correctly attributed (player 1 vs player 2) when the local player is NOT entity 1."
    why_human: "WR-02 (_friendly_player_id hardcoded to 1) can produce inverted player/opponent event payloads for 50% of games."
    resolution: "code-review-fix run (commit `892cd60`) replaced the misleading comment with a TODO(WR-02) block documenting the misclassification risk and required data (BattleTag account hi/lo). Added baseline test `test_card_drawn_controller_reflects_log_controller` in tests/test_services/test_engine.py to lock the raw-controller pass-through behavior. Full logic fix deferred to the phase when account-id data is available — tracked in 02-HUMAN-UAT.md."
---

# Phase 2: Log Infrastructure Verification Report

**Phase Goal:** The app can reliably tail Hearthstone's Power.log and produce a clean stream of game events without blocking the UI
**Verified:** 2026-04-25
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | LogWatcher detects new lines appended to Power.log within 1 second and emits parsed events | VERIFIED | `PowerLogWatcher` polls every 150ms via `wx.Timer`. `test_appended_lines_picked_up_within_one_tick` (test_watcher.py) confirms lines appear in the same `_do_tick()` call after a write. Real fixture `mid_game.log` drives `test_mid_game_fixture_emits_expected_events` (4 PASSED). |
| 2 | PowerTaskList duplicate lines are filtered (no double-counted events) | VERIFIED | `_is_gamestate_line()` in `_watcher.py` pre-filters to `GameState.` prefix before passing to parser. `test_powertasklist_dropped_by_hslog` (test_parser.py) confirms zero packets emitted. `test_dual_source_fixture_no_duplicates` against `mid_game.log` (632 PowerTaskList lines present) confirms event counts are identical whether feeding the full fixture or a GameState-only copy. |
| 3 | Background thread runs without blocking the wxPython main thread | VERIFIED | Architecture uses `wx.Timer` (150ms) on the GUI thread — no background thread, no blocking poll, no Queue. D-19 reinterpreted as "Timer can be started and stopped cleanly; no UI freezes." Linux smoke test via `wx.CallLater(500, frame.Close)` confirmed clean start/stop lifecycle without UI freeze. `test_start_stop_clean` (test_tracker.py) confirms idempotent start/stop. |
| 4 | log.config is verified/created on startup if missing | VERIFIED | `ensure_log_config()` called in `StoneReaderApp.OnInit()` before `tracker.start()`. `test_creates_file_when_absent`, `test_preserves_other_sections`, `test_idempotent_when_correct` all pass. Linux smoke produced `Updated log.config` log line on first run; second run (idempotent) produced no log line. `[Foo]` sentinel injected survived re-launch (Pitfall 5 verified). |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `stonereader/services/__init__.py` | Package barrel re-exporting all events + GameTracker | VERIFIED | Exports 12 event types + GameTracker; `__all__` complete |
| `stonereader/services/_logging_config.py` | `configure_logging()` with RotatingFileHandler, STONEREADER_DEBUG | VERIFIED | 61 lines; RotatingFileHandler(2MB, backupCount=3), idempotent handler dedup |
| `stonereader/services/_log_config.py` | `ensure_log_config()` idempotent INI bootstrap | VERIFIED | 70 lines; RawConfigParser with optionxform=str; all 5 [Power] keys; preserves other sections |
| `stonereader/services/_log_path.py` | `discover_power_log_path()` mtime-based selection | VERIFIED | 122 lines; 4-step strategy; startswith("Hearthstone_") filter; registry fallback Windows-only |
| `stonereader/services/_process_detect.py` | `ProcessDetector` with TTL cache and clock injection | VERIFIED | 100 lines; -inf initial cache; case-insensitive match; clock: Callable injectable |
| `stonereader/services/_packets.py` | 9 frozen Packet dataclasses | VERIFIED | 93 lines; 9 frozen dataclasses; no hslog imports (D-10) |
| `stonereader/services/_exceptions.py` | `ServicesError`, `ParserError`, `EngineError` | VERIFIED | 27 lines; 3-class hierarchy |
| `stonereader/services/_parser.py` | `Parser` wrapping hslog.LogParser; D-10 isolation | VERIFIED | 245 lines; only file in services/ with hslog import; NoSuchEnum log-once cache; `reset()` creates fresh LogParser |
| `stonereader/services/_events.py` | `GameEvent` base + 10 concrete frozen event classes | VERIFIED | 12 frozen dataclasses total; all 11 required concrete events present |
| `stonereader/models/game_state.py` | Extended Hero, GameEntity; new PlayedCard; extended GameState | VERIFIED | PlayedCard added; hero_class, drawn_turn, player_played, opponent_played, player_drawn, opponent_drawn, game_state, player_starting_hand all present; no List[] types (Pitfall 4) |
| `stonereader/services/_line_reader.py` | `_LineReader` UTF-8 boundary-safe splitter | VERIFIED | 41 lines; codecs.getincrementaldecoder; reset() clears decoder AND partial buffer (Pitfall 8) |
| `stonereader/services/_engine.py` | `GameEngine` consuming Packets, emitting events, maintaining frozen GameState | VERIFIED | 424 lines; no hslog imports (D-10); no wx imports (reusable for Phase 4); 11 event types emitted per behavior table |
| `stonereader/services/_watcher.py` | `PowerLogWatcher` wx.Timer tail with backward-scan | VERIFIED | 170 lines; POLL_INTERVAL_MS=150, MAX_BUFFERED_LINES=100_000, BACKWARD_SCAN_MAX_BYTES=1_048_576; CREATE_GAME_NEEDLE; D-04 tick error containment |
| `stonereader/services/_tracker.py` | `GameTracker` facade with subscribe/unsubscribe bus | VERIFIED | 179 lines; subscriber exception isolation per Pitfall 3; process-gone reset (D-03); idempotent start/stop (D-19) |
| `stonereader/__main__.py` | `configure_logging()` called before StoneReaderApp | VERIFIED | configure_logging() on line 14, before StoneReaderApp construction; `grep -c "configure_logging" app.py` == 0 (Pitfall 10) |
| `stonereader/app.py` | GameTracker instantiated, started after frame.Show, stopped on close | VERIFIED | ensure_log_config() in OnInit; frame.Show() on line 490; tracker.start(parent=frame) on line 495 (Pitfall 9); tracker.stop() in _on_close before Destroy() |
| `tests/fixtures/log/match_start.log` | Captured Power.log fixture (match start) | VERIFIED | 630 lines, 51 KB; anonymized (no Eyeronic BattleTag); 1 CREATE_GAME |
| `tests/fixtures/log/mid_game.log` | Captured Power.log fixture (mid-game) | VERIFIED | 1568 lines, 153 KB; anonymized; 1 CREATE_GAME; 632 PowerTaskList lines for dedup test |
| `tests/fixtures/log/game_end.log` | Captured Power.log fixture (complete match) | VERIFIED | 2017 lines, 204 KB; anonymized; PLAYSTATE present |
| `tests/fixtures/log/reconnect.log` | Captured Power.log fixture (reconnect pattern) | PARTIAL | 2621 lines, 255 KB; 2 GameState CREATE_GAME blocks present; however SUMMARY documents this is two sequential matches, not a genuine force-quit + reconnect. The reconnect re-dump scenario (Pitfall 7) is not accurately represented. No test currently asserts the reconnect invariant, so no test regression occurs. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_watcher.py` | `wx.Timer` | Timer parent is wx.EvtHandler; POLL_INTERVAL_MS=150 | WIRED | `self._timer = wx.Timer(parent)` at line confirmed |
| `_watcher.py` | `_LineReader` | `_line_reader.feed(chunk)` in `_do_tick()` | WIRED | `self._line_reader.feed(chunk)` present |
| `_parser.py` | `hslog.LogParser` | Only services/ file importing hslog (D-10) | WIRED | `grep -lr "^from hslog\|^import hslog" stonereader/services/` returns only `_parser.py` |
| `_parser.py` | `_packets.py` | Translates hslog packets to internal Packet types | WIRED | `from stonereader.services._packets import ...` at top of _parser.py |
| `_engine.py` | `_packets.py` | Engine consumes internal Packet types only (D-10) | WIRED | Imports from `stonereader.services._packets`; no hslog import |
| `_engine.py` | `_events.py` | Engine emits typed GameEvent subclasses | WIRED | Imports from `stonereader.services._events`; all 11 concrete events emitted per behavior table |
| `_tracker.py` | `_watcher.py + _parser.py + _engine.py + _process_detect.py + _log_path.py` | Composition — tracker owns all 5 components | WIRED | `self._watcher = PowerLogWatcher(...)`, `self._parser = Parser()`, `self._engine = GameEngine(...)`, `self._process_detector = ... ProcessDetector()` |
| `app.py` | `GameTracker` | `self._tracker = GameTracker(card_db)`, `self._tracker.start(parent=self._frame)` | WIRED | Lines confirmed; `grep "self._tracker" app.py` matches |
| `__main__.py` | `configure_logging()` | Called before StoneReaderApp construction | WIRED | `configure_logging()` on line 14 of __main__.py |
| `services/__init__.py` | `_events.py` + `_tracker.py` | Re-exports all 12 event types + GameTracker | WIRED | `from stonereader.services._events import ...` and `from stonereader.services._tracker import GameTracker` present |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_tracker._on_lines()` | `lines: List[str]` | `PowerLogWatcher.on_lines` callback with tailed file bytes | Yes — real file I/O via `path.open("rb")` + `fp.read()` | FLOWING |
| `GameEngine.current_state` | `_current_state: Optional[GameState]` | Built from `CreateGamePacket`, updated by `TagChangePacket` via `dataclasses.replace` | Yes — reconstructed per packet, confirmed by 4 PASSED engine tests | FLOWING |
| `GameTracker._dispatch` | `event: GameEvent, state: Optional[GameState]` | Engine.apply(packet) returns list; iterated in _on_lines | Yes — fixture tests confirm events are emitted from real Power.log lines | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 242 tests pass (0 skipped) | `uv run pytest tests/ -q` | `242 passed in 0.91s` | PASS |
| Fixture engine tests pass | `uv run pytest tests/test_services/test_engine.py -v` | 4 PASSED | PASS |
| hslog importable | `uv run python -c "import hslog; print(hslog.__version__)"` | Confirmed in SUMMARY (1.18.0) | PASS |
| psutil importable | `uv run python -c "import psutil; print(psutil.__version__)"` | Confirmed in SUMMARY (7.2.2) | PASS |
| D-10 isolation | `grep -lr "^from hslog\|^import hslog" stonereader/services/` | Returns only `_parser.py` | PASS |
| No wx in engine | `grep -E "^import wx\|^from wx" stonereader/services/_engine.py` | No output | PASS |
| Pitfall 9: Timer after Show | `grep -nE "self._frame.Show\|self._tracker.start" stonereader/app.py` | Show on 490, start on 495 | PASS |
| Pitfall 10: no configure_logging in app.py | `grep -c "configure_logging" stonereader/app.py` | 0 | PASS |
| Fixtures anonymized | `grep "Eyeronic" tests/fixtures/log/*.log` | No output | PASS |
| Fixture dedup verification | `test_dual_source_fixture_no_duplicates` with mid_game.log (632 PTL lines) | PASSED | PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LOG-01 | 02-01, 02-03, 02-06, 02-08 | App watches Power.log in real time | SATISFIED | PowerLogWatcher + 150ms timer; `test_appended_lines_picked_up_within_one_tick` passes; `test_mid_game_fixture_emits_expected_events` passes against real fixture |
| LOG-02 | 02-01, 02-05, 02-06, 02-08 | Filters PowerTaskList duplicate lines | SATISFIED | Watcher pre-filter + hslog parser filter (defense in depth); `test_powertasklist_dropped_by_hslog` + `test_dual_source_fixture_no_duplicates` both pass |
| LOG-03 | 02-01, 02-03, 02-06 | Detects Power.log reset on Hearthstone restart | SATISFIED | `_handle_reset()` called on truncation (size < offset) or new path; `test_truncation_resets_offset_and_parser` passes; parser + engine reset on watcher reset |
| LOG-04 | 02-01, 02-02, 02-07 | Auto-creates or verifies log.config | SATISFIED | `ensure_log_config()` wired in OnInit; 4 tests pass (creates absent, preserves sections, idempotent, path resolution); smoke test confirmed on Linux |
| LOG-05 | 02-01, 02-07 | Log watcher runs without blocking UI | SATISFIED | wx.Timer architecture (not background thread per D-19 reinterpretation); `test_start_stop_clean` confirms Timer stopped cleanly; no blocking observed in smoke test |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `stonereader/services/_engine.py` | 74, 95, 188 | `_game_started_emitted` flag is set but never checked as a guard before emitting `GameStarted` — `_on_create_game` always returns `[GameStarted(...)]` unconditionally (because `reset()` clears the flag before the check would occur anyway) | Warning | If CREATE_GAME appears twice in a session (genuine mid-game reconnect), `GameStarted` is emitted twice to all subscribers. Not a Phase 2 blocker — no Phase 3 subscriber exists yet. Review finding WR-01. |
| `stonereader/services/_engine.py` | 78, 268, 293, 332, 337 | `_friendly_player_id` hardcoded to `1` and never updated from CONTROLLER tag observations — comment promises refinement that was not implemented | Warning | Player/opponent classification inverted for 50% of games where local player is assigned entity_id=2 by the server. Phase 3 event subscribers (`CardDrawn.controller`, `CardPlayed.controller`) will return wrong values in those games. Review finding WR-02. Requires human verification to confirm scope of impact. |
| `stonereader/services/_engine.py` | 424 | `_ = GameEntity` dead-code suppression sentinel — GameEntity is imported but only referenced in a comment | Info | Minor — no behavioral impact. Review finding IN-01. |
| `stonereader/services/_tracker.py` | 69 | `def start(self, parent) -> None:` missing type annotation on `parent` | Info | Minor type-checking gap. Review finding IN-02. |
| `stonereader/services/_parser.py` | 89 | `self._hslog._parsing_state` accesses a private hslog attribute without a one-time warning on AttributeError | Info | Silent failure on hslog API drift. Review finding IN-03. |
| `stonereader/services/_log_config.py` | 67 | Write path has no internal exception handling — `PermissionError`/`OSError` propagates to caller without documentation | Info | Caller in app.py does wrap with broad except, so no crash. Review finding WR-03. |

### Human Verification Required

#### 1. Windows App Launch + log.config Integration (Plan 07 Task 3, blocking checkpoint)

**Test:** Run `uv run python -m stonereader` on a Windows machine with a screen reader (NVDA or JAWS). Verify:
1. Existing UI (card browser, deck manager) launches cleanly without exception
2. `~/.stonereader/stonereader.log` exists and contains entries including "GameTracker started"
3. `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config` was created or updated to include `[Power]` section with all 5 required keys. Other tools' sections (e.g. `[Achievements]`, `[FullScreenFX]`) are preserved unchanged
4. Close the app window. Log shows "GameTracker stopped". Process exits without a dangling Timer
5. Re-launch confirms idempotent: no second "Updated log.config" message; `[Power]` values identical

**Expected:** Clean launch, correct log.config, clean shutdown, no UI freeze on any of the above steps

**Why human:** The wx.Timer start/stop lifecycle (Pitfall 9) is only observable with a real Windows wx event loop. Linux smoke test confirmed the sequence via `wx.CallLater` but that bypasses the actual NVDA/JAWS message pump. Plan 07 explicitly designated this as a `checkpoint:human-verify gate="blocking"` task that was never closed with an "approved" signal.

#### 2. Live Game Tracking: Player ID Classification

**Test:** On Windows with Hearthstone running, start a Casual match and note which entity_id (1 or 2) you are assigned. Check `stonereader.log` for `CardDrawn` and `CardPlayed` events — confirm `controller=1` maps to your own cards (not opponent's).

**Expected:** All your cards report `controller=1`; opponent cards report `controller=2` regardless of which player entity_id you were assigned.

**Why human:** `_friendly_player_id` is hardcoded to `1` (WR-02 from code review). This produces inverted classifications when the local player is entity_id=2 — which occurs in approximately half of all games. Only a live game test can confirm whether this causes visible incorrect behavior in the Phase 3 event stream. The fix requires observing CONTROLLER tags during game init to identify the local player entity.

### Gaps Summary

No automated gaps were found that block the phase goal. All four roadmap success criteria are verified by passing tests (242/242). Two items require human verification before the phase can be declared fully passed:

1. **Plan 07 Task 3 Windows checkpoint** (blocking per plan design) — The smoke test ran successfully on Linux, but the plan explicitly requires Windows verification with a real app launch to confirm wx.Timer lifecycle, log.config write, and no UI freeze.

2. **WR-02 player ID classification** — The `_friendly_player_id=1` stub is a known limitation flagged by the code review. It does not prevent Phase 2's log infrastructure from functioning (events are emitted), but it means the `controller` field on emitted events (CardDrawn, CardPlayed, etc.) is incorrect for games where the local player is entity 2. This should be confirmed or accepted before Phase 3 builds subscriber logic on top of these events.

Both items are human-verification rather than code gaps. The infrastructure is built, tested, and the test suite is fully green.

---

_Verified: 2026-04-25_
_Verifier: Claude (gsd-verifier)_
