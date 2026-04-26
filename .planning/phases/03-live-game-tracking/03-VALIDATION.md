---
phase: 3
slug: live-game-tracking
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-26
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (already installed via `[dependency-groups] dev` in `pyproject.toml`) |
| **Config file** | none — pytest discovers tests via convention |
| **Quick run command** | `uv run pytest tests/test_live_game_presenter.py tests/test_global_hotkey.py tests/test_services/test_engine_friendly_player.py tests/test_services/test_engine_lineage.py -x` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~20–60 seconds for full suite; ~5–15 seconds for touched-file quick run |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest <touched test files> -x` (~5–15s)
- **After every plan wave:** Run `uv run pytest tests/test_live_game_presenter.py tests/test_global_hotkey.py tests/test_services/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green via `uv run pytest tests/ -v` plus `uv run ruff check .` and `uv run pyright`
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner during plan generation. Each plan task entries are mirrored here with their automated test command. Wave 0 entries below cover the Wave 0 file-creation gap; planner fills the rest.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-W0-01 | W0 | 0 | LIVE-01..09 | — | N/A | unit-stubs | `uv run pytest tests/test_live_game_presenter.py --collect-only` | ❌ W0 | ⬜ pending |
| 03-W0-02 | W0 | 0 | LIVE-09 | — | N/A | unit-stubs | `uv run pytest tests/test_global_hotkey.py --collect-only` | ❌ W0 | ⬜ pending |
| 03-W0-03 | W0 | 0 | WR-02 / D-18 | — | N/A | unit-stubs | `uv run pytest tests/test_services/test_engine_friendly_player.py --collect-only` | ❌ W0 | ⬜ pending |
| 03-W0-04 | W0 | 0 | D-19 | — | N/A | unit-stubs | `uv run pytest tests/test_services/test_engine_lineage.py --collect-only` | ❌ W0 | ⬜ pending |
| 03-W0-05 | W0 | 0 | shared mock | — | N/A | fixture | `uv run pytest tests/conftest.py --collect-only` | ✅ ext | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Planner SHALL extend this table with one row per task in each PLAN.md, mapping `<automated>verify</automated>` blocks to the requirement IDs / threat refs they cover.

---

## Wave 0 Requirements

- [ ] `tests/test_live_game_presenter.py` — covers LIVE-01..09, D-07, D-08, D-09. Stub test functions for: `test_lifecycle_silence`, `test_remaining_deck_speech_format`, `test_remaining_deck_sort_order`, `test_drawn_to_zero_visible`, `test_opponent_played_speech_format`, `test_opponent_hand_count`, `test_announce_deck_counts`, `test_mana_query`, `test_auto_deck_detection`, `test_detection_resets_per_game`, `test_silent_during_event`, `test_cursor_preserves_across_render`, `test_no_game_baseline`.
- [ ] `tests/test_global_hotkey.py` — covers LIVE-09 dispatch + conflict + cleanup. Stubs for: `test_register_returns_status`, `test_browse_open_dispatch`, `test_clear_all_idempotent`. Mock `wx.Frame.RegisterHotKey` to return scriptable bool.
- [ ] `tests/test_services/test_engine_friendly_player.py` — covers WR-02 / D-18. Stubs for: `test_local_is_player_2`, `test_ai_heuristic`, `test_show_entity_fallback`, `test_captured_fixtures_resolve`.
- [ ] `tests/test_services/test_engine_lineage.py` — covers D-19. Stubs for: `test_lineage_recorded`, `test_no_lineage_for_normal_draw`, `test_no_lineage_for_friendly`, `test_reconnect_drops_lineage`.
- [ ] `tests/conftest.py` (or `tests/test_live_game_presenter.py` local conftest) — Add `MockGameTracker` fixture exposing `subscribe`/`unsubscribe`/`current_state` without real wx + hslog. (`MockSpeechService`, `power_log_fixture`, `MockProcessDetector` already exist — no new framework install needed.)
- [ ] `tests/test_services/test_engine.py` — UPDATE: `players=((2, "P1", 1, 1), (3, "P2", 2, 2))` tuple shape may need to grow once parser retains `player_id`. Carry-forward task in Wave 0 to keep existing tests green.
- [ ] `tests/test_services/test_parser.py` — UPDATE if `CreateGamePacket.players` shape changes; assert new tuple contains `player_id`.

> If none of these gaps surface in execution, mark `wave_0_complete: true` in frontmatter.

---

