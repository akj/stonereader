---
phase: 01-deck-management
plan: 05
subsystem: deck-management
tags: [deckstring-import, hearthstone-data, graceful-degrade, error-diagnostics, tdd]

# Dependency graph
requires:
  - phase: 01-deck-management
    provides: ImportDeckPresenter, Deck.from_deckstring strict path, MockSpeechService test fixtures
provides:
  - Deck.from_deckstring(allow_unknown=True) graceful-degrade path with placeholder Card construction
  - MissingCardsError(ValueError) subclass with missing_dbf_ids tuple attribute
  - count_unknown_cards(deck) helper for presenter consumption
  - ImportDeckPresenter._format_missing_cards_message diagnostic formatter
  - Unknown-card-count announcement suffix in import success speech (singular and plural forms)
affects: [01-06-deck-detail, 01-07-deck-management, future hearthstone-data refresh tooling]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Graceful-degrade import: reference-preserving placeholders rather than hard failure"
    - "Typed exception with structured attribute (missing_dbf_ids tuple) instead of error-message string parsing"
    - "Keyword-only flag for opt-in lenient behavior preserves existing strict callers"
    - "Presenter-owned formatting helper (_format_missing_cards_message) so the model stays UI-agnostic"

key-files:
  created:
    - tests/test_deck.py
  modified:
    - stonereader/models/deck.py
    - stonereader/models/__init__.py
    - stonereader/presenters/import_deck.py
    - tests/test_import_deck.py

key-decisions:
  - "MissingCardsError subclasses ValueError so existing `except ValueError` handlers continue to catch the missing-cards path without code churn"
  - "Placeholder Cards have collectible=False so they cannot leak into Card Library search results (mitigates T-01-13)"
  - "allow_unknown is keyword-only to prevent positional callers from accidentally toggling lenient mode"
  - "Persisted deckstring is the original (not the placeholder-rebuilt one) so a future hearthstone-data refresh resolves the unknown cards correctly without data loss"
  - "Singular/plural branching for unknown-card count keeps the speech announcement grammatical"

patterns-established:
  - "Typed-exception-with-structured-attribute: subclass ValueError to expose machine-readable diagnostic data without breaking string-error-path callers"
  - "Graceful-degrade with opt-in keyword flag: default behavior is unchanged; lenient mode is explicit at the call site"
  - "Model owns the placeholder ID convention; presenters consume via count_unknown_cards helper rather than re-implementing the prefix check"

requirements-completed: [DECK-01]

# Metrics
duration: ~10 min
completed: 2026-04-25
---

# Phase 01 Plan 05: UAT Gap 1 — Graceful-Degrade Deckstring Import + DBF Diagnostics Summary

**Deckstring import now succeeds when the bundled card database lags behind the deckstring's expansion, building placeholder Cards for unknown DBF IDs and announcing the unknown count via speech; strict-mode path surfaces specific missing DBF IDs in error text via a new MissingCardsError(ValueError) subclass.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-25T18:47:00Z (approximate, after worktree base reset)
- **Completed:** 2026-04-25T18:57:29Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- Eliminated the dead-end where a single newer DBF ID blocked the entire import: `Deck.from_deckstring(..., allow_unknown=True)` now builds `_make_placeholder_card(dbf_id)` for unresolved IDs, with `id="UNKNOWN_{dbf_id}"`, `name="Unknown card #{dbf_id}"`, `collectible=False`, and zero stats.
- Added `MissingCardsError(ValueError)` exposing `missing_dbf_ids: tuple[int, ...]` so callers can format diagnostic messages without parsing error strings.
- `ImportDeckPresenter.validate_and_import` now uses graceful-degrade by default; the success announcement appends `, {N} unknown cards` (singular: `, 1 unknown card`) when `count_unknown_cards(deck) > 0`, and is unchanged otherwise.
- Strict-mode error message helper `_format_missing_cards_message` lists specific DBF IDs (e.g. `"... (DBF IDs: 99999, 88888). The deck code may be from a newer expansion."`), retained as defense-in-depth in case a future caller bypasses graceful-degrade.
- Added 8 new tests in `tests/test_deck.py` covering the strict path, lenient path, partial resolution, helper count, keyword-only enforcement, and `Card.to_speech_text()` contract preservation.
- Updated `tests/test_import_deck.py` with 4 new tests (known-cards-only suffix omission, singular form, dialog DBF inclusion, empty-tuple fallback) and replaced `test_missing_cards_shows_error` with `test_missing_cards_imports_with_placeholders` to reflect the new graceful behavior.
- Re-exported `MissingCardsError` from `stonereader.models` package surface alongside `Deck` and `DeckSummary`.

## Task Commits

Each task followed the TDD RED → GREEN gate:

1. **Task 1 RED: failing tests for graceful-degrade Deck.from_deckstring** — `4030c71` (test)
2. **Task 1 GREEN: graceful-degrade and diagnostic DBF IDs in Deck.from_deckstring** — `459922f` (feat)
3. **Task 2 RED: updated import-deck tests for graceful-degrade and missing-DBF diagnostics** — `5f4ff46` (test)
4. **Task 2 GREEN: wire graceful-degrade and diagnostics into ImportDeckPresenter** — `3a30f05` (feat)

No REFACTOR commits — both implementations were minimal-correct on first GREEN pass and required no further cleanup beyond automated formatting.

## Files Created/Modified

