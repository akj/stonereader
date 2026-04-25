---
phase: 2
slug: log-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
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
| TBD by planner | — | — | LOG-01..05 | — | — | — | — | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Phase Requirements → Test Map (from RESEARCH.md)

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| LOG-01 | Watcher detects new bytes appended to a fixture file within one tick | unit (file fixtures) | `uv run pytest tests/test_services/test_watcher.py::test_appended_lines_picked_up_within_one_tick -x` | ❌ W0 |
| LOG-01 | Real Power.log fixture (`mid_game.log`) parsed end-to-end into events + final GameState | integration | `uv run pytest tests/test_services/test_engine.py::test_mid_game_fixture_emits_expected_events -x` | ❌ W0 |
| LOG-01 | LogParser receives only `GameState.*` lines (PowerTaskList filtered) | unit | `uv run pytest tests/test_services/test_watcher.py::test_powertasklist_lines_filtered -x` | ❌ W0 |
| LOG-02 | Feeding hslog the same log file twice does NOT produce duplicate events | unit | `uv run pytest tests/test_services/test_parser.py::test_powertasklist_dropped_by_hslog -x` | ❌ W0 |
| LOG-02 | Fixture with both PowerTaskList and GameState lines emits exactly N events (matches GameState-only count) | integration | `uv run pytest tests/test_services/test_engine.py::test_dual_source_fixture_no_duplicates -x` | ❌ W0 |
| LOG-03 | Watcher detects file truncation (size shrinks) and resets offset + parser state | unit | `uv run pytest tests/test_services/test_watcher.py::test_truncation_resets_offset_and_parser -x` | ❌ W0 |
| LOG-03 | After reset, lines from new file are parsed correctly without partial decode buffer leak | unit | `uv run pytest tests/test_services/test_watcher.py::test_reset_clears_partial_line_buffer -x` | ❌ W0 |
| LOG-03 | When `hearthstone.exe` disappears, watcher pauses and resets parser state | unit (mock psutil) | `uv run pytest tests/test_services/test_tracker.py::test_process_gone_resets_state -x` | ❌ W0 |
| LOG-04 | `ensure_log_config` creates file with `[Power]` section when none exists | unit (tmp_path) | `uv run pytest tests/test_services/test_log_config.py::test_creates_file_when_absent -x` | ❌ W0 |
| LOG-04 | `ensure_log_config` updates `[Power]` keys without destroying other sections | unit (tmp_path) | `uv run pytest tests/test_services/test_log_config.py::test_preserves_other_sections -x` | ❌ W0 |
| LOG-04 | `ensure_log_config` is idempotent — second call returns False (no change) | unit | `uv run pytest tests/test_services/test_log_config.py::test_idempotent_when_correct -x` | ❌ W0 |
| LOG-05 (D-19) | `tracker.start()` then `tracker.stop()` does not leak Timer or threads | unit (wx.App fixture) | `uv run pytest tests/test_services/test_tracker.py::test_start_stop_clean -x` | ❌ W0 |
| LOG-05 (D-19) | A 1000-line fixture processed in a single tick completes in under 50ms | unit (timing) | `uv run pytest tests/test_services/test_engine.py::test_tick_under_50ms -x` | ❌ W0 |

---

## Wave 0 Requirements

The following must exist before Wave 1 begins:

- [ ] `tests/test_services/__init__.py` — empty package marker
- [ ] `tests/test_services/conftest.py` — fixture loaders, mock wx.App, mock psutil
- [ ] `tests/test_services/test_log_config.py` — covers LOG-04
- [ ] `tests/test_services/test_log_path.py` — covers D-12 path discovery
- [ ] `tests/test_services/test_process_detect.py` — covers D-03 (mock psutil)
- [ ] `tests/test_services/test_watcher.py` — covers LOG-01, LOG-03 (file polling + reset)
- [ ] `tests/test_services/test_parser.py` — covers LOG-02 (hslog wrapper)
- [ ] `tests/test_services/test_engine.py` — covers integration: LOG-01/02 end-to-end
- [ ] `tests/test_services/test_tracker.py` — covers LOG-05/D-19 (facade lifecycle)
- [ ] `tests/fixtures/log/match_start.log` — D-17 capture
- [ ] `tests/fixtures/log/mid_game.log` — D-17 capture
- [ ] `tests/fixtures/log/game_end.log` — D-17 capture
- [ ] `tests/fixtures/log/reconnect.log` — D-17 capture
- [ ] `tests/fixtures/log/battlegrounds.log` — D-17 capture (optional v1, stress test)
- [ ] Framework install: `uv add hslog psutil` — required before any test runs

*No changes to existing `tests/conftest.py` are required — `MockSpeechService` is unchanged. New `tests/test_services/conftest.py` adds local fixtures only.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Hearthstone game runs with the live watcher attached | LOG-01..05 | Requires Windows + active Hearthstone client + a live match | Launch StoneReader on Windows, start a Hearthstone match, observe stonereader.log for parsed events; HVC item to be captured post-Phase-2 in `verification.md` |
| `log.config` persistence across machine reboots | LOG-04 | Requires reboot — not automatable in unit tests | Run app on Windows, reboot machine, relaunch app, confirm `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config` retains `[Power]` section |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
