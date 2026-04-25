# Phase 2: Log Infrastructure - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Headless engine that watches Hearthstone's `Power.log`, parses each line, filters duplicates and resets, and emits a clean stream of game events plus running `GameState` snapshots — all without UI. The output is consumed by Phase 3 (Live Game Tracking) for speech announcements / hotkey queries and reused by Phase 4 (Replay Viewer) for HSReplay XML parsing.

This phase introduces no presenter or view, no user-facing UI elements. Scope ends at the public API of `stonereader.services` (watcher subscribe/unsubscribe + GameState read).

</domain>

<decisions>
## Implementation Decisions

### Threading & Lifecycle

- **D-01:** **wx.Timer at 150ms on the GUI thread** — no `threading.Thread`, no `wx.CallAfter`. Per-tick read is microseconds (a few KB max), so "doesn't block UI" is satisfied without OS threading. Matches HDT and Firestone.
- **D-02:** **Direct subscriber-callback event delivery.** Watcher exposes `subscribe(callback)` / `unsubscribe(callback)`. No wx-specific event posting — keeps `services/` reusable by Phase 4 without a wx context. Matches the existing `_notify_view()` pattern from presenters.
- **D-03:** **Auto-start when `hearthstone.exe` is detected running.** Process detection via `psutil` (or `win32api` if we want to avoid the dep). Watcher idle until process appears; on disappearance, watcher pauses and resets parser state. Matches HDT and Firestone exactly.
- **D-04:** **Tick errors are caught, logged, and the Timer keeps ticking.** Single-tick failure (file gone mid-tick, decode glitch, truncation race) does not kill the watcher. Errors logged via Python `logging` (see D-16). Backoff is *not* added in v1 — keep it simple; revisit if real-world noise demands it.

### Output Contract

- **D-05:** **Engine emits frozen `GameState` snapshots AND typed events.** Same pattern as HDT (`Game` object + `GameEvents` static class) and Firestone (`GameState` + `GameEvent` stream). Events answer "what just happened?" (drives Phase 3 announcements). Snapshots answer "what's the current state?" (drives Phase 3 hotkey queries — LIVE-02..07).
- **D-06:** **Event categories emitted in v1:** Game lifecycle (`GameStarted`, `GameEnded`), Turn lifecycle (`TurnChanged`, `MulliganDone`), Card movement (`CardDrawn`, `CardPlayed`, `CardRevealed`, `CardRemoved`), Combat (`AttackStarted`, `MinionDied`, `DamageDealt`). Combat events go beyond v1 LIVE-* requirements but harvesting them now means Phase 4 replay drill-down (REPLAY-05) gets them for free.
- **D-07:** **New frozen `GameState` per meaningful change.** Engine constructs a new instance whenever a relevant tag/zone/turn/lifecycle event applies. No mutation of existing state. Multiple subscribers share the same immutable snapshot.
- **D-08:** **The existing `stonereader/models/game_state.py` `GameState` will need to grow** to support Phase 3 queries (LIVE-02 player remaining deck, LIVE-03 cards-drawn history, LIVE-04 opponent played-in-order). **Specific field shape and naming is deferred to the planner** — research how HDT/Firestone shape these and propose a concrete diff in PLAN.md.

### Parser Strategy

- **D-09:** **Adopt `hslog` as an explicit dependency this phase. `hsreplay` is deferred to Phase 4.** STATE.md's "transitive install" claim was wrong on verification (`uv run python -c "import hslog"` fails). hslog handles BLOCK regex variations, dormant minions, transforms, hidden entities, FriendlyPlayerExporter logic — all already maintained by HearthSim. Cost of rolling our own = ongoing patch maintenance for no upside.
- **D-10:** **`hslog` is isolated to `parser.py`. The engine and public API never import hslog.** `parser.py` wraps `hslog.LogParser` and emits our own `Packet` / typed event objects. Engine consumes those, never raw `hslog.PacketTree` nodes. Lets us swap the parser later without breaking subscribers.

### Bootstrap