- `tests/test_deck.py` (created) — 8 tests covering MissingCardsError contract, allow_unknown=True placeholder construction, partial resolution, count helper, keyword-only enforcement, and to_speech_text preservation.
- `stonereader/models/deck.py` (modified) — added `MissingCardsError`, `_make_placeholder_card`, `count_unknown_cards`, and the keyword-only `allow_unknown` parameter on `Deck.from_deckstring`.
- `stonereader/models/__init__.py` (modified) — re-exports `MissingCardsError`.
- `stonereader/presenters/import_deck.py` (modified) — `validate_and_import` calls `Deck.from_deckstring(..., allow_unknown=True)`, adds singular/plural unknown-count speech, retains MissingCardsError except branch as defense-in-depth, adds `_format_missing_cards_message` helper.
- `tests/test_import_deck.py` (modified) — replaced obsolete `test_missing_cards_shows_error` with `test_missing_cards_imports_with_placeholders`; added 4 new tests for the graceful-degrade and diagnostic behaviors.

## Decisions Made

- **MissingCardsError subclasses ValueError, not Exception.** Existing `except ValueError` blocks (including the presenter's own pre-fix `except ValueError`) continue to work; the typed attribute is additive for callers that want it.
- **Placeholder construction goes through Card constructor, not attribute mutation.** Card is a frozen dataclass; the helper passes all fields including required ones (cost=0, attack=None, etc.) so the immutability invariant is preserved.
- **Persist the original deckstring, not a re-encoded one.** `Deck.deckstring = deckstring` (the input). When hearthstone-data is later refreshed, re-loading the saved deckstring will resolve the previously-unknown DBF IDs to real Cards without data migration.
- **Pluralization handled in presenter, not model.** `count_unknown_cards` returns an integer; the presenter formats `"1 unknown card"` vs `"N unknown cards"`. Keeps the model UI-agnostic.
- **`_format_missing_cards_message` lives on the presenter, not the model.** The dialog text includes user-facing context ("The deck code may be from a newer expansion.") that doesn't belong in the model layer.

## Deviations from Plan

None - plan executed exactly as written.

The only minor automated adjustment: `uv run ruff format` reformatted `stonereader/models/deck.py` (collapsed a multi-line `sum(...)` expression into one line) and `stonereader/presenters/import_deck.py` (collapsed the existing `set_on_show_error` signature to one line — pre-existing reformat opportunity, not introduced by this plan). Both reformats are mechanical and were applied as part of the GREEN commits.

## Issues Encountered

None.

## Verification

All commands listed in the plan's `<verification>` section pass:

1. `uv run pytest tests/ -v` → **154 passed** (142 baseline + 12 new/modified tests; 0 regressions)
2. `uv run pytest tests/test_deck.py tests/test_import_deck.py -v` → **21 passed**
3. `uv run ruff check stonereader/models/deck.py stonereader/models/__init__.py stonereader/presenters/import_deck.py tests/test_deck.py tests/test_import_deck.py` → All checks passed
4. `uv run ruff format --check ...` → 5 files already formatted
5. `uv run pyright stonereader/models/deck.py stonereader/presenters/import_deck.py` → 0 errors, 0 warnings, 0 informations
6. Smoke import: `from stonereader.models.deck import Deck, MissingCardsError, count_unknown_cards, _make_placeholder_card` → OK

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- DECK-01 closed; the import flow is unblocked for current-meta deckstrings without requiring a `hearthstone-data` refresh.
- The `count_unknown_cards`/`UNKNOWN_` placeholder convention is a stable contract for plans 06 and 07 (Deck Detail / Deck Management) — those views may want to label placeholder rows distinctly (e.g. "(unknown card from newer expansion)") but no functional changes are required for them to work.
- Future enhancement candidate (out of scope here): add `CardDatabase.refresh()` that fetches latest XML from HearthSim; re-loading saved decks afterward would resolve placeholders to real Cards because the original deckstring is preserved. Explicitly deferred per gap-closure scope (Option B rejected).
- No new security surface introduced beyond what's already documented in the plan's `<threat_model>`. DBF IDs are integers from `parse_deckstring` (already trusted), used only in f-strings (no SQL/HTML/eval), and surfaced in error dialogs (not secret).

## TDD Gate Compliance

Both tasks executed the full RED → GREEN cycle:

- Task 1: `4030c71` (test, RED — `ImportError: cannot import name 'MissingCardsError'` confirmed) → `459922f` (feat, GREEN — 8/8 pass)
- Task 2: `5f4ff46` (test, RED — 4 failing tests confirmed) → `3a30f05` (feat, GREEN — 13/13 pass)

No tests passed unexpectedly during RED; gate sequence is intact.

## Self-Check: PASSED

- File `tests/test_deck.py` exists: FOUND
- File `stonereader/models/deck.py` modified: FOUND (MissingCardsError, allow_unknown, _make_placeholder_card, count_unknown_cards present)
- File `stonereader/presenters/import_deck.py` modified: FOUND (allow_unknown=True, MissingCardsError except branch, _format_missing_cards_message present)
- File `stonereader/models/__init__.py` re-exports MissingCardsError: FOUND
- File `tests/test_import_deck.py` updated with new tests: FOUND
- Commit `4030c71` (Task 1 RED): FOUND in git log
- Commit `459922f` (Task 1 GREEN): FOUND in git log
- Commit `5f4ff46` (Task 2 RED): FOUND in git log
- Commit `3a30f05` (Task 2 GREEN): FOUND in git log

---
*Phase: 01-deck-management*
*Completed: 2026-04-25*
