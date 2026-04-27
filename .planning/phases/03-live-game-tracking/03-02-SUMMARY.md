---
phase: 03-live-game-tracking
plan: 02
subsystem: services
tags: [phase-03, wr-02, friendly-player, engine, parser, hslog, friendly-player-exporter]

# Dependency graph
requires:
  - phase: 02-log-infrastructure
    provides: GameEngine, Parser, CreateGamePacket, ShowEntityPacket, FullEntityPacket, TagChangePacket, GameTracker subscriber bus
  - phase: 03-live-game-tracking
    provides: 03-01 — xfail stub tests in tests/test_services/test_engine_friendly_player.py + power_log_fixture loader
provides:
  - 5-tuple CreateGamePacket.players carrying (entity_id, player_id, name, hi, lo) end-to-end
  - Deferred CreateGame emission so the parser waits until hslog has appended Player rows
  - GameEngine._friendly_player_id resolved correctly via AI heuristic (CREATE_GAME) + SHOW_ENTITY-into-HAND fallback
  - Authoritative re-bucket from _entities CONTROLLER state on resolution (correct mixed-timing attribution)
  - Reconnect-safe re-resolution (reset() clears _friendly_player_resolved)
affects: [03-03, 03-04, 03-05, 03-06, 04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred packet emission: parser holds back CreateGame translation until hslog parsing state confirms Player rows are complete (entity_packet no longer points at the in-progress CreateGame or one of its Players)"
    - "Authoritative re-bucket on friendly-player resolution: walk drawn/played rows and re-attribute each based on _entities[entity_id].CONTROLLER, not the bucket the row was first placed in"
    - "AI heuristic mirrored from hslog.export.FriendlyPlayerExporter without importing hslog (D-10 isolation): exactly one lo==0 + one lo!=0 → lo!=0 is friendly"

key-files:
  created:
    - .planning/phases/03-live-game-tracking/03-02-SUMMARY.md
  modified:
    - stonereader/services/_packets.py
    - stonereader/services/_parser.py
    - stonereader/services/_engine.py
    - tests/test_services/test_engine.py
    - tests/test_services/test_parser.py
    - tests/test_services/test_engine_friendly_player.py

key-decisions:
  - "CreateGamePacket.players widened to 5-tuple (entity_id, player_id, name, hi, lo) so the engine can run the FriendlyPlayerExporter heuristic without an hslog import (D-10)"
  - "Player.entity_id extracted from PlayerReference.entity_id (hslog Player.entity is a PlayerReference, not a plain int) — added _player_entity_id helper for defensive extraction"
  - "Player name resolved from Player.name first, then PlayerReference.name fallback (hslog initially leaves Player.name=None until later parsing populates it)"
  - "Deferred CreateGame emission: prior parser walked too eagerly and emitted CreateGamePacket(players=()) on the same line as CREATE_GAME header — fixed by deferring until hslog's entity_packet state moves past the Player block or until a subsequent top-level packet appears"
  - "Re-bucket from authoritative _entities CONTROLLER state, not blind list-swap (per 03-REVIEWS.md HIGH #2). The swap would only have worked when ALL pre-resolution events were uniformly inverted; mixed-timing produces correctly-attributed AND incorrectly-attributed rows in the same accumulators"
  - "reset() clears _friendly_player_resolved AND _friendly_player_id so reconnects (second CREATE_GAME) re-run the heuristic against the new server-assigned slot"

patterns-established:
  - "Deferred-emission pattern: a parser walking an in-progress packet tree may need to delay translating a packet until the upstream library confirms its child collections are complete. Use entity_packet (or equivalent build-state cursor) to detect 'still building'"
  - "Authoritative-recompute on attribution flip: when a derived attribute (friendly_player_id) flips during streaming, recompute downstream buckets from the authoritative source-of-truth (per-entity CONTROLLER tags) rather than transforming the existing buckets"
  - "Defensive Player extraction: hslog Player records carry refs to PlayerReference objects whose fields are populated incrementally — extract via getattr-with-fallback so the parser tolerates incomplete records"

requirements-completed: [WR-02]

# Metrics
duration: 11min
completed: 2026-04-27
---

# Phase 03 Plan 02: WR-02 Friendly-Player Resolution Summary

**FriendlyPlayerExporter-style resolution (AI heuristic + SHOW_ENTITY-into-HAND fallback) wired into GameEngine with 5-tuple CreateGamePacket and authoritative re-bucket on flip — fixes inverted CardDrawn/CardPlayed attribution for ~50% of multiplayer games where the local player is server-assigned CONTROLLER=2.**

## Performance

- **Duration:** ~11 min
- **Started:** 2026-04-27T03:08:12Z
- **Completed:** 2026-04-27T03:19:53Z
- **Tasks:** 2 (both TDD: RED then GREEN)
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- Widened `CreateGamePacket.players` from 4-tuple `(entity_id, name, hi, lo)` to 5-tuple `(entity_id, player_id, name, hi, lo)` so the engine has `player_id` distinctly from the entity ID — required for the FriendlyPlayerExporter algorithm.
- Updated the parser to extract `entity_id` from the hslog `PlayerReference` object (`Player.entity.entity_id`) and `player_id` from `Player.player_id`, with name fallback through `PlayerReference.name` for the common case where `Player.name` is initially `None`.
- Added deferred CreateGame emission to the parser — the previous walk emitted `CreateGamePacket(players=())` because hslog appends Player rows after the CREATE_GAME line is parsed. Now the walk defers translation until hslog's `entity_packet` state confirms parsing has moved past the Player block.
- Replaced the `_friendly_player_id = 1` constant stub in `GameEngine.__init__` with a real two-path resolution: AI heuristic at CREATE_GAME consumption (immediate when one player has `lo == 0` and one has `lo != 0`) + SHOW_ENTITY-into-HAND fallback (multiplayer games where both players have `lo != 0`).
- Added `_rebucket_from_entities()` which, on resolution flip, walks every accumulated `player_drawn` / `opponent_drawn` / `player_played` / `opponent_played` row and re-attributes it based on `self._entities[row.entity_id].CONTROLLER` — the authoritative source rather than blindly swapping accumulator lists. This addresses 03-REVIEWS.md HIGH #2's mixed-timing concern.
- Cleared `_friendly_player_resolved` in `reset()` so reconnects (second CREATE_GAME) re-run the heuristic without leaking prior-game state.
- All 6 stub tests in `tests/test_services/test_engine_friendly_player.py` now pass green (xfail removed).
- Pre-existing `test_card_drawn_controller_reflects_log_controller` continues to pass — raw `CardDrawn.controller` pass-through is preserved.
- All 4 captured Power.log fixtures continue to resolve `friendly_player_id == 1` (regression-locked).
- Engine still has zero `hslog` imports (D-10 boundary preserved — engine remains reusable for Phase 4 replays).

## Task Commits

Each task was committed atomically:

1. **Task 1: Widen CreateGamePacket to 5-tuple + parser extracts entity_id from PlayerReference + deferred CreateGame emission** — `e0e7a1b` (feat)
2. **Task 2 RED: Replace WR-02 xfail stubs with real failing tests** — `3872d7d` (test)
3. **Task 2 GREEN: Implement WR-02 friendly-player resolution in GameEngine** — `81aa889` (feat)

**Plan metadata commit:** pending (created with this SUMMARY).

## Files Created/Modified

- `stonereader/services/_packets.py` — Modified. `CreateGamePacket.players` annotation widened to `Tuple[Tuple[int, int, str, int, int], ...]`; docstring updated to document the 5-tuple shape and the WR-02 / D-18 rationale. Drive-by: removed unused `typing.Any` import (pre-existing, fixed because the file was being touched).
- `stonereader/services/_parser.py` — Modified. CreateGame translation now emits the 5-tuple via two new helpers `_player_entity_id` (extracts `.entity_id` from `PlayerReference`) and `_player_name` (falls back through `PlayerReference.name`). Added deferred-emission tracking via `_pending_create_game_pyid` and `_create_game_still_building()` so CreateGamePacket waits for the Player block to complete before translation.
- `stonereader/services/_engine.py` — Modified. Replaced WR-02 stub block with real init (`_friendly_player_id` + `_friendly_player_resolved`); destructures players in 5-tuple form; calls `_resolve_friendly_player_ai_heuristic` after the players loop; calls `_resolve_friendly_player_show_entity_fallback` from `_on_show_entity` when not yet resolved; adds three new private helpers (heuristic, fallback, rebucket); `reset()` clears the resolved flag + default ID. Stores `PLAYER_ID` on the player entity for downstream consumers.
- `tests/test_services/test_engine.py` — Modified. Two CreateGamePacket constructor calls carried forward to 5-tuple form. Semantic outputs (CardDrawn.controller assertion etc.) unchanged.
- `tests/test_services/test_parser.py` — Modified. Existing `test_translates_create_game_packet` extended with positive shape assertions on the new 5-tuple. Added a trailing TAG_CHANGE line to the test fixture so the deferred-emission logic can confirm the Player block is complete (and updated expected `name` to `""` because the test fixture omits PlayerName lines, so hslog leaves both `Player.name` and `PlayerReference.name` as `None`).
- `tests/test_services/test_engine_friendly_player.py` — Modified. Replaced the 6 Wave 0 xfail stubs with real test bodies covering AI heuristic for both player slots, SHOW_ENTITY fallback, mixed-timing re-bucket scenario, captured-fixture regression lock, and reconnect re-resolution.

## Decisions Made

- **5-tuple over per-engine PlayerID lookup:** the cleanest place to expose `player_id` is at the packet boundary, since the engine cannot import hslog (D-10). Widening the tuple keeps the packet self-describing and the engine pure.
- **Deferred emission over re-emission:** an alternative would have been to emit CreateGamePacket immediately and re-emit when players completed, but that would break the existing "each packet emitted exactly once" contract and require subscribers to deduplicate. Deferring trades a minor latency (one extra log line) for contract-preserving behaviour.
- **Authoritative re-bucket over blind swap (03-REVIEWS.md HIGH #2):** the original plan considered swapping the `player_drawn` / `opponent_drawn` lists when the friendly_player_id flipped. That works only when ALL pre-resolution events were uniformly inverted — but mixed-timing scenarios (some events before resolution, some after) produce both correctly-attributed AND incorrectly-attributed rows in the same accumulators. Walking each row against the authoritative `_entities` CONTROLLER tag is the only correct approach.
- **Default `_friendly_player_id = 1` retained:** when AI heuristic is inconclusive (multiplayer games before the first SHOW_ENTITY), the engine continues to use 1 as the working assumption. The fallback flips it correctly once the first SHOW_ENTITY-into-HAND arrives, and `_rebucket_from_entities` cleans up any rows added during the unresolved window.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 / Rule 3 - Blocking parser bug] Deferred CreateGame emission to capture Player rows**
- **Found during:** Task 1 verification (RED phase of `test_translates_create_game_packet` shape assertion)
- **Issue:** The parser walked the hslog packet tree on every `feed_line` call and marked CreateGame as seen on the first walk — but hslog appends Player rows to the SAME CreateGame packet on subsequent lines. As a result, `CreateGamePacket.players` was always `()` regardless of how many Player lines followed. This made the WR-02 AI heuristic impossible to invoke (it needs non-empty players).
- **Fix:** Added `_pending_create_game_pyid` tracking and a `_create_game_still_building(hp)` predicate that inspects `hslog._parsing_state.entity_packet` to detect whether parsing is still inside the CreateGame's GameEntity / Player section. CreateGame translation is deferred until either (a) a subsequent top-level packet exists after it, or (b) entity_packet has moved past the CreateGame and its Players.
- **Files modified:** stonereader/services/_parser.py
- **Verification:** `test_translates_create_game_packet` passes with non-empty players; all captured-fixture engine tests continue to pass; `test_captured_fixtures_resolve` correctly resolves friendly_player_id=1 for all 4 fixtures.
- **Committed in:** `e0e7a1b` (Task 1 commit)

**2. [Rule 1 - Bug] Extract entity_id from PlayerReference instead of treating Player.entity as int**
- **Found during:** Task 1 verification (after fixing the deferred-emission, the resulting tuple had a `PlayerReference(...)` object in slot 0 instead of an int)
- **Issue:** hslog's `Player.entity` is a `PlayerReference` object (with `.entity_id`, `.player_id`, `.name`) — not a plain int. The previous parser code `getattr(p, "entity", 0) or getattr(p, "player_id", 0)` would have returned the truthy `PlayerReference` object, so even if CreateGame had been emitted with players, the entity_id field would have been wrong.
- **Fix:** Added `_player_entity_id(p)` helper that pulls `.entity_id` from a `PlayerReference` (or falls back to `int(player_id)` if the reference is missing). Also added `_player_name(p)` that falls back through `PlayerReference.name` because `Player.name` itself is initially `None` (hslog populates it later).
- **Files modified:** stonereader/services/_parser.py
- **Verification:** parser tests + engine fixture tests pass; `test_translates_create_game_packet` confirms `players[0] == (2, 1, "", 1, 1)` for the test data.
- **Committed in:** `e0e7a1b` (Task 1 commit)

**3. [Rule 1 - Test data correction] Updated test_parser assertion's expected name from "P1" to "" and added trailing TAG_CHANGE line**
- **Found during:** Task 1 verification
- **Issue:** The plan's specified assertion `(2, 1, "P1", 1, 1)` would never have matched what hslog actually produces for the test fixture lines `Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]` — those lines do NOT include a player name token, so hslog leaves both `Player.name` and `PlayerReference.name` as `None`. Additionally, without a trailing non-CreateGame packet, the new deferred-emission logic would correctly hold back the CreateGamePacket forever (because there's no signal that the Player block is complete).
- **Fix:** Updated the test assertion to expect `(2, 1, "", 1, 1)` / `(3, 2, "", 2, 2)` (matching the empty-name fallback) and added a trailing `TAG_CHANGE Entity=GameEntity tag=NEXT_STEP value=BEGIN_MULLIGAN` line to the test input so the deferred-emission logic can flush the CreateGame.
- **Files modified:** tests/test_services/test_parser.py
- **Verification:** test passes with both assertions matching exactly.
- **Committed in:** `e0e7a1b` (Task 1 commit)

