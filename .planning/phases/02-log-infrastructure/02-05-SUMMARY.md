---
phase: 02-log-infrastructure
plan: "05"
subsystem: services
tags: [parser, hslog, isolation, packets, exceptions, tdd, d-10]
dependency_graph:
  requires: [02-01]
  provides: [stonereader.services._exceptions, stonereader.services._packets, stonereader.services._parser]
  affects: [02-06, 02-07, 02-08]
tech_stack:
  added: []
  patterns:
    - "Object-identity set (_seen_ids) for append-only packet tree walk"
    - "Log-once cache (_missing_enums_logged) for NoSuchEnum per Pitfall 6"
    - "Tags-as-tuples translation: hslog list-of-tuples -> str-keyed dict"
key_files:
  created:
    - stonereader/services/_exceptions.py
    - stonereader/services/_packets.py
    - stonereader/services/_parser.py
    - tests/test_services/test_exceptions_packets.py
  modified:
    - tests/test_services/test_parser.py
decisions:
  - "NoSuchEnum(enum, value) requires two args — not one as shown in plan template; tests fixed accordingly"
  - "hslog Block uses .suboption/.target (not .sub_option/.target_id) — _translate uses correct attribute names"
  - "hslog tags stored as list of (GameTag, value) tuples, not dict — _tags_to_dict handles conversion"
  - "HideEntity.zone is a Zone enum object, not int — _enum_to_int() handles both cases"
  - "Player.entity (not .entity_id) holds EntityID — CreateGamePacket translation corrected"
  - "D-10: grep -lr matches docstring text; actual import-line checks confirm only _parser.py imports hslog"
metrics:
  duration: "~20 minutes"
  completed: "2026-04-26"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
  tests_added: 20
  tests_passing: 20
---

# Phase 02 Plan 05: hslog Parser Wrapper Summary

**One-liner:** Frozen-dataclass Packet discriminated union + hslog.LogParser wrapper with D-10 isolation, Pitfall-6 NoSuchEnum log-once cache, and append-only packet tree walk via object-identity set.

## What Was Built

Three new files in `stonereader/services/` implementing the hslog isolation layer (D-10):

**`_exceptions.py`** (27 lines): `ServicesError` base + `ParserError` + `EngineError`. Callers catch these symbols instead of hslog exceptions.

**`_packets.py`** (93 lines): Nine frozen dataclasses — `Packet` base plus `CreateGamePacket`, `TagChangePacket`, `BlockStartPacket`, `BlockEndPacket`, `FullEntityPacket`, `ShowEntityPacket`, `HideEntityPacket`, `ChangeEntityPacket`. Engine consumes these; never `hslog.packets.*`.

**`_parser.py`** (245 lines): `Parser` class wrapping `LogParser`. `feed_line(line)` returns `list[Packet]`. Uses object-identity set (`_seen_ids`) to walk an append-only packet tree and emit only new packets. `reset()` constructs a fresh `LogParser` + clears state. Handles all hslog exceptions per threat model T-2-PARSE, T-2-DRIFT, T-2-RESET.

**Tests added:**
- `tests/test_services/test_exceptions_packets.py` (16 tests): exception hierarchy, frozen dataclass properties, field validation, D-10 import checks
- `tests/test_services/test_parser.py` (4 tests): PowerTaskList drop, CreateGamePacket translation, NoSuchEnum catch+log, log-once cache

## File Paths and Line Counts

| File | Lines | Role |
|------|-------|------|
| `stonereader/services/_exceptions.py` | 27 | Typed exception hierarchy |
| `stonereader/services/_packets.py` | 93 | Internal Packet discriminated union |
| `stonereader/services/_parser.py` | 245 | hslog wrapper + translator |
| `tests/test_services/test_exceptions_packets.py` | 186 | 16 tests for exceptions + packets |
| `tests/test_services/test_parser.py` | 79 | 4 tests for parser (stubs converted) |

## Test Pass Count

20 tests added, 20 passing. Full suite: 210 passed, 14 skipped (stubs from future plans).

## D-10 Isolation Confirmation

```
grep -rn "^from hslog\|^import hslog" stonereader/
```
Returns exactly: `stonereader/services/_parser.py` lines 11-13.

