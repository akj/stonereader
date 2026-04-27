---
phase: 03-live-game-tracking
plan: 05
subsystem: presenters
tags: [phase-03, live-game-presenter, zone-navigation, auto-detect, speech, wave-2]

# Dependency graph
requires:
  - phase: 02-log-infrastructure
    provides: GameTracker subscriber bus, GameState/GameEntity/PlayedCard frozen dataclasses, GameStarted/GameEnded/CardDrawn/TurnChanged events
  - phase: 03-live-game-tracking
    provides: 03-01 — MockGameTracker + MockSpeechService + 19 xfail stub tests for LiveGamePresenter; 03-02 — friendly_player_id resolution; 03-03 — opponent_hand reconstruction + creation_lineage field
provides:
  - LiveGamePresenter (wx-free) subscribing to GameTracker with 4 zones (remaining_deck, opponent_hand, opponent_played, cards_drawn) per ZoneNavigationMixin
  - OpponentHandRow presenter-layer view shape (frozen dataclass)
  - Public accessors per 03-REVIEWS.md HIGH #3: current_title(), cursor_for_zone(), detected_deck_name(), current_state_snapshot(), current_mana_summary(), announce_opponent_hand_count(), announce_deck_counts(), jump_to_zone()
  - 10-key get_key_map() (left/right/up/down/home/end + 1/2/3/4 zone-switch) per 03-CHECKER blocker #1
  - Auto-deck-detection runs once when player_deck reaches 30 revealed cards; strict 0/1/2+ multiset matching
  - D-13/D-14/D-15 + LIVE-03 cards_drawn per-row speech formats with drawn_turn==-1 -> "unknown" fallback
  - 19 passing tests (Wave 0 xfail stubs replaced with real assertions)
