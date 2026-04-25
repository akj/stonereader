# Phase 2: Log Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 02-log-infrastructure
**Areas discussed:** Threading model, Output interface, hslog adoption, Bootstrap (log.config + path + startup), Module location, Buffer/memory caps, Logging rollout, Testing fixtures, Models library (attrs vs dataclasses)

---

## Threading Model

### Q1 — Threading model for the log watcher

| Option | Description | Selected |
|--------|-------------|----------|
| wx.Timer on GUI thread | 150ms wx.Timer ticks on GUI thread. No locks, no wx.CallAfter. Matches HDT/Firestone. | ✓ |
| threading.Thread + wx.CallAfter | Dedicated background thread, events posted via wx.CallAfter. Literal LOG-05. | |
| Threaded watcher, Timer parser | Hybrid: thread reads bytes, Timer drains queue + parses on GUI thread. | |

**User's choice:** wx.Timer on GUI thread (Recommended)
**Notes:** LOG-05 reinterpreted as "doesn't block UI" (D-19) since per-tick reads are microseconds. Reads HDT/Firestone behavior.

### Q2 — How the watcher signals events

| Option | Description | Selected |
|--------|-------------|----------|
| Direct callback (subscriber list) | `subscribe(callback)`. No wx coupling. Reusable by Phase 4. | ✓ |
| wx.PostEvent (custom wx.PyEvent) | Custom wx events to a target window. Idiomatic wx but ties services/ to wx. | |
| queue.Queue + drain on Timer | Useful if threaded; overkill for GUI-thread Timer. | |

**User's choice:** Direct callback (Recommended)
**Notes:** Mirrors existing `_notify_view()` callback pattern.

### Q3 — Watcher start/stop lifecycle (asked twice — research clarification)

**First pass:**
| Option | Selected |
|--------|----------|
| Always-on after app launch | (asked: leaning 1, want HDT/Firestone research) |
| User-toggled via menu/hotkey | |
| Auto-start on Hearthstone process detection | |

**User asked:** "how do other games handle this? I'm thinking 1, but maybe 3 is better?"
**Research provided:** HDT and Firestone both use process detection (option 3) — avoids replaying stale logs from old sessions, cleanly handles missing log file, lets them show "waiting for Hearthstone" UI.

**Second pass (with context):**
| Option | Description | Selected |
|--------|-------------|----------|
| Always-on with stale-log guard | wx.Timer at launch, jump to EOF on first tick. No process detection. | |
| Auto-start on Hearthstone process detection | psutil/win32api process check. Matches HDT/Firestone exactly. | ✓ |
| Always-on, replay full file | Read whole Power.log on launch. Wasteful. | |

**User's choice:** Auto-start on Hearthstone process detection
**Notes:** Matches industry pattern. Adds a process detection layer (D-03).

### Q4 — Tick error handling

| Option | Description | Selected |
|--------|-------------|----------|
| Catch + log + keep ticking | Single failure logged, watcher continues. | ✓ |
| Catch + log + retry with backoff | 150ms → 1s → 5s on repeated failures. | |
| Bubble up, let app crash | Fail loudly. Bad for users. | |

**User's choice:** Catch + log + keep ticking (Recommended)
**Notes:** Backoff deferred — revisit if real-world noise demands it.

---

## Output Interface to Phase 3

### Q5 — What does Phase 2 emit (asked twice — research request)

**First pass:**
| Option | Selected |
|--------|----------|
| GameState snapshots + typed events | (asked: thinking 1, but research other trackers) |
| Typed events only | |
| hslog packets / PacketTree | |
| Raw lines | |

**User asked:** "thinking 1, but research other trackers"
**Research provided:**
- HDT uses `GameEvents` static class (typed events) + long-lived `Game` object (UI polls on demand). UI subscribes to events, reads `Game.Player.Hand`, etc.
- Firestone emits typed `GameEvent`s + maintains `GameState` (Redux-style). UI components subscribe to events AND read from GameState.
- Both use option 1.

**Second pass (with context):**
| Option | Description | Selected |
|--------|-------------|----------|
| Yes — lock option 1 | Snapshots + typed events (HDT/Firestone pattern). | ✓ |
| Yes, but events-only | Phase 3 builds its own GameState. Adds duplication. | |
| Need more info | Free text in Other. | |

**User's choice:** Yes — lock option 1 (Recommended)
**Notes:** Events drive announcements, snapshots drive hotkey queries.

### Q6 — Event categories to emit