## Per-Requirement Test Map (from RESEARCH.md §"Validation Architecture")

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| LIVE-01 | Panel state resets on GameStarted, preserves on GameEnded, "No game in progress" until first event | unit | `pytest tests/test_live_game_presenter.py::test_lifecycle_silence -x` |
| LIVE-02 | Remaining-deck zone announces per-row format from `state.player_deck`; updates on `CardDrawn` | unit | `pytest tests/test_live_game_presenter.py::test_remaining_deck_speech_format -x` |
| LIVE-02 | Sort by mana cost ascending then alphabetical (D-13/D-20) | unit | `pytest tests/test_live_game_presenter.py::test_remaining_deck_sort_order -x` |
| LIVE-02 | Drawn-to-zero cards show "0 copies" when detected deck is known (D-13) | unit | `pytest tests/test_live_game_presenter.py::test_drawn_to_zero_visible -x` |
| LIVE-03 | Opponent-hand zone announces position + identity (or `?`) + drawn turn + lineage (D-04/D-14) | unit | `pytest tests/test_live_game_presenter.py::test_opponent_hand_speech_format -x` |
| LIVE-04 | Opponent-played zone announces "Turn N, Card name"; chronological order (D-15) | unit | `pytest tests/test_live_game_presenter.py::test_opponent_played_speech_format -x` |
| LIVE-05 | Opponent hand count surfaces via panel zone count and/or speak-only hotkey | unit | `pytest tests/test_live_game_presenter.py::test_opponent_hand_count -x` |
| LIVE-06 | Speak-only `announce_deck_counts` produces "N left, opponent M." (D-16) | unit | `pytest tests/test_live_game_presenter.py::test_announce_deck_counts -x` |
| LIVE-07 | Mana fields readable from `GameState`; panel exposes them (panel-only per Open Q2 — confirm in plan) | unit | `pytest tests/test_live_game_presenter.py::test_mana_query -x` |
| LIVE-08 | Auto-detection: 0 saved decks match → "Unknown deck"; 1 match → name shown; 2+ match → "Unknown deck" (D-11) | unit | `pytest tests/test_live_game_presenter.py::test_auto_deck_detection -x` |
| LIVE-08 | Detection runs once per game and re-runs on next GameStarted (D-10, Pitfall 6) | unit | `pytest tests/test_live_game_presenter.py::test_detection_resets_per_game -x` |
| LIVE-09 | `GlobalHotkeyService.register` returns True on success and False on conflict; failed labels accumulate | unit | `pytest tests/test_global_hotkey.py::test_register_returns_status -x` |
| LIVE-09 | Browse-open hotkey opens panel and jumps to zone with D-17 entry speech | integration (no real WM_HOTKEY) | `pytest tests/test_global_hotkey.py::test_browse_open_dispatch -x` |
| LIVE-09 | `clear_all` unregisters every registered chord | unit | `pytest tests/test_global_hotkey.py::test_clear_all_idempotent -x` |
| LIVE-09 | `MainWindow._on_close` calls both `tracker.stop()` and `hotkeys.clear_all()` | integration | `pytest tests/test_navigation.py::test_close_cleans_hotkeys -x` (extends existing test) |
| WR-02 | `_friendly_player_id` resolves to Player 2 when local player has CONTROLLER=2 (D-18) | unit (synthetic packet stream) | `pytest tests/test_services/test_engine_friendly_player.py::test_local_is_player_2 -x` |
| WR-02 | AI heuristic: `lo==0` player is opponent, `lo!=0` player is friendly | unit | `pytest tests/test_services/test_engine_friendly_player.py::test_ai_heuristic -x` |
| WR-02 | SHOW_ENTITY fallback resolves friendly when both players have `lo!=0` | unit (synthetic) | `pytest tests/test_services/test_engine_friendly_player.py::test_show_entity_fallback -x` |
| WR-02 | Existing test `test_card_drawn_controller_reflects_log_controller` still passes (no regression) | unit | `pytest tests/test_services/test_engine.py::test_card_drawn_controller_reflects_log_controller -x` |
| WR-02 | All 4 captured fixtures (`match_start`, `mid_game`, `game_end`, `reconnect`) produce `friendly_player_id=1` | integration | `pytest tests/test_services/test_engine_friendly_player.py::test_captured_fixtures_resolve -x` |
| D-19 | BLOCK_START POWER subject + FULL_ENTITY in opponent HAND records lineage | unit (synthetic) | `pytest tests/test_services/test_engine_lineage.py::test_lineage_recorded -x` |
| D-19 | No lineage for cards drawn outside POWER blocks | unit (synthetic) | `pytest tests/test_services/test_engine_lineage.py::test_no_lineage_for_normal_draw -x` |
| D-19 | No lineage for friendly entities | unit (synthetic) | `pytest tests/test_services/test_engine_lineage.py::test_no_lineage_for_friendly -x` |
| D-19 | Reconnect (second CREATE_GAME) drops lineage from prior game (Pitfall 7) | integration (`reconnect.log` fixture) | `pytest tests/test_services/test_engine_lineage.py::test_reconnect_drops_lineage -x` |
| D-07 | Live-update event handler does NOT call SpeechService | unit | `pytest tests/test_live_game_presenter.py::test_silent_during_event -x` |
| D-07 | Cursor preserved by logical key across re-render (Pitfall 3) | unit | `pytest tests/test_live_game_presenter.py::test_cursor_preserves_across_render -x` |
| D-08 | Panel shows "No game in progress" before first GameStarted | unit | `pytest tests/test_live_game_presenter.py::test_no_game_baseline -x` |
| D-09 | `_on_game_event` for GameStarted/GameEnded never calls speech | unit | `pytest tests/test_live_game_presenter.py::test_lifecycle_silence -x` |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real `WM_HOTKEY` dispatch on Windows | LIVE-09 | Sending OS-level hotkey messages requires Windows + real wx event loop; CI environment may be headless Linux. | On a Windows dev box, run `python -m stonereader`, focus Hearthstone (or any window), press `Ctrl+Shift+R`. Live Game panel should open and Remaining Deck zone should be announced. Repeat for `Ctrl+Shift+O` (Opponent Hand zone). |
| NVDA / JAWS speech with global hotkeys | LIVE-09 | Screen reader behavior is OS-level + reader-version-dependent. | Smoke test on a Windows VM with NVDA active: verify speak-only chord doesn't get cut off by NVDA's own speech queue, and that browse-open chord's zone-entry speech is read in full. |
| Hotkey conflict UX | LIVE-09 | Requires another process holding a chord at the OS level. | On Windows, register `Ctrl+Shift+R` via AutoHotkey or another app, then start StoneReader. Verify the failure-announcement path fires once at startup with the failed chord label. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (4 new test files + 2 update-existing test files + MockGameTracker fixture)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