**4. [Rule 1 - Hygiene] Removed pre-existing unused typing.Any import in _packets.py**
- **Found during:** Task 2 verification (`uv run ruff check stonereader/services/`)
- **Issue:** `_packets.py` had `from typing import Any, Dict, Optional, Tuple` but `Any` was never used in the file (pre-existing, present since the file was created in plan 02-05). Since the task touched this file and the plan's verification step requires `uv run ruff check stonereader/services/` to pass, leaving the unused import would have failed verification.
- **Fix:** Removed `Any` from the typing import.
- **Files modified:** stonereader/services/_packets.py
- **Verification:** `uv run ruff check stonereader/services/` exits 0.
- **Committed in:** `81aa889` (Task 2 GREEN commit, drive-by)

---

**Total deviations:** 4 auto-fixed (3 blocking parser correctness bugs that the plan didn't anticipate, 1 hygiene fix in a touched file).

**Impact on plan:** Deviations 1 and 2 are pre-existing parser bugs that the plan-author had assumed were already correct (the parser comment `Player uses .entity (EntityID) and .player_id (PlayerID)` suggested the entity field was treated as a plain int). Without fixing these, WR-02 cannot ship at all because the AI heuristic would always see `players=()`. Deviation 3 was a small test-data correction needed to match what hslog actually produces. Deviation 4 was trivial hygiene. No scope creep — all four were correctness or hygiene fixes inside the files this plan was already modifying.

## Issues Encountered

None beyond the deviations above. The plan's pre-flight reading (Wave 0 stubs, parser source, engine source, fixtures) gave a clean execution path once the upstream parser bugs were addressed.

## Threat Flags

None. The implementation matches the plan's `<threat_model>` mitigation for T-03-WR-02 (friendly-player misattribution) — the FriendlyPlayerExporter algorithm is reproduced, captured-fixture regression-lock test added, AI-heuristic and SHOW_ENTITY-fallback paths covered, mixed-timing re-bucket validated, and raw `CardDrawn.controller` pass-through preserved (verified by the existing `test_card_drawn_controller_reflects_log_controller`).

## User Setup Required

None — the plan touched parser and engine only; no new dependencies, config files, or external services.

## Next Phase Readiness

- **Plan 03-03 (D-19 creation lineage):** can now rely on `_friendly_player_id` resolving correctly when bucketing card events. The `PLAYER_ID` tag is now stamped on player entities for any subsequent presenter that needs it.
- **Plan 03-04 (GlobalHotkeyService):** unaffected — purely UI/wx layer.
- **Plan 03-05 (LiveGamePresenter):** when the presenter consumes `GameState.player_drawn` / `opponent_drawn`, the buckets will be correct for all coin-flip outcomes (no more 50% inversion).
- **Plan 03-06 (LiveGamePanel + app wiring):** unaffected.
- **Phase 4 (Replay viewer):** the engine remains hslog-free (D-10), so it can be reused to replay HSReplay XMLs once the replay-specific Parser is added.

## Self-Check: PASSED

Verified files and commits exist on disk and in git history:

- `stonereader/services/_packets.py` — FOUND (5-tuple Tuple type annotation present, docstring updated)
- `stonereader/services/_parser.py` — FOUND (`_player_entity_id`, `_player_name`, `_pending_create_game_pyid`, `_create_game_still_building` all present)
- `stonereader/services/_engine.py` — FOUND (`_resolve_friendly_player_ai_heuristic`, `_resolve_friendly_player_show_entity_fallback`, `_rebucket_from_entities`, `_friendly_player_resolved` all present; TODO(WR-02) gone)
- `tests/test_services/test_engine_friendly_player.py` — FOUND (6 named tests, no `pytestmark = pytest.mark.xfail`)
- `tests/test_services/test_engine.py` — FOUND (5-tuple carry-forward at lines 28 and 59)
- `tests/test_services/test_parser.py` — FOUND (5-tuple shape assertion present)
- `.planning/phases/03-live-game-tracking/03-02-SUMMARY.md` — FOUND (this file)
- Commit `e0e7a1b` — FOUND (Task 1: 5-tuple + deferred emission)
- Commit `3872d7d` — FOUND (Task 2 RED: real failing tests)
- Commit `81aa889` — FOUND (Task 2 GREEN: WR-02 implementation)

Plan-level verification:
- `uv run pytest tests/ -q` → 250 passed, 30 xfailed (other Phase 3/4 stubs)
- `uv run pytest tests/test_services/ -q` → 81 passed, 6 xfailed (D-19 stubs from 03-01 not yet implemented; that's plan 03-03)
- `uv run ruff check stonereader/services/` → All checks passed
- `uv run pyright stonereader/services/_engine.py stonereader/services/_packets.py stonereader/services/_parser.py` → 0 errors, 0 warnings
- `grep "import hslog\|from hslog" stonereader/services/_engine.py` → no matches (D-10 boundary preserved)

---
*Phase: 03-live-game-tracking*
*Completed: 2026-04-27*
