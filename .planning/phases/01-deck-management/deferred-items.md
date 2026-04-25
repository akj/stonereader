# Deferred Items -- Phase 01 Deck Management

Out-of-scope discoveries logged during plan execution per the executor scope-boundary protocol. These are NOT fixed inline because they were not directly caused by the current plan's changes.

## From 01-06-PLAN (transient-panel concept)

### F401 unused imports in tests/test_deck_manager.py (pre-existing)

- **Discovered:** 2026-04-25 during 01-06 final verification
- **File:** `tests/test_deck_manager.py:7` and `tests/test_deck_manager.py:9`
- **Issue:** Two unused imports flagged by ruff:
  - `stonereader.db.get_all_decks` -- imported but never referenced
  - `stonereader.models.deck.DeckSummary` -- imported but never referenced
- **Pre-existing:** Confirmed by checking out the file at base commit `b407306` -- both errors reproduce there. Not caused by 01-06 changes.
- **Plan scope:** 01-06 verification step 3 explicitly scopes ruff to `stonereader/app.py` and `tests/test_navigation.py`; both of those are clean.
- **Suggested fix:** Trivial -- run `uv run ruff check tests/test_deck_manager.py --fix`. Should be addressed in a separate hygiene commit, not as part of a feature plan.