affects: [03-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Presenter subscribes to GameTracker on construction; cleanup() unsubscribes (symmetric lifecycle)"
    - "_on_game_event NEVER calls SpeechService — D-07 silent-during-event rule preserved by structural separation (engine path vs hotkey/key-map path)"
    - "Public accessors expose all view-needed presenter state without private-field access (HIGH #3) — view/app/tests use current_title()/cursor_for_zone()/detected_deck_name()/current_state_snapshot() exclusively"
    - "Auto-detection runs ONCE per game (gated by self._detection_attempted flag); resets on GameStarted; skipped for non-Constructed game types (BATTLEGROUNDS, ARENA per Pitfall 8)"
    - "Strict-match auto-detection: 0 or 2+ saved-deck matches => detected_deck_name = None (Unknown deck); only exactly 1 match wins (D-11)"

key-files:
  created:
    - stonereader/presenters/live_game.py
    - .planning/phases/03-live-game-tracking/03-05-SUMMARY.md
  modified:
    - tests/test_live_game_presenter.py

key-decisions:
  - "OpponentHandRow defined in live_game.py (presenter layer) rather than promoted to stonereader/models — pure view shape adapting GameEntity snapshots into per-row D-14 data, not used outside the presenter"
  - "Drop unused GameEntity import after writing the module skeleton (ruff F401 fix); GameEntity is referenced only by type annotations elsewhere (OpponentHandRow's identity uses Card directly, not GameEntity)"
  - "Use FormatType.FT_STANDARD enum value for write_deckstring() in tests instead of raw int 2 — matches test_deck.py:61 pattern and fixes pyright reportArgumentType errors"
  - "Number keys 1/2/3/4 map to zones in display order (1=remaining, 2=played, 3=hand, 4=drawn) per 03-UI-SPEC §Keyboard Contract — total 10 keys per CHECKER blocker #1"
  - "Test for detection-resets explicitly reads private fields (_detection_attempted, _original_deck_cards) because no public accessor exposes those; documented in test docstring as the rare exception to public-only access"

patterns-established:
  - "Wave 0 xfail-stub flip pattern: drop file-level pytestmark, replace each pytest.xfail() body with real assertions, keep stub function names exact for traceability"
  - "Presenter test scaffolding: _make_presenter(tmp_path, cards=...) helper bundles MockSpeechService + MockGameTracker + sqlite + CardDatabase + presenter construction in one tuple — kept tests under 60 lines each"
  - "tracker.dispatch(event, state) drives _on_game_event synchronously without needing real wx/hslog — Wave 0 MockGameTracker contract works perfectly for presenter-level tests"

requirements-completed: [LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, LIVE-06, LIVE-07, LIVE-08]

# Metrics
duration: 7min
completed: 2026-04-27
---

# Phase 03 Plan 05: LiveGamePresenter Summary

**LiveGamePresenter delivers the 4-zone live-tracking surface (remaining_deck / opponent_hand / opponent_played / cards_drawn) wired to GameTracker, with auto-deck-detection, D-13/D-14/D-15 speech formats, public accessors per REVIEWS HIGH #3, and 10-key keyboard map — all 19 Wave 0 xfail stubs flipped to passing tests.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-27T03:38:58Z
- **Completed:** 2026-04-27T03:45:49Z
- **Tasks:** 2 (Task 1 presenter + Task 2 tests)
- **Files modified:** 3 (1 presenter created, 1 test rewritten, 1 SUMMARY created)

## Accomplishments

- Created `stonereader/presenters/live_game.py` (395 lines) with `LiveGamePresenter(ZoneNavigationMixin, BasePresenter)` and `OpponentHandRow` frozen-dataclass view shape.
- Subscribed/unsubscribed GameTracker symmetrically in `__init__` / `cleanup()` per D-02.
- Implemented `_on_game_event(event, state)` as the single subscriber entrypoint with strict D-07 silence (zero `self._speech.speak` calls inside this method or its descendants).
- Implemented all 4 zones (`remaining_deck`, `opponent_hand`, `opponent_played`, `cards_drawn` — LIVE-03 per 03-REVIEWS.md HIGH #1) with cursor-per-zone via `_init_navigation([...])`.
- Implemented `_format_item_speech` overrides for all 4 zones with D-13 ("Glacial Shard, 1 copy"), D-14 ("Position 3, identity, drawn turn 5" + lineage variant), D-15 ("Turn 6, Reno Jackson"), and LIVE-03 ("Turn 3, Fireball, drawn") formats.
- Added `drawn_turn == -1` -> "drawn turn unknown" fallback per 03-REVIEWS.md MEDIUM #5.
- Implemented all 8 public accessors per 03-REVIEWS.md HIGH #3: `current_title()`, `cursor_for_zone()`, `detected_deck_name()`, `current_state_snapshot()`, `current_mana_summary()`, `announce_opponent_hand_count()`, `announce_deck_counts()`, `jump_to_zone()`.
- Implemented auto-deck-detection (`_run_auto_detection`): runs once when `player_deck` reveals 30 cards, strict multiset match against `get_all_decks(self._db_conn)`; resets per `GameStarted`; skipped for `BATTLEGROUNDS` / `ARENA`.
- Implemented 10-key `get_key_map()` per 03-UI-SPEC §"Keyboard Contract" (left/right/up/down/home/end + number keys 1/2/3/4 for zone switching per 03-CHECKER blocker #1).
- Replaced all 19 Wave 0 `pytest.xfail()` stub bodies in `tests/test_live_game_presenter.py` with real assertions; dropped file-level `pytestmark = pytest.mark.xfail` marker.
- All 19 tests pass green; full suite goes from 256 passed / 24 xfailed (after 03-03) to 275 passed / 5 xfailed (only the still-stubbed 03-06 panel/wiring tests remain xfail).
- Pre-existing tests unaffected (no regressions).
- `uv run ruff check` + `uv run pyright` both clean for the new presenter and the rewritten test file.
- Presenter is wx-free and hslog-free (D-10 boundary preserved — same module reusable in Phase 4 replays).

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor protocol):

1. **Task 1: Create LiveGamePresenter** — `6948d9a` (feat)
2. **Task 2: Implement 19 LiveGamePresenter tests** — `1d70b36` (test)

**Plan metadata commit:** pending (created with this SUMMARY).

## Files Created/Modified

- `stonereader/presenters/live_game.py` — Created. 395 lines. `LiveGamePresenter` + `OpponentHandRow` + 4 zone constants + `_NON_CONSTRUCTED_GAME_TYPES` + `_ZONE_LABELS` mapping.
- `tests/test_live_game_presenter.py` — Modified (Wave 0 stubs replaced). 748 insertions / 165 deletions. 19 real test bodies + helper functions (`_make_card`, `_make_card_db`, `_make_db`, `_make_state`, `_make_entity`, `_make_opponent_hand_entity`, `_make_presenter`, `_make_legal_deck_30`).
- `.planning/phases/03-live-game-tracking/03-05-SUMMARY.md` — Created (this file).

## Decisions Made

- **OpponentHandRow lives in `live_game.py`** rather than being promoted to `stonereader/models/`. It's a pure presenter-layer view shape — adapting engine `GameEntity` snapshots into D-14 row data — and is never consumed outside the presenter. Promoting it would expose presenter-internal concerns through the model surface.
- **Number-key zone-switch order matches 03-UI-SPEC display order** (1=remaining_deck, 2=opponent_played, 3=opponent_hand, 4=cards_drawn). The order intentionally separates the two opponent zones (positions 2 and 3 — "what they did" vs "what they hold") so users can move between them with adjacent keys.
- **`test_detection_resets_per_game` reads private fields explicitly**. Per the test docstring, this is the rare test that must check internal state — `_detection_attempted` is the "we tried at the threshold" flag with no public accessor (it's not user-facing, only internal logic). Documented as deliberate exception to the HIGH #3 public-only-access rule.
- **`FormatType.FT_STANDARD` enum value** instead of raw int `2` for `write_deckstring()` in tests. Matches the established `test_deck.py:61` pattern and fixes 2 pyright `reportArgumentType` errors that the plan's verbatim test code would have produced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Hygiene] Removed unused `GameEntity` import in live_game.py**
- **Found during:** Task 1 verification (`uv run ruff check stonereader/presenters/live_game.py`)
- **Issue:** The plan's verbatim module skeleton imported `GameEntity` from `stonereader.models.game_state`, but `GameEntity` is not referenced anywhere in the presenter — `OpponentHandRow.identity` is typed as `Optional[Card]` (the `base_card` extracted from the entity), not `Optional[GameEntity]`. Ruff F401 flagged the unused import.
- **Fix:** Changed `from stonereader.models.game_state import GameEntity, GameState, PlayedCard` to `from stonereader.models.game_state import GameState, PlayedCard`.
- **Files modified:** `stonereader/presenters/live_game.py`
- **Verification:** `uv run ruff check stonereader/presenters/live_game.py` exits 0.
- **Committed in:** `6948d9a` (Task 1 commit, applied before commit).

**2. [Rule 1 - Type correctness] Use `FormatType.FT_STANDARD` instead of raw int `2` in `write_deckstring()` calls**
- **Found during:** Task 2 verification (`uv run pyright tests/test_live_game_presenter.py`)
- **Issue:** The plan's verbatim test code passes `2` as the `format` argument to `write_deckstring(cards, heroes, format)`. Pyright correctly flags this with 2 `reportArgumentType` errors because hslog's deckstrings module types the argument as `FormatType` (an enum), not `int`. The runtime accepts either, but the codebase already uses the enum form (see `test_deck.py:61`). Passing the bare int silently fails type checking and is a CLAUDE.md style violation (Type-annotated parameters and return values throughout (Python 3.12+)).
- **Fix:** Added `from hearthstone.enums import FormatType` to both `test_drawn_to_zero_visible` and `test_auto_deck_detection`, and changed both `write_deckstring(cards_data, [637], 2)` calls to `write_deckstring(cards_data, [637], FormatType.FT_STANDARD)`.
- **Files modified:** `tests/test_live_game_presenter.py`
- **Verification:** `uv run pyright tests/test_live_game_presenter.py` reports `0 errors, 0 warnings`. Both affected tests still pass.
- **Committed in:** `1d70b36` (Task 2 commit, applied before commit).

**3. [Rule 2 - Test hygiene] Added `assert presenter is not None` lines in `test_lifecycle_silence` and `test_silent_during_event`**
- **Found during:** Task 2 implementation
- **Issue:** Both tests construct `presenter` only for its side-effect of subscribing to the tracker. Without a reference to it in the test body, lint tools could flag it as an unused local. Adding a trivial assert line keeps the local "live" without changing test semantics, and documents the side-effect-only construction.
- **Fix:** Added `assert presenter is not None` at the end of both tests.
- **Files modified:** `tests/test_live_game_presenter.py`
- **Verification:** Both tests still pass; no ruff/pyright warnings.
- **Committed in:** `1d70b36` (Task 2 commit).

---

**Total deviations:** 3 auto-fixed (1 hygiene, 1 type-correctness, 1 test hygiene). All discovered during the per-task verification cycle and fixed before commit. No scope creep — all three are corrections to the plan's verbatim code that pass ruff + pyright as the project standard requires.

**Impact on plan:** None to scope or design. Deviations 1 and 2 would have failed the plan's own automated verification (`uv run ruff check` and `uv run pyright`). Deviation 3 is a no-op test improvement.

## Issues Encountered

None beyond the deviations above. The plan's pre-flight reading (Wave 0 stubs, presenter base, GameTracker contract, GameState shape, tests/conftest fixtures) gave a clean execution path.

## Threat Flags

None. The implementation matches every threat in the plan's `<threat_model>`:

- **T-03-LIVE-01** (auto-detect mis-attribution): mitigated by D-11 strict-match — `len(matches) == 1` else `_detected_deck_name = None`. `test_auto_deck_detection` regression-locks all three branches (0/1/2+) with legal Hearthstone deck composition.
- **T-03-LIVE-02** (malformed deckstring DoS): mitigated by `try/except Exception` around `Deck.from_deckstring(...)` in `_run_auto_detection`; combined with `allow_unknown=True` for graceful-degrade of newer expansions.
- **T-03-LIVE-03** (stale detection across games): mitigated by Pitfall 6 reset — every `GameStarted` clears `_detected_deck_name`, `_detection_attempted`, `_original_deck_cards`, and zeros every `_zone_cursors` entry. `test_detection_resets_per_game` regression-locks.
- **T-03-LIVE-04** (subscriber-raise DoS): inherited from production GameTracker._dispatch's exception-isolation contract (Phase 2 Pitfall 3). The presenter's `_on_game_event` is small, side-effect-free except `_notify_view`, and never raises in normal flows.

ASVS L1 V11 (business logic) explicitly covered.

## Known Stubs

None. The presenter is fully wired:
- All 4 zones return real data from `_current_state` (no hardcoded empty lists in production paths — only the `_current_state is None` baseline returns `[]`, which is correct per D-08).
- All public accessors return real values from cached state.
- Auto-detection actually queries `get_all_decks(self._db_conn)` and parses each deckstring with `Deck.from_deckstring(...)`.

## User Setup Required

None — the plan touched presenter and tests only; no new dependencies, config files, or external services. No new ports, no new env vars.

## Next Phase Readiness

- **Plan 03-06 (LiveGamePanel + app wiring):** can now construct `LiveGamePresenter(speech, db_conn, tracker, card_db)`. The 8 public accessors give the panel everything it needs without reading private fields. Title updates flow via `set_on_title_changed(callback)`; row-render updates via `set_on_state_changed(callback)`. Hotkey handlers call `presenter.announce_deck_counts()`, `presenter.announce_opponent_hand_count()`, `presenter.jump_to_zone(zone_name)` directly. `cleanup()` symmetrically unsubscribes on tab close.
- **Phase 4 (Replay viewer):** the presenter is wx-free and hslog-free (D-10), so the same zone-navigation + speech-format machinery can be reused for replay panels — only the GameTracker substitute would change (replay engine driving events instead of live Power.log tail).

## Self-Check: PASSED

Verified files and commits exist on disk and in git history:

- `stonereader/presenters/live_game.py` — FOUND (395 lines; `class LiveGamePresenter(ZoneNavigationMixin, BasePresenter)` + `class OpponentHandRow` + `_CARDS_DRAWN_ZONE = "cards_drawn"` + all 8 public accessors present)
- `tests/test_live_game_presenter.py` — FOUND (19 named test functions; no `pytestmark = pytest.mark.xfail`; `_make_legal_deck_30` helper present; `FormatType.FT_STANDARD` used)
- `.planning/phases/03-live-game-tracking/03-05-SUMMARY.md` — FOUND (this file)
- Commit `6948d9a` — FOUND (Task 1: LiveGamePresenter creation)
- Commit `1d70b36` — FOUND (Task 2: 19 tests implementation)

Plan-level verification:
- `uv run pytest tests/test_live_game_presenter.py -v` -> 19 passed
- `uv run pytest tests/ -q` -> 275 passed, 5 xfailed (only still-stubbed plan 03-06 panel/wiring tests remain xfail)
- `uv run ruff check stonereader/presenters/live_game.py tests/test_live_game_presenter.py` -> All checks passed
- `uv run pyright stonereader/presenters/live_game.py` -> 0 errors, 0 warnings, 0 informations
- `grep -c "import wx\|from wx" stonereader/presenters/live_game.py` -> 0 (wx-free contract preserved)
- `awk '/def _on_game_event/,/def [a-z_]/{print}' stonereader/presenters/live_game.py | grep -c "self._speech.speak"` -> 0 (D-07 silent-during-event preserved)
- `grep -c '"1": lambda\|"2": lambda\|"3": lambda\|"4": lambda' stonereader/presenters/live_game.py` -> 4 (all number-key zone switches per CHECKER #1)

---
*Phase: 03-live-game-tracking*
*Completed: 2026-04-27*
