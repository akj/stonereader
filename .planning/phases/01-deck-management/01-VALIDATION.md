---
phase: 1
slug: deck-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | pyproject.toml (implicit) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DECK-01 | — | N/A | unit | `uv run pytest tests/test_import_deck.py -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | DECK-01 | — | N/A | unit | `uv run pytest tests/test_import_deck.py::test_invalid_deckstring -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | DECK-01 | — | N/A | unit | `uv run pytest tests/test_import_deck.py::test_empty_name_rejected -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | DECK-02 | — | N/A | unit | `uv run pytest tests/test_deck_manager.py -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | DECK-02 | — | N/A | unit | `uv run pytest tests/test_deck_manager.py::test_speech_format -x` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 1 | DECK-02 | — | N/A | unit | `uv run pytest tests/test_deck_manager.py::test_sort_order -x` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 1 | DECK-03 | — | N/A | unit | `uv run pytest tests/test_deck_contents.py -x` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 1 | DECK-03 | — | N/A | unit | `uv run pytest tests/test_deck_contents.py::test_metadata_announced -x` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 1 | DECK-04 | — | N/A | unit | `uv run pytest tests/test_deck_manager.py::test_delete_deck -x` | ❌ W0 | ⬜ pending |
| 01-04-02 | 04 | 1 | DECK-04 | — | N/A | unit | `uv run pytest tests/test_deck_manager.py::test_cursor_after_delete -x` | ❌ W0 | ⬜ pending |
| 01-05-01 | 05 | 1 | DECK-05 | — | N/A | unit | `uv run pytest tests/test_deck_manager.py::test_export_deckstring -x` | ❌ W0 | ⬜ pending |
| 01-nav-01 | — | 1 | N/A | — | N/A | unit | `uv run pytest tests/test_navigation.py -x` | ❌ W0 | ⬜ pending |
| 01-home-01 | — | 1 | N/A | — | N/A | unit | `uv run pytest tests/test_home.py -x` | ❌ W0 | ⬜ pending |
| 01-db-01 | — | 1 | N/A | — | Parameterized queries | unit | `uv run pytest tests/test_db.py -x` | ✅ extend | ⬜ pending |
| 01-input-01 | — | 1 | N/A | — | N/A | unit | `uv run pytest tests/test_input_layer.py -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_deck_manager.py` — stubs for DECK-02, DECK-04, DECK-05
- [ ] `tests/test_deck_contents.py` — stubs for DECK-03
- [ ] `tests/test_import_deck.py` — stubs for DECK-01
- [ ] `tests/test_home.py` — stubs for home screen navigation
- [ ] `tests/test_navigation.py` — stubs for NavigationController panel swap
- [ ] Extend `tests/test_db.py` with CRUD function tests (save_deck, get_all_decks, delete_deck)
- [ ] Extend `tests/test_input_layer.py` with WXK_DELETE key spec test

*Existing infrastructure covers test framework and fixtures (conftest.py has MockSpeechService).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Screen reader announces deck list items | DECK-02 | Requires NVDA/JAWS running | 1. Open app with NVDA active 2. Navigate to Deck Manager 3. Arrow through deck list 4. Verify speech reads "Name, Class, Format, N of M" |
| Modal dialogs auto-read by screen reader | DECK-04 | Requires NVDA/JAWS running | 1. Select a deck 2. Press Delete key 3. Verify NVDA reads dialog content automatically |
| Clipboard auto-detection dialog appears | DECK-01 | Requires manual clipboard interaction | 1. Copy a deckstring to clipboard 2. Alt-tab to StoneReader 3. Verify import dialog appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