- **D-11:** **Auto-create / idempotently update `log.config` silently on first launch.** Path: `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config` (Windows). Required `[Power]` section keys are written or merged in. No user prompt — Hearthstone logging just works. Speaks one-line confirmation if the file was newly created.
- **D-12:** **Power.log path discovery: newest `Logs/Hearthstone_*/` subdirectory by mtime, with registry / running-process-path fallback.** Strategy:
  1. If `hearthstone.exe` is running, derive install dir from `Process.MainModule.FileName` (the .exe path).
  2. Otherwise read `HKEY_LOCAL_MACHINE\SOFTWARE\Blizzard\Hearthstone` registry via `winreg`.
  3. Within `Logs/`, pick the newest `Hearthstone_YYYY_MM_DD_HH_MM_SS/` subdirectory.
  4. Fall back to `Logs/Power.log` (older Hearthstone format) if no subdirs.
  5. Re-scan when process restarts (Hearthstone restart = new subdirectory).
  No `handle.exe` / locked-file detection — HDT and Firestone don't either.
- **D-13:** **On watcher start, backward-scan to the latest `CREATE_GAME` line.** If a game is already in progress when StoneReader launches (common case: user starts the app mid-match), parse from that boundary forward. If no `CREATE_GAME` is found in the file, jump to EOF and wait. Matches HDT's startup behavior.

### Module & Infrastructure

- **D-14:** **All new code lives under `stonereader/services/`.** Matches the roadmap STATE.md note ("New services/ directory for LogWatcher, GameEngine, GlobalHotkeyService, ReplayEngine"). The April-2026 design spec uses `log_parser/` — that document is overridden here for module location only. Phases 3 and 4 will add `global_hotkey_service.py` and `replay_engine.py` to the same directory.
- **D-15:** **Raw-line buffer capped at 100,000 lines.** Matches HDT's precedent. Prevents unbounded growth in long Battlegrounds sessions. **No packet history retained** — once a packet is applied to `GameState`, the engine discards it. Game-end persistence to SQLite (the `games` table from `db.py`) is *out of scope* for Phase 2 and will be addressed by Phase 3 or a later phase.
- **D-16:** **Adopt Python stdlib `logging` module in this phase.** Closes the "No Logging System" item from `.planning/codebase/CONCERNS.md`. Setup:
  - Configure once at app entry (`stonereader/__main__.py` or `app.py`).
  - File handler: `~/.stonereader/stonereader.log` (same directory as the SQLite DB).
  - Console handler: same logger, mirrors to stdout.
  - Default level: `INFO`. `DEBUG` enabled via `STONEREADER_DEBUG=1` environment variable.
  - All Phase 2 modules use `logging.getLogger(__name__)`.
  - D-04 ("log on tick error") depends on this being in place.
- **D-17:** **Captured real Power.log fixtures in `tests/fixtures/log/`.** Hand-capture short representative games (~50–200KB each): standard match start, mid-game, normal game-end, reconnection (full re-dump), and one Battlegrounds session for stress. Commit fixtures to the repo. Tests feed fixtures through `parser.py`/`engine.py` and assert on the emitted event sequence and final `GameState` shape.
- **D-18:** **Stick with `@dataclass(frozen=True)` for all new models.** No `attrs` migration. Reasoning: stdlib only, already used everywhere in StoneReader, validators/converters not needed (parser layer owns coercion), and CLAUDE.md already locks this in. Revisit per-class if runtime validation ever becomes essential.

### Acceptance-Criteria Reinterpretation

- **D-19:** **LOG-05 ("Log watcher runs in a background thread without blocking the UI") is reinterpreted as "Log watcher does not block the UI."** With `wx.Timer` on the GUI thread (D-01), there is no OS thread to start, stop, or orphan. The original ROADMAP success criterion #5 — "thread can be started and stopped cleanly without UI freezes or orphaned threads" — becomes "Timer can be started and stopped cleanly; no UI freezes." Planner should update the phase's verifiable success criteria to match the chosen architecture.

### Claude's Discretion

- Exact polling interval is fixed at **150 ms** (D-01) but may be tuned by the planner if profiling shows under/over-shoot.
- Internal naming inside `services/` (e.g., whether the watcher class is `PowerLogWatcher` or `LogWatcher`) — pick whichever reads cleanest; planner decides.
- Exception class hierarchy for parser/engine errors — planner's call.
- The `GameStarted` event payload shape (game type, format, deck list, hero classes) — planner researches HDT/Firestone and proposes.
- Whether `services/` exposes a single `GameTracker` facade or distinct `Watcher` / `Parser` / `Engine` objects — planner's architectural call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements & Roadmap
- `.planning/ROADMAP.md` §"Phase 2: Log Infrastructure" — Goal, success criteria, dependencies, requirements list (LOG-01..05).
- `.planning/REQUIREMENTS.md` §"Log Infrastructure" — LOG-01 through LOG-05 acceptance items (note D-19 reinterprets LOG-05).
- `.planning/STATE.md` "Blockers/Concerns" — pre-existing notes on PowerTaskList duplication, file reset detection, threading, log.config (now resolved by decisions above).

