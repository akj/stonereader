# Phase 03 Deferred Items

Out-of-scope discoveries logged during plan execution. Each entry includes the
discovering plan, the symptom, evidence the issue is pre-existing, and a
recommended owner.

---

## D-DEFER-01: wx test-ordering fragility breaks tests/test_navigation.py

**Discovered during:** Plan 03-04 execution (worktree run, 2026-04-27).

**Symptom:** When any test that constructs a real `wx.App()` + `wx.Frame(None)`
runs *before* `tests/test_navigation.py` in the same pytest session, ~29 of the
36 navigation tests fail with errors that include `wx....` (PyAssertionError /
wxAssertionError variants typical of a corrupted wx event loop).

In isolation, every navigation test passes. The order
`tests/test_navigation.py tests/test_global_hotkey.py` → all 36 + 5 pass.
The reverse order → 29 navigation failures.

**Pre-existing — not caused by 03-04:** Reproducible with the existing wx-using
test added before plan 03-04:

```bash
uv run pytest tests/test_services/test_tracker.py::test_start_stop_clean \
              tests/test_navigation.py -q
# → 29 navigation failures, identical to running my hotkey tests first.
```

That existing test predates this plan, so the plan's new tests merely surface
the same latent problem.

**Likely root cause:** Multiple `wx.App()` instances per pytest session leak
GUI state (the navigation tests use `app = wx.App()` per test as well). The
canonical fix is a session-scoped wx app fixture in `tests/conftest.py` (or
`tests/test_navigation.py`'s fixture) that holds a single `wx.App` for the
whole run. Out of scope for plan 03-04.

**Recommended owner:** A future test-infrastructure plan (or plan 03-06 when
it adds further wx-bound presenter tests).

**Workaround until fixed:** Run `tests/test_navigation.py` before any other
wx-using suite, or run navigation tests in their own pytest invocation.

---

## D-DEFER-02: pre-existing ruff F401 unused-import warnings in test files

**Discovered during:** Plan 03-06 final verification (`uv run ruff check stonereader/ tests/`).

**Symptom:** 6 ruff F401 errors across 4 test files I did not modify in 03-06:

- `tests/test_deck_manager.py:7,9` — `get_all_decks`, `DeckSummary` unused
- `tests/test_services/test_events.py:6` — `pytest` unused
- `tests/test_services/test_log_config.py:62,63` — `stat`, `MagicMock` unused
- `tests/test_services/test_parser.py:6` — `pytest` unused

**Pre-existing — not caused by 03-06:** Last touched in `e0e7a1b feat(03-02)`,
`5901b33 fix(02)`, `d8af4ae chore: merge executor worktree (02-04 data layer)` —
all before plan 03-06.

**Recommended owner:** A future test-cleanup pass; trivially fixable with
`uv run ruff check --fix tests/` but explicitly out of scope per the Scope
Boundary rule (file changes unrelated to plan 03-06's work).

**Pyright:** Pyright scoped to `stonereader/` is clean (0 errors). Whole-tree
`uv run pyright` reports 12 errors in `tests/test_services/test_exceptions_packets.py`
which are also pre-existing and out of scope.
