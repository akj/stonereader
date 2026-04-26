---
phase: 2
slug: log-infrastructure
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-25
last_updated: 2026-04-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (existing, in `pyproject.toml [dependency-groups] dev`) |
| **Config file** | None — pytest uses defaults; `tests/conftest.py` provides `MockSpeechService` |
| **Quick run command** | `uv run pytest tests/test_services/ -x` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds (services-only); ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_services/ -x`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Filled in by the planner. Each PLAN.md task adds a row here with its automated command, requirement coverage, and threat reference (if any). Status is updated by the executor as tasks land.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 01 | 0 | (infra) | T-2-00 | dependency pinning | unit | `uv run python -c "import hslog, psutil"` | pyproject.toml | ⬜ pending |
| 02-01-T2 | 01 | 0 | (infra) | — | — | infra | `uv run python -c "import sys; sys.path.insert(0, 'tests/test_services'); import conftest; assert hasattr(conftest, 'FakeClock')"` | tests/test_services/conftest.py | ⬜ pending |
| 02-01-T3 | 01 | 0 | LOG-01..05 | — | — | infra (stubs) | `uv run pytest tests/test_services/ --collect-only -q` | tests/test_services/test_*.py | ⬜ pending |
| 02-02-T1 | 02 | 1 | (infra) | T-2-DOS | rotating log handler caps at 8MB | unit | `uv run pytest tests/test_services/test_logging_config.py -x` | stonereader/services/_logging_config.py | ⬜ pending |
| 02-02-T2 | 02 | 1 | LOG-04 | T-2-02 | RawConfigParser preserves other tools' sections | unit | `uv run pytest tests/test_services/test_log_config.py -x` | stonereader/services/_log_config.py | ⬜ pending |
| 02-03-T1 | 03 | 1 | LOG-01 | T-2-01 | Logs/ subdir mtime selection only — no path traversal beyond user-owned filesystem | unit | `uv run pytest tests/test_services/test_log_path.py -x` | stonereader/services/_log_path.py | ⬜ pending |
| 02-03-T2 | 03 | 1 | LOG-03 | T-2-DOS | psutil TTL cache caps process_iter cost; defensive try/except (NoSuchProcess) | unit | `uv run pytest tests/test_services/test_process_detect.py -x` | stonereader/services/_process_detect.py | ⬜ pending |
| 02-04-T1 | 04 | 2 | LOG-01,LOG-02 | T-2-DATA | Tuple-only collections; frozen dataclass | unit | `uv run pytest tests/test_services/test_game_state_extension.py -x` | stonereader/models/game_state.py | ⬜ pending |
| 02-04-T2 | 04 | 2 | LOG-01,LOG-02 | T-2-DATA | 11 frozen event classes | unit | `uv run pytest tests/test_services/test_events.py -x` | stonereader/services/_events.py | ⬜ pending |
| 02-05-T1 | 05 | 2 | LOG-02 | — | typed exceptions; D-10 isolation enforced | unit | `uv run python -c "from stonereader.services._exceptions import ParserError, EngineError; from stonereader.services._packets import CreateGamePacket; import dataclasses; assert dataclasses.is_dataclass(CreateGamePacket)"` | stonereader/services/_packets.py, _exceptions.py | ⬜ pending |
| 02-05-T2 | 05 | 2 | LOG-02 | T-2-PARSE,T-2-DRIFT | NoSuchEnum log-once cache; PowerTaskList drop verified | unit | `uv run pytest tests/test_services/test_parser.py -x` | stonereader/services/_parser.py | ⬜ pending |
| 02-06-T1 | 06 | 3 | LOG-01,LOG-02,LOG-03 | T-2-RESET | _LineReader resets decoder + partial buffer; engine snapshots frozen | unit | `uv run pytest tests/test_services/test_line_reader.py tests/test_services/test_engine.py -x` | stonereader/services/_line_reader.py, _engine.py | ⬜ pending |
| 02-06-T2 | 06 | 3 | LOG-01,LOG-02,LOG-03 | T-2-03,T-2-D04 | 100k buffer cap; tick error log+continue; backward scan capped at 1MB | unit | `uv run pytest tests/test_services/test_watcher.py -x` | stonereader/services/_watcher.py | ⬜ pending |
| 02-07-T1 | 07 | 4 | LOG-05 | T-2-04 | Subscriber exception isolation (Pitfall 3) | unit | `uv run pytest tests/test_services/test_tracker.py -x` | stonereader/services/_tracker.py | ⬜ pending |
| 02-07-T2 | 07 | 4 | LOG-04,LOG-05 | T-2-PITFALL10 | configure_logging called exactly once at __main__ | integration | `uv run pytest tests/ -x && uv run python -c "from stonereader.app import StoneReaderApp"` | stonereader/__main__.py, stonereader/app.py | ⬜ pending |
| 02-07-T3 | 07 | 4 | LOG-01..05 | T-2-LIFECYCLE | Manual launch verifies Timer + log.config + lifecycle | manual | (human verify — see Plan 07 task 3) | (human checkpoint) | ⬜ pending |
| 02-08-T1 | 08 | 5 | LOG-01,LOG-02 | T-2-PII | Anonymization removes BattleTags/BnetIDs | manual | (capture procedure — see Plan 08 task 1) | tests/fixtures/log/*.log | ⬜ pending |
| 02-08-T2 | 08 | 5 | (infra) | T-2-FIXTURE-DRIFT | Documented re-capture procedure | infra | `test -f .planning/phases/02-log-infrastructure/02-FIXTURE-CAPTURE.md` | 02-FIXTURE-CAPTURE.md | ⬜ pending |
| 02-08-T3 | 08 | 5 | LOG-01,LOG-02 | T-2-FIXTURE-SIZE | Fixtures fit size budget | integration | `uv run pytest tests/test_services/test_engine.py -v` (test_mid_game_*, test_dual_source_*, test_tick_under_50ms PASS not SKIP) | tests/fixtures/log/*.log | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Phase Requirements → Test Map (from RESEARCH.md)

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| LOG-01 | Watcher detects new bytes appended to a fixture file within one tick | unit (file fixtures) | `uv run pytest tests/test_services/test_watcher.py::test_appended_lines_picked_up_within_one_tick -x` | ⬜ Plan 06 |
| LOG-01 | Real Power.log fixture (`mid_game.log`) parsed end-to-end into events + final GameState | integration | `uv run pytest tests/test_services/test_engine.py::test_mid_game_fixture_emits_expected_events -x` | ⬜ Plan 06 stub, Plan 08 fixture |
| LOG-01 | LogParser receives only `GameState.*` lines (PowerTaskList filtered) | unit | `uv run pytest tests/test_services/test_watcher.py::test_powertasklist_lines_filtered -x` | ⬜ Plan 06 |
| LOG-02 | Feeding hslog the same log file twice does NOT produce duplicate events | unit | `uv run pytest tests/test_services/test_parser.py::test_powertasklist_dropped_by_hslog -x` | ⬜ Plan 05 |
| LOG-02 | Fixture with both PowerTaskList and GameState lines emits exactly N events (matches GameState-only count) | integration | `uv run pytest tests/test_services/test_engine.py::test_dual_source_fixture_no_duplicates -x` | ⬜ Plan 06 stub, Plan 08 fixture |
| LOG-03 | Watcher detects file truncation (size shrinks) and resets offset + parser state | unit | `uv run pytest tests/test_services/test_watcher.py::test_truncation_resets_offset_and_parser -x` | ⬜ Plan 06 |
| LOG-03 | After reset, lines from new file are parsed correctly without partial decode buffer leak | unit | `uv run pytest tests/test_services/test_watcher.py::test_reset_clears_partial_line_buffer -x` | ⬜ Plan 06 |
| LOG-03 | When `hearthstone.exe` disappears, watcher pauses and resets parser state | unit (mock psutil) | `uv run pytest tests/test_services/test_tracker.py::test_process_gone_resets_state -x` | ⬜ Plan 07 |
| LOG-04 | `ensure_log_config` creates file with `[Power]` section when none exists | unit (tmp_path) | `uv run pytest tests/test_services/test_log_config.py::test_creates_file_when_absent -x` | ⬜ Plan 02 |
| LOG-04 | `ensure_log_config` updates `[Power]` keys without destroying other sections | unit (tmp_path) | `uv run pytest tests/test_services/test_log_config.py::test_preserves_other_sections -x` | ⬜ Plan 02 |
| LOG-04 | `ensure_log_config` is idempotent — second call returns False (no change) | unit | `uv run pytest tests/test_services/test_log_config.py::test_idempotent_when_correct -x` | ⬜ Plan 02 |
| LOG-05 (D-19) | `tracker.start()` then `tracker.stop()` does not leak Timer or threads | unit (wx.App fixture) | `uv run pytest tests/test_services/test_tracker.py::test_start_stop_clean -x` | ⬜ Plan 07 |
| LOG-05 (D-19) | A 1000-line fixture processed in a single tick completes in under 50ms | unit (timing) | `uv run pytest tests/test_services/test_engine.py::test_tick_under_50ms -x` | ⬜ Plan 06 stub, Plan 08 fixture |

---

## Wave 0 Requirements

The following must exist before Wave 1 begins:

- [ ] `tests/test_services/conftest.py` — fixture loaders, MockProcessDetector, FakeClock (Plan 01 Task 2)
- [ ] `tests/test_services/test_log_config.py` — covers LOG-04 (Plan 01 Task 3)
- [ ] `tests/test_services/test_log_path.py` — covers D-12 path discovery (Plan 01 Task 3)
- [ ] `tests/test_services/test_process_detect.py` — covers D-03 (Plan 01 Task 3)
- [ ] `tests/test_services/test_watcher.py` — covers LOG-01, LOG-03 (Plan 01 Task 3)
- [ ] `tests/test_services/test_parser.py` — covers LOG-02 (Plan 01 Task 3)
- [ ] `tests/test_services/test_engine.py` — covers integration (Plan 01 Task 3)
- [ ] `tests/test_services/test_tracker.py` — covers LOG-05/D-19 (Plan 01 Task 3)
- [ ] `tests/test_services/test_logging_config.py` — covers D-16 (Plan 01 Task 3)
- [ ] Framework install: `uv add hslog psutil` (Plan 01 Task 1)

Fixtures (`tests/fixtures/log/*.log`) are created by Plan 08 (Wave 5), NOT in Wave 0. Wave 3 fixture-dependent tests SKIP gracefully via `power_log_fixture` until Plan 08 lands.

*No changes to existing `tests/conftest.py` are required — `MockSpeechService` is unchanged. New `tests/test_services/conftest.py` adds local fixtures only.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| App launches with tracker integrated, log.config written, no UI freeze | LOG-04, LOG-05 | Requires real wx app + filesystem | Plan 07 Task 3 (checkpoint:human-verify) |
| Real Hearthstone game runs with the live watcher attached | LOG-01..05 | Requires Windows + active Hearthstone client + a live match | HVC item to be captured post-Phase-2 in `verification.md` |
| `log.config` persistence across machine reboots | LOG-04 | Requires reboot — not automatable in unit tests | Run app on Windows, reboot, relaunch, confirm `log.config` retains `[Power]` section |
| Power.log fixture capture | LOG-01, LOG-02 | Requires Hearthstone gameplay | Plan 08 Task 1 (checkpoint:human-action) — see 02-FIXTURE-CAPTURE.md (created by Plan 08 Task 2) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test stubs)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** Ready for execution.