### Power.log Domain Knowledge (authoritative for Phase 2)
- `docs/superpowers/research/2026-04-08-powerlog-parsing.md` — Comprehensive research on hslog API, Power.log line formats, packet types, event detection table, file behavior, edge cases (opponent hand, generated cards, joust/reveal, multi-game sessions), and pitfalls. Use this as the implementation reference for parser internals. **Note:** the doc's `wx.Timer` recommendation matches D-01; its `log_parser/` directory name is overridden by D-14 to `services/`.
- `docs/superpowers/specs/2026-04-08-stonereader-design.md` §"Log Parser" / §"Project Structure" — Original architecture spec. Overridden where it conflicts with this CONTEXT.md (module location D-14, dependency reality D-09).

### Codebase Maps
- `.planning/codebase/STRUCTURE.md` §"Where to Add New Code" — Pattern for new feature modules. Note: existing pattern is for presenter+view features; Phase 2 is headless and adds a `services/` directory not covered by the existing template.
- `.planning/codebase/CONVENTIONS.md` — Naming (snake_case modules, PascalCase classes), absolute imports, frozen dataclasses, type hints throughout.
- `.planning/codebase/CONCERNS.md` "Missing Critical Features → No Logging System" — Closed by D-16.
- `.planning/codebase/STACK.md` — Confirms `hearthstone 9.20.2` installed; `hslog`/`hsreplay` are NOT (D-09 adds hslog).

### Existing Code (required reading)
- `stonereader/models/game_state.py` — `Hero`, `GameEntity`, `GameState` frozen dataclasses. Engine produces these (D-05) but the model needs extension (D-08).
- `stonereader/models/card.py` — `Card`, `CardDatabase`. `GameEntity.base_card` references `Card`; engine may need to look up cards by ID via `CardDatabase`.
- `stonereader/db.py` — `~/.stonereader/` directory creation pattern (reused by D-16 log file). `games` table schema present but Phase 2 does not persist (D-15 note).
- `stonereader/app.py` `StoneReaderApp.OnInit()` — Integration point: instantiates the watcher/engine and starts the Timer.
- `stonereader/CLAUDE.md` — "Frozen dataclasses for all game state models — never mutate" (D-07, D-18).