| Option | Description | Selected |
|--------|-------------|----------|
| Game lifecycle (GameStarted, GameEnded) | CREATE_GAME / TAG_CHANGE STATE=COMPLETE | ✓ |
| Turn lifecycle (TurnChanged, MulliganDone) | CURRENT_PLAYER, MULLIGAN_STATE tags | ✓ |
| Card movement (CardDrawn, CardPlayed, CardRevealed, CardRemoved) | ZONE TAG_CHANGEs, SHOW_ENTITY | ✓ |
| Combat (AttackStarted, MinionDied, DamageDealt) | BLOCK_START ATTACK/DEATHS, HEALTH/DAMAGE | ✓ |

**User's choice:** All four (multiSelect)
**Notes:** Combat events go beyond v1 LIVE-* but unblock Phase 4 REPLAY-05 drill-down.

### Q7 — GameState immutability

| Option | Description | Selected |
|--------|-------------|----------|
| New frozen GameState per change | Construct new instance per relevant event. | ✓ |
| Mutable internal, frozen on demand | Working state mutable, snapshot frozen on request. Breaks "never mutate" rule. | |
| Snapshot only on game end | Doesn't fit live tracking. | |

**User's choice:** New frozen GameState per change (Recommended)
**Notes:** Enforces project's "never mutate" rule.

---

## hslog Adoption

### Q8 — Parsing strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt hslog now, hsreplay later | hslog dep this phase. hsreplay → Phase 4. | ✓ |
| Adopt both hslog + hsreplay now | Both deps in Phase 2 even though hsreplay unused. | |
| Roll our own regex parser | No hslog dep. Real engineering + per-patch maintenance. | |

**User's choice:** Adopt hslog now, hsreplay later (Recommended)
**Notes:** STATE.md was wrong — hslog is NOT installed transitively.

### Q9 — Coupling between engine and hslog

| Option | Description | Selected |
|--------|-------------|----------|
| Use hslog only in parser; engine talks our types | parser.py wraps hslog; engine never imports hslog. | ✓ |
| Re-export hslog packets as public API | Subscribers see hslog.PacketTree. Locks downstream forever. | |

**User's choice:** Use hslog only inside parser (Recommended)
**Notes:** Allows future parser swap without breaking subscribers.

---

## Bootstrap (log.config + path + startup)

### Q10 — log.config bootstrap

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-create silently | Idempotent merge of [Power] keys on first run. | ✓ |
| Prompt user before creating/modifying | wx.MessageDialog confirmation. | |
| Require manual setup | Surface error if absent. Highest friction. | |

**User's choice:** Auto-create silently (Recommended)
**Notes:** Speaks one-line confirmation if newly created.

### Q11 — Power.log path discovery (asked twice — research request + conflict concern)

**First pass:**
| Option | Selected |
|--------|----------|
| Pick newest Logs/ subdirectory + fall back to Logs/Power.log | |
| Detect process and use directory it has open | (asked: appealing but worried about conflicts) |
| User-configurable path only | |

**User asked:** "how do hdt and firestone do this? 2 sounds appealing but may conflict with other strategies we agreed to earlier"
**Research provided:**
- HDT: `Process.GetProcessesByName` (which we already use for auto-start) → derives Logs dir from `Process.MainModule.FileName` → newest `Hearthstone_*` subdirectory by mtime. **No** `handle.exe` / locked-handle detection.
- Firestone: HKLM\SOFTWARE\Blizzard\Hearthstone registry → newest subdirectory by mtime. Also no locked-handle.
- Clarification: "process detection" (we have for D-03) and "locked-handle path detection" are different things. Latter needs Sysinternals `handle.exe` or Win32 `NtQuerySystemInformation`.

**Second pass:**
| Option | Description | Selected |
|--------|-------------|----------|
| Newest Logs/ subdir + registry/process-path fallback | HKLM registry or running .exe path → newest subdir by mtime. | ✓ |
| Default install paths only, no registry | Hardcoded. Breaks on custom installs. | |
| User-configurable with discovery fallback | More work, escape hatch for non-standard installs. | |

**User's choice:** Newest Logs/ subdir + registry/process-path fallback (Recommended)
**Notes:** Matches HDT + Firestone exactly. No new tooling beyond stdlib + winreg.

### Q12 — Startup read position

| Option | Description | Selected |
|--------|-------------|----------|
| Backward-scan to current CREATE_GAME or EOF | Find latest game boundary, replay from there. Matches HDT. | ✓ |
| Always start from EOF | Misses in-progress game on app restart. | |
| Always read from beginning | Replays everything. Wasteful. | |