No other `stonereader/` file has hslog import statements. (The `grep -lr` command in the plan acceptance criteria matches docstring text in `_packets.py` — that is a false positive from the plan's grep; the actual import-line check confirms D-10 is enforced.)

## hslog Version-Specific Attribute Access Fallbacks

During implementation, several hslog 1.18.0 attribute names differed from the plan template:

| hslog object | Plan assumed | Actual attribute | Fix applied |
|---|---|---|---|
| `Player` | `.entity_id` | `.entity` | `getattr(p, "entity", 0)` |
| `Block` | `.sub_option` | `.suboption` | `getattr(hp, "suboption", None)` |
| `Block` | `.target_id` | `.target` | `getattr(hp, "target", None)` |
| `FullEntity/ShowEntity.tags` | `dict` | `list[tuple]` | `_tags_to_dict()` converts |
| `HideEntity.zone` | `int` | `Zone` enum | `_enum_to_int()` handles both |
| `TagChange.tag` | enum name | enum object | `_tag_name()` returns `.name` |
| `NoSuchEnum(...)` | 1 arg | 2 args `(enum, value)` | Tests fixed to `NoSuchEnum("GameTag", "UNKNOWN_TAG")` |

All fallbacks use `getattr(..., default)` so the parser degrades gracefully if hslog changes attribute names in future versions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] NoSuchEnum constructor requires 2 arguments**
- **Found during:** Task 2 GREEN (test failure)
- **Issue:** `NoSuchEnum("UNKNOWN_TAG")` raises `TypeError: missing 1 required positional argument: 'value'` — actual signature is `NoSuchEnum(enum, value)`
- **Fix:** Updated both test instances to `NoSuchEnum("GameTag", "UNKNOWN_TAG")`
- **Files modified:** `tests/test_services/test_parser.py`
- **Commit:** df35ca7 (included in GREEN commit)

**2. [Rule 1 - Bug] hslog uses `.suboption`/`.target` not `.sub_option`/`.target_id` on Block**
- **Found during:** Task 2 implementation (verified via `uv run python` inspection)
- **Fix:** `_translate` uses `getattr(hp, "suboption", None)` and `getattr(hp, "target", None)`
- **Files modified:** `stonereader/services/_parser.py`

**3. [Rule 1 - Bug] hslog tags stored as list-of-tuples, not dict**
- **Found during:** Task 2 implementation
- **Fix:** Added `_tags_to_dict()` static method to convert `[(GameTag, value), ...]` → `{str: int}`
- **Files modified:** `stonereader/services/_parser.py`

**4. [Rule 1 - Bug] D-10 test checked docstring text for "from hslog"**
- **Found during:** Task 1 GREEN test run
- **Fix:** Updated `test_no_hslog_import_in_packets` to check only lines starting with `import`/`from`
- **Files modified:** `tests/test_services/test_exceptions_packets.py`

## TDD Gate Compliance

RED gate commits: `0c2f5e5` (exceptions/packets tests), `ef1fafd` (parser tests)
GREEN gate commits: `65dbe6f` (exceptions/packets implementation), `df35ca7` (parser implementation)

Gate sequence: RED → GREEN → RED → GREEN (two tasks, two cycles). No REFACTOR phase needed.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All threat model items (T-2-PARSE, T-2-DRIFT, T-2-RESET) are addressed:
- T-2-PARSE: all hslog exceptions caught in `feed_line`, bare `except Exception` as outermost guard
- T-2-DRIFT: `_missing_enums_logged` set logs NoSuchEnum once per unique `(enum, value)` pair
- T-2-RESET: `reset()` constructs new `LogParser` and clears `_seen_ids` + `_next_packet_id`

## Known Stubs

None. All packet types are fully implemented and translatable. The engine (Plan 06) will consume these packets; that wiring is Plan 06's scope, not a stub in this plan.

## Self-Check: PASSED

All files verified present:
- stonereader/services/_exceptions.py: FOUND
- stonereader/services/_packets.py: FOUND
- stonereader/services/_parser.py: FOUND
- tests/test_services/test_exceptions_packets.py: FOUND
- .planning/phases/02-log-infrastructure/02-05-SUMMARY.md: FOUND

All commits verified present:
- 0c2f5e5 (RED: exceptions/packets tests): FOUND
- 65dbe6f (GREEN: exceptions/packets impl): FOUND
- ef1fafd (RED: parser tests): FOUND
- df35ca7 (GREEN: parser impl): FOUND