### Phase 1 Reference (carry-forward decisions)
- `.planning/phases/01-deck-management/01-CONTEXT.md` §`<canonical_refs>` and §`<decisions>` — confirms architectural patterns Phase 2 inherits (frozen dataclasses, presenter pattern, `_notify_view()` callback shape mirrored by D-02 subscriber pattern).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `stonereader/models/game_state.py` — `GameState`, `GameEntity`, `Hero` frozen dataclasses are the engine's output type (after D-08 extension).
- `stonereader/models/card.py` — `CardDatabase.get_card_by_id()` / `get_card_by_dbf_id()` for engine to resolve card IDs from log entries.
- `hearthstone` package (already installed) — `hearthstone.enums.Zone`, `GameTag`, `BlockType`, `GameType`, `FormatType` enums for typed events and packet interpretation.
- `~/.stonereader/` directory pattern (`stonereader/db.py`) — reused by D-16 for log file location.
- Subscriber-callback pattern (existing presenters' `_notify_view()`) — D-02 mirrors this shape; idiomatic to the codebase.

### Established Patterns
- **Frozen dataclasses everywhere** — engine-emitted snapshots inherit this rule (D-07, D-18).
- **`snake_case` module names, `PascalCase` classes, absolute imports** — `services/` follows this.
- **Type hints throughout** — `Sequence[Card]`, `Optional[GameEntity]`, `Callable[[GameEvent], None]` for subscriber signatures.
- **`__init__.py` as a barrel** for the package — `services/__init__.py` should re-export the public API (`GameTracker` / `Watcher` / etc.) so consumers do `from stonereader.services import ...`.

### Integration Points
- `stonereader/app.py` `StoneReaderApp.OnInit()` — Currently sets up CardDatabase + DeckManager. Phase 2 adds: configure logging (D-16), instantiate the service, start the Timer. The Timer must live on a `wx.Frame`/`wx.App` to fire on the GUI thread.
- `stonereader/__main__.py` — Logging configuration could go here instead of `app.py` so it captures startup errors before the wx app initializes. Planner picks.
- `pyproject.toml` — Add `hslog` to `[project] dependencies`, add `psutil` if going that route for D-03 process detection. Run `uv sync` to update `uv.lock`.

### New code shape (advisory — planner finalizes)
```
stonereader/services/
├── __init__.py            # Public API barrel
├── log_path.py            # D-12 path discovery (registry, process, mtime)
├── log_config.py          # D-11 log.config bootstrap
├── watcher.py             # D-01/D-02 wx.Timer, subscribers, byte-offset tracking, D-13 backward scan, D-15 buffer cap
├── parser.py              # D-09/D-10 hslog wrapper, emits internal Packet objects
├── engine.py              # D-05/D-06/D-07 typed events + frozen GameState production
└── process_detect.py      # D-03 hearthstone.exe detection (psutil or win32api)

tests/fixtures/log/        # D-17 captured real Power.log fixtures
tests/test_services/       # parser, engine, watcher, log_path, log_config, process_detect tests
```

### Conflict Note
- The April-2026 design spec (`docs/superpowers/specs/2026-04-08-stonereader-design.md`) named this directory `log_parser/`. **D-14 overrides** this to `services/` to match the multi-phase plan (Phase 3/4 modules join the same dir). Planner: when reading the design spec, mentally substitute `log_parser/` → `services/`.

</code_context>

<specifics>
## Specific Ideas

- **Match HDT and Firestone where they agree** — they both use process detection for auto-start (D-03), mtime-based subdirectory selection (D-12), and the typed-events-plus-snapshot pattern (D-05). Where they diverge from the research doc (e.g., the doc's claim that wx.Timer is the obvious choice — true, and it stands), prefer HDT/Firestone behavioral parity since users may have used those trackers.
- **The `logging` rollout is part of this phase**, not a side quest. D-04 (catch + log on tick error) presupposes a logger exists. Planner should treat logging setup as a first task, not an afterthought.
- **Test fixtures matter** — Phase 2 has no UI to manually verify against. Captured Power.log fixtures (D-17) are how we prove `LogWatcher detects new lines within 1 second` (success criterion #1) and `duplicate lines from PowerTaskList blocks are filtered` (success criterion #2). At least one fixture per success criterion.
- **The `models/game_state.py` extension (D-08)** is the only model-shape decision that's deliberately deferred. Planner should research HDT's `Game.Player.Hand`/`Deck`/`Board` shape and Firestone's `GameState` shape, then propose a concrete diff in PLAN.md before any engine code is written.

</specifics>

<deferred>
## Deferred Ideas

- **Game-end persistence to SQLite `games` table** — `db.py` has the schema, but Phase 2 emits, doesn't store. Deferred to Phase 3 or a dedicated history phase.
- **Hot-reload of `log.config` changes** — we write it once on first run; we don't watch it for user edits. Out of scope.
- **UTF-8 partial-character handling at byte-chunk boundaries** — research doc flags this as a real edge case. Planner should address in `watcher.py` (decode as `utf-8` with `errors="replace"` or buffer until newline+decode), but it's an implementation concern, not a phase-level gray area.
- **Hearthstone reconnection / spectate mid-game** — research doc covers it (full re-dump as new `CREATE_GAME`). Engine handles via the same boundary logic as a fresh game start. Planner should include a fixture that exercises reconnect (D-17).
- **Backoff on repeated tick errors** — D-04 keeps it simple (always tick). Revisit if real-world noise demands it.
- **`psutil` vs `win32api` for process detection (D-03)** — both work. Planner picks based on which avoids the most platform-specific code.
- **Specific shape of `GameStarted` event payload** — Claude's discretion above. Planner researches and proposes.
- **Whether `services/` exposes a single `GameTracker` facade or distinct objects** — planner's architectural call.

</deferred>

---

*Phase: 02-log-infrastructure*
*Context gathered: 2026-04-25*