**User's choice:** Backward-scan to current CREATE_GAME or EOF (Recommended)

---

## Remaining Items (batch)

### Q13 — Module naming

| Option | Description | Selected |
|--------|-------------|----------|
| stonereader/services/ | Matches roadmap STATE.md. Phases 3+4 join here. | ✓ |
| stonereader/log_parser/ | Matches design spec. Tighter scope, but Phase 3/4 need a new home anyway. | |

**User's choice:** stonereader/services/ (Recommended)

### Q14 — Buffer/memory caps

| Option | Description | Selected |
|--------|-------------|----------|
| Cap raw line buffer at 100K, no packet history cap | HDT precedent. Engine retains only current GameState. | ✓ |
| Cap raw line buffer at 100K, retain last N packets | Small ring buffer for debugging. More memory. | |
| No caps — trust modern memory | OOM risk on multi-hour BG. | |

**User's choice:** Cap raw line buffer at 100K, no packet history cap (Recommended)

### Q15 — Logging system rollout

| Option | Description | Selected |
|--------|-------------|----------|
| Add stdlib logging now, file + console | ~/.stonereader/stonereader.log, INFO default, DEBUG via env var. | ✓ |
| Print to stdout only | No file log for bug reports. | |
| Defer logging to a later phase | Inconsistent with D-04. | |

**User's choice:** Add stdlib logging now (Recommended)
**Notes:** Closes "No Logging System" item in CONCERNS.md.

### Q16 — Testing fixture strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Captured real Power.log fixtures in tests/fixtures/log/ | Hand-capture short games. Anonymize if needed. | ✓ |
| Synthetic minimal logs hand-written | Brittle to format changes. | |
| Both — fixtures + synthetic | More test infra, most coverage. | |

**User's choice:** Captured real Power.log fixtures (Recommended)

### Q17 — GameState extension fields

| Option | Description | Selected |
|--------|-------------|----------|
| Leave to planner | Lock that GameState needs to grow; defer specifics to PLAN.md. | ✓ |
| Lock specific fields now | More work in discussion, less ambiguity downstream. | |
| Skip — extend in Phase 3 | Engine emits using current fields only. | |

**User's choice:** Leave to planner (Recommended)
**Notes:** D-08 records the need; planner researches HDT/Firestone shape.

---

## Models Library (attrs vs dataclasses)

### Q18 — User raised: should we consider attrs?

**User's question:** "considering attrs to handle dataclasses. thoughts? does attrs give us any capability that dataclasses wouldn't?"

**Analysis provided:** For StoneReader specifically, `attrs` adds nothing material:
- Validators/converters: not needed (parser handles coercion).
- `slots=True`: frozen dataclasses support this since Python 3.10 (we're on 3.12).
- `evolve()`: `dataclasses.replace()` is identical.
- Performance: matters at millions of objects, not 30-100 entities/game.
- Cost of attrs: third-party dep, mixes patterns with existing dataclass models, CLAUDE.md rule already locks `@dataclass(frozen=True)`.

| Option | Description | Selected |
|--------|-------------|----------|
| Stick with @dataclass(frozen=True) | No new dep. Consistent. CLAUDE.md rule. | ✓ |
| Switch new Phase 2 engine types to attrs | Mixed pattern across codebase. | |
| Migrate all models to attrs | Real cost, no benefit. | |

**User's choice:** Stick with @dataclass(frozen=True) (Recommended)

---

## Claude's Discretion

- Internal naming inside `services/` (e.g., `PowerLogWatcher` vs `LogWatcher`)
- Exception class hierarchy for parser/engine errors
- `GameStarted` event payload shape (game type, format, deck list, hero classes) — planner researches HDT/Firestone
- Single `GameTracker` facade vs distinct `Watcher`/`Parser`/`Engine` objects
- Logging configuration location (`__main__.py` vs `app.py`) — planner picks
- `psutil` vs `win32api` for process detection — planner picks based on platform-specific code minimization

## Deferred Ideas

- Game-end persistence to SQLite `games` table — Phase 3 or later
- Hot-reload of `log.config` changes — out of scope
- UTF-8 partial-character handling at byte boundaries — implementation detail, planner addresses
- Hearthstone reconnection / spectate mid-game — handled by same boundary logic as fresh start
- Backoff on repeated tick errors — revisit if real-world noise demands
- Specific GameState extension field shapes — planner researches and proposes in PLAN.md
