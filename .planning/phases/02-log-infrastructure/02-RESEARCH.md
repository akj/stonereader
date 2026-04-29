# Phase 2: Log Infrastructure - Research

**Researched:** 2026-04-25
**Domain:** Real-time log tailing, Power.log parsing, frozen-snapshot game state engine, headless wxPython service
**Confidence:** HIGH (stack/library facts verified against live source); MEDIUM (HDT/Firestone state-shape mappings cited from current GitHub, but adapted for our model)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Threading & Lifecycle**
- D-01: wx.Timer at 150ms on the GUI thread. No `threading.Thread`. No `wx.CallAfter`.
- D-02: `subscribe(callback)` / `unsubscribe(callback)` direct-callback delivery. No wx events.
- D-03: Auto-start when `hearthstone.exe` is detected running. Process detection via `psutil` or `win32api`. Watcher pauses + resets parser state on process disappearance.
- D-04: Tick errors are caught, logged, and the Timer keeps ticking. No backoff in v1.

**Output Contract**
- D-05: Engine emits frozen `GameState` snapshots AND typed events.
- D-06: v1 events: Game lifecycle (`GameStarted`, `GameEnded`), Turn lifecycle (`TurnChanged`, `MulliganDone`), Card movement (`CardDrawn`, `CardPlayed`, `CardRevealed`, `CardRemoved`), Combat (`AttackStarted`, `MinionDied`, `DamageDealt`).
- D-07: New frozen `GameState` per meaningful change. No mutation. Subscribers share the same immutable snapshot.
- D-08: The existing `stonereader/models/game_state.py` `GameState` will need to grow. Specific field shape and naming is **deferred to the planner** — research HDT/Firestone and propose a concrete diff in PLAN.md.

**Parser Strategy**
- D-09: Adopt `hslog` as an explicit dependency this phase. `hsreplay` deferred to Phase 4.
- D-10: `hslog` is isolated to `parser.py`. The engine and public API never import hslog.

**Bootstrap**
- D-11: Auto-create / idempotently update `log.config` silently on first launch. Path: `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config` (Windows). Required `[Power]` keys written or merged. Speak one-line confirmation if newly created.
- D-12: Power.log path discovery: newest `Logs/Hearthstone_*/` subdirectory by mtime, with running-process-path / registry fallback (in that order). Re-scan when process restarts.
- D-13: On watcher start, backward-scan to the latest `CREATE_GAME` line. If none, jump to EOF and wait.

**Module & Infrastructure**
- D-14: All new code lives under `stonereader/services/` (overrides design spec's `log_parser/`).
- D-15: Raw-line buffer capped at 100,000 lines. No packet history retained. Game-end persistence is out of scope for Phase 2.
- D-16: Adopt Python stdlib `logging` module. File handler at `~/.stonereader/stonereader.log`. Console mirror. Default INFO. `STONEREADER_DEBUG=1` -> DEBUG. All Phase 2 modules use `logging.getLogger(__name__)`.
- D-17: Captured real Power.log fixtures in `tests/fixtures/log/`. Hand-capture standard match start/mid/end, reconnection, and one Battlegrounds session (~50–200KB each).
- D-18: `@dataclass(frozen=True)` for all new models.

**Acceptance Reinterpretation**
- D-19: LOG-05 ("background thread") becomes "Log watcher does not block the UI." With `wx.Timer` (D-01), there is no OS thread. Original ROADMAP success criterion #5 ("thread can be started/stopped") becomes "Timer can be started and stopped cleanly; no UI freezes."

### Claude's Discretion
- Polling interval: fixed at 150ms but planner may tune if profiling shows under/over-shoot.
- Internal naming inside `services/` (e.g., `PowerLogWatcher` vs `LogWatcher`) — pick whichever reads cleanest.
- Exception class hierarchy for parser/engine errors — planner's call.
- The `GameStarted` event payload shape (game type, format, deck list, hero classes) — planner researches HDT/Firestone and proposes (this RESEARCH proposes a concrete shape below; planner confirms).
- Whether `services/` exposes a single `GameTracker` facade or distinct `Watcher` / `Parser` / `Engine` objects — planner's architectural call (this RESEARCH recommends below).

### Deferred Ideas (OUT OF SCOPE)
- Game-end persistence to SQLite `games` table (Phase 3 or later).
- Hot-reload of `log.config` user edits.
- Backoff on repeated tick errors (revisit if real-world noise demands).
- `hsreplay` library (Phase 4).
- Battlegrounds-specific tracking (only ensure parser doesn't crash on BG logs).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOG-01 | App watches Hearthstone's Power.log file for changes in real time. | Polling section: `wx.Timer` at 150ms, byte-offset tracking, `FileShare.ReadWrite` semantics in HDT confirmed; Python `open(path, "rb")` matches Windows shared-read default. Validation: fixture `mid_game.log` appended in 100-line chunks during test; emitted-event count grows within one tick. |
| LOG-02 | App filters PowerTaskList duplicate lines to prevent double-counting. | hslog `parser.py` source confirms: `HandlerBase._game_state_processor = "GameState"` and every `find_callback` matches only `GameState.<method>` lines. **PowerTaskList lines are silently ignored by hslog.** Our watcher should additionally pre-filter for performance (HDT does), but correctness comes from hslog. |
| LOG-03 | App detects Power.log file reset on Hearthstone restart and resets parser state. | Detection: when `os.stat(path).st_size < self._offset` -> reset offset to 0, instantiate a fresh `LogParser`, drop accumulated GameState. Also triggered by `hearthstone.exe` disappearance (D-03). HDT pattern in `LogFileWatcher.cs` lines 188-275. |
| LOG-04 | App auto-creates or verifies log.config so Power.log output is enabled. | `log_config.py`: read existing INI via stdlib `configparser`, ensure `[Power]` section keys (`LogLevel=1`, `FilePrinting=True`, `ConsolePrinting=False`, `ScreenPrinting=False`, `Verbose=True`), preserve other sections. HDT writes 6 sections (Power, Achievements, Arena, FullScreenFX, LoadingScreen, Gameplay) — we only need `[Power]` for v1. |
| LOG-05 | (Reinterpreted by D-19) Log watcher does not block the UI. Timer can be started/stopped cleanly. | `wx.Timer.Stop()` is synchronous and idempotent. No threads to join. Per-tick read budget verified: HDT polls at 100ms reading multi-KB chunks without blocking — at 150ms with ~few-KB ticks, sub-millisecond per tick. |
</phase_requirements>

## Summary

Phase 2 is a headless service that tails Hearthstone's `Power.log` from a `wx.Timer`, feeds clean `GameState.DebugPrintPower` lines through `hslog.LogParser.read_line()`, and produces a stream of (a) typed event objects and (b) frozen `GameState` snapshots for downstream phases. The work splits cleanly into six small modules under `stonereader/services/`, plus a stdlib `logging` rollout, plus a captured-fixture test suite.

`hslog 1.18.0` (June 2025) is current and gives us the parser surface we need. It already filters `GameState` vs `PowerTaskList` automatically — confirmed by reading its source. HDT's open-source `LogFileWatcher.cs` is the reference for the polling loop, byte-offset tracking, file-rotation detection, and backward-scan-for-`CREATE_GAME` algorithm. Both HDT (C#) and Firestone (TypeScript) emit zone-grouped collections (Hand/Deck/Board/Graveyard/Secrets) plus a separate `cardsPlayedThisMatch` history list — we map this directly onto our existing `GameState` with three additions (Tuple fields).

**Primary recommendation:** Build a single `GameTracker` facade that internally composes `LogConfigBootstrapper`, `LogPathDiscoverer`, `ProcessDetector`, `PowerLogWatcher`, `Parser`, and `GameEngine`. Subscribers register against the facade. This matches HDT's `LogWatcher` orchestrator pattern and avoids leaking five separate objects to Phase 3 consumers. Internally each component is independently unit-testable.

## Architectural Responsibility Map

Phase 2 is headless. The service runs entirely on the wx GUI thread (via `wx.Timer`), reads from local disk, and exposes a Python callback API. No UI tier exists in this phase. The map below uses application tiers rather than browser/server tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Power.log tailing | wx GUI thread (Timer) | Disk I/O | D-01: `wx.Timer.Notify` runs on the same thread as `wx.App.MainLoop`. Avoids threading + `wx.CallAfter` complexity. |
| log.config bootstrap | One-shot at app init | Disk I/O | Runs once before Timer starts; idempotent. |
| Process detection | Polled per tick | OS API (psutil/win32) | Cheap call (~µs); ride the existing 150ms Timer. |
| hslog parsing | wx GUI thread | CPU | Per-line work is microseconds. Verified: HDT does this at 100ms on the UI thread. |
| GameState construction | wx GUI thread | CPU | Frozen-dataclass construction is microseconds. |
| Subscriber dispatch | wx GUI thread (synchronous) | — | D-02: direct callback. Subscribers run inline; phase 3 presenters will `wx.CallAfter` if they need to defer to a paint cycle. |
| Persistent logging | Background of `logging.FileHandler` | — | Stdlib FileHandler is non-blocking enough for a desktop app. |

**No misassignment risk.** All work is GUI-thread-bound and synchronous; the only question is whether each tick's work fits in a 150ms budget, which it trivially does.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `hslog` | 1.18.0 (Jun 2025) [VERIFIED: PyPI JSON API 2026-04-25] | Power.log line-by-line parser | Maintained by HearthSim, regex variants for BLOCK_START / dormant minions / hidden entities already battle-tested. We never want to maintain these regexes. |
| `psutil` | 7.2.2 (latest) [VERIFIED: pip index 2026-04-25] | Cross-platform process detection | Idiomatic Python, returns named-tuple processes; `process_iter(["name"])` is the canonical recipe in psutil's official docs. Avoids pywin32 import-time leakage in cross-platform tests. |
| `wxPython` | 4.2.5 | GUI shell + `wx.Timer` (existing) | Already locked; phase reuses `wx.Timer.Notify` for tick. |
| `hearthstone` | 9.20.2 (existing) | Enums (Zone, GameTag, BlockType, GameType, FormatType), `entities.Game/Player/Card` | Already a dep for card data; hslog requires it transitively. |

### Supporting (stdlib only)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `logging` | Structured logger per D-16 | All Phase 2 modules: `logging.getLogger(__name__)` |
| `configparser` | INI read/write for `log.config` | `log_config.py` — preserves comments via `RawConfigParser` |
| `pathlib.Path` | Filesystem ops | All path manipulation |
| `winreg` | Read `HKLM\SOFTWARE\Blizzard\Hearthstone` | `log_path.py` fallback when process not running |
| `codecs.getincrementaldecoder('utf-8')` | UTF-8 boundary-safe decode | `watcher.py` byte-stream chunking |
| `dataclasses` | Frozen dataclasses (events + state) | All event/state types |
| `typing` | `Callable[[GameEvent], None]`, `Sequence`, `Optional` | Subscriber signatures, immutable collections |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `psutil` | `pywin32` (`win32api.EnumProcesses`) | psutil avoids leaking Windows-only import into cross-platform test runs; `pywin32` is already in tree (transitive of `accessible-output2`) but its API is verbose and platform-specific. Choose **psutil**. |
| `psutil.process_iter(["name"])` | `psutil.pids() + Process(pid).name()` | `process_iter` is the documented idiom and pre-fetches attrs efficiently [CITED: github.com/giampaolo/psutil/blob/master/docs/recipes.md]. |
| `codecs.IncrementalDecoder` | `bytes.decode('utf-8', errors='replace')` | IncrementalDecoder buffers partial multi-byte sequences across chunk boundaries; `errors='replace'` corrupts the next character on every chunk that splits a UTF-8 sequence. Card names like "Sí:7'irí" can contain multi-byte chars. Choose **IncrementalDecoder**. |
| `RawConfigParser` | `configparser.ConfigParser` | RawConfigParser does not interpolate `%` characters — Hearthstone's log paths contain `%LOCALAPPDATA%`-shaped strings nowhere near INI values, but `Verbose=True` doesn't need interpolation either. Either works. **RawConfigParser** is safer. |

**Installation:**
```bash
uv add hslog psutil
# Updates pyproject.toml [project] dependencies and uv.lock.
```

**Version verification (run during planning, not now):**
```bash
uv run python -c "import hslog; print(hslog.__version__)"   # expect 1.18.0+
uv run python -c "import psutil; print(psutil.__version__)" # expect 7.x
```

[VERIFIED 2026-04-25] `uv run python -c "import hslog"` currently fails (ModuleNotFoundError) — STATE.md's "transitive install" note was wrong. `psutil` also missing. Adding both is required.

## Library Reference: hslog API Surface and Contract

**[VERIFIED 2026-04-25]** by reading `https://raw.githubusercontent.com/HearthSim/python-hslog/master/hslog/parser.py` and `tokens.py`.

### LogParser

```python
from hslog import LogParser
from hslog.exceptions import (
    ParsingError, RegexParsingError, CorruptLogError, NoSuchEnum,
)

parser = LogParser()
parser.read_line(line: str) -> Any | None    # one log line, with or without trailing \n
parser.read(fp)                               # iterates fp, calls read_line per line
parser.flush()                                # finalize pending mulligan/choice state
parser.games                                  # list[PacketTree] — completed games
parser.game_meta                              # dict — global game metadata
parser.player_manager                         # PlayerManager — name/ID resolution
```

**Input type:** `str` (one line at a time). Source: `parser.py` line 1102 — `read_line(self, line)` immediately runs `tokens.TIMESTAMP_RE.match(line)`. Strings, not bytes. Trailing `\n` is fine; the regex tolerates it. Lines must be complete — partial lines raise `RegexParsingError`.

**Streaming contract:** `read_line` is fully streaming. Internal `ParsingState` accumulates across calls. Multi-line packets (BLOCK_START with nested children, CREATE_GAME with players + entities, EntityChoices) are stitched together via `current_block` state. **No buffering required from us** — we just feed lines as they arrive.

**Source-tag filtering (CRITICAL for LOG-02):**
```python
# parser.py line 191:
class HandlerBase:
    def __init__(self):
        self._game_state_processor = "GameState"
    def parse_method(self, m):
        return "%s.%s" % (self._game_state_processor, m)
```
Every handler (`PowerHandler`, `ChoicesHandler`, `OptionsHandler`) registers callbacks keyed on `"GameState.<method>"`. `find_callback` returns `None` for `PowerTaskList.*` lines, and the dispatch loop in `read_line` (line 1145-1158) silently skips them. **hslog already does PowerTaskList filtering for us. We do not need to re-implement this.**

We *should* still pre-filter at the watcher layer for performance — HDT does. Filter rule: keep only lines that, after the timestamp prefix `D HH:MM:SS.ttttttt `, start with `GameState.` (or, defensively, lines hslog will silently drop are also fine — it's just slightly more CPU per tick).

**Backward-scan friendliness (CRITICAL for D-13):**
```python
# parser.py line 1132:
if not self._parsing_state.current_block and "CREATE_GAME" not in msg:
    # Ignore messages before the first CREATE_GAME packet
    return
```
hslog itself ignores any `GameState` line before `CREATE_GAME` is seen. So if we feed it from a stale offset (mid-game), it will spin its wheels until it finds a `CREATE_GAME`. **For correctness we must not feed it from a stale offset** — backward-scan finds the right boundary first.

### Exceptions

| Exception | When | Strategy |
|-----------|------|----------|
| `RegexParsingError` | Line doesn't match expected regex (corrupt write, encoding issue) | Catch in watcher; log WARNING; skip line; keep tick |
| `ParsingError` | Generic packet logic error (orphaned BLOCK_END, unknown entity) | Catch in engine; log WARNING; reset current packet tree only if game lifecycle is poisoned |
| `CorruptLogError` | NUL bytes in stream (rare, indicates disk corruption) | Catch; log ERROR; reset offset to current EOF |
| `NoSuchEnum` | Hearthstone enum drift (new GameTag value hslog doesn't know yet) | Catch; log WARNING with enum + value; **continue** (hslog itself swallows the EOE-from-HearthstoneAccess case at line 1162 — same pattern) |

### Packet Tree (read-only data we extract events from)

```python
from hslog.packets import (
    PacketTree, CreateGame, Block, FullEntity, ShowEntity, HideEntity,
    ChangeEntity, TagChange, MetaData, Choices, ResetGame,
)
from hearthstone.enums import Zone, GameTag, BlockType, GameType, FormatType
```

The completed-game packet tree is iterable. For live tracking, we read `parser._parsing_state.packet_tree` (the in-progress tree), or — cleaner — we register our own custom dispatch on top of `BaseExporter` from `hslog.export` to incrementally consume packets. Since D-10 isolates hslog to `parser.py`, our `parser.py` will:

1. Wrap `LogParser` instance.
2. After each `read_line()`, walk *new* packets in `parser._parsing_state.current_block.packets` (or top-level `packet_tree.packets`).
3. Translate each new packet into our internal `Packet` discriminated union (`CreateGamePacket`, `TagChangePacket`, `BlockStartPacket`, `BlockEndPacket`, `FullEntityPacket`, `ShowEntityPacket`, `HideEntityPacket`, `ChangeEntityPacket`).
4. Hand those to `engine.py`. Engine never sees `hslog.packets.*`.

Bookkeeping: track an integer `packet_id` cursor (hslog assigns monotonic IDs via `packet_counter`); after each `read_line` batch, walk packets with id > cursor.

### Useful enums (re-exported from `hearthstone.enums`)

```python
Zone:        PLAY=1, DECK=2, HAND=3, GRAVEYARD=4, REMOVEDFROMGAME=5,
             SETASIDE=6, SECRET=7
BlockType:   ATTACK=1, JOUST=2, POWER=3, SCRIPT=4, TRIGGER=5,
             DEATHS=6, PLAY=7, FATIGUE=8, RITUAL=9, REVEAL_CARD=10
GameType:    GT_RANKED=7, GT_CASUAL=8, GT_ARENA=5,
             GT_BATTLEGROUNDS=23, GT_TAVERNBRAWL=16
FormatType:  FT_UNKNOWN=0, FT_WILD=1, FT_STANDARD=2, FT_CLASSIC=3, FT_TWIST=4
GameTag:     ZONE, ZONE_POSITION, CONTROLLER, CARDTYPE, COST, ATK, HEALTH,
             DAMAGE, TURN, NUM_TURNS_IN_PLAY, MULLIGAN_STATE,
             PLAYSTATE (PLAYING/WON/LOST/TIED), STATE (RUNNING/COMPLETE),
             CURRENT_PLAYER, CARD_ID
```

## Domain Reference: HDT and Firestone GameState Shapes

**[VERIFIED 2026-04-25]** HDT — read `Hearthstone Deck Tracker/Hearthstone/Player.cs` via WebFetch. **[CITED]** Firestone — `libs/game-state/src/lib/models/deck-state.ts` via WebFetch.

### HDT `Player` (per-player object)

| Property | Type | Meaning |
|----------|------|---------|
| `Hand` | `IEnumerable<Entity>` (filtered by `IsInHand`) | Cards currently in hand |
| `Deck` | `IEnumerable<Entity>` (filtered by `IsInDeck`) | Cards still in deck |
| `Board` | `IEnumerable<Entity>` (filtered by `IsInPlay`) | Minions on board |
| `Graveyard` | filtered | Dead/discarded |
| `SecretZone` | filtered | Secrets and Quests (combined zone) |
| `Secrets` | `Where(IsSecret)` | Just secrets |
| `Quests` | `Where(IsQuest \|\| IsSideQuest)` | Just quests |
| `SetAside` | filtered | Transformed-out / cthun-style holding |
| `CardsPlayedThisMatch` | `List<Entity>` | History — every card played this game, **in play order** |
| `CardsPlayedThisTurn` | `List<Entity>` | Reset each turn |
| `CardsPlayedLastTurn` | `List<Entity>` | Previous turn snapshot |
| `StartingHand` | `List<Entity>` | Cards held at end of mulligan |
| `EntitiesDiscardedFromHand` | `List<Entity>` | Discard tracking |
| `DeadMinionsCards` | `List<Card>` | Minions that died |
| `LastDrawnCardId` | `string` | Most recent draw |
| `RevealedEntities` | `List<Entity>` | All cards exposed during the game |
| `RevealedCards` | grouped `Card` collection | Revealed cards grouped by id |
| `KnownCardsInDeck` | grouped `Card` collection | Identified deck cards |

### Firestone `DeckState` (per-player)

| Field | Type | Meaning |
|-------|------|---------|
| `hand` | `readonly DeckCard[]` | Hand zone |
| `deck` | `readonly DeckCard[]` | Deck zone |
| `board` | `readonly DeckCard[]` | Board zone |
| `otherZone` | `readonly DeckCard[]` | Graveyard + setaside + removed |
| `secrets` | `readonly BoardSecret[]` | Secrets |
| `cardsPlayedThisMatch` | `readonly ShortCardWithTurn[]` | **Play history with turn number** |
| `cardsPlayedThisTurn` | `readonly DeckCard[]` | Reset per turn |
| `cardsPlayedLastTurn` | `readonly DeckCard[]` | Previous turn |
| `cardDrawnThisGame` | `number` | Total draw count |
| `cardsDrawnByTurn` | `readonly NumericTurnInfo[]` | Per-turn draw counts |
| `secretsTriggeredThisMatch` | grouped | Triggered secrets |
| `minionsDeadThisMatch` | grouped | Dead minions |

### Convergence

Both trackers split data into two structures:
1. **Zone collections** — Hand / Deck / Board / Graveyard / Secrets — current snapshot.
2. **History lists** — `cardsPlayedThisMatch`, draws, deaths — append-only over the game's lifetime.

**Important:** History lists are *not* derivable from current zones at a moment in time. A card played and then destroyed leaves Board (no longer there) and shows up in Graveyard, but we still want to say "your opponent played Reno on turn 4." That's why HDT and Firestone both maintain explicit play-history lists.

LIVE-04 ("opponent's played cards in play order") *requires* this history list. We cannot rebuild it from a single `GameState` snapshot — we need to either keep a per-player play-history field on `GameState`, or have the engine maintain the history outside `GameState` and expose it via a separate read API.

### Recommendation: history-on-GameState

Putting play history on `GameState` directly keeps the snapshot-as-single-source-of-truth contract (D-05/D-07). Each new snapshot copies the previous history list and appends. The history is bounded by game length (~100 cards/game max in standard, ~250 in BG). Memory cost: trivial.

## Proposed `GameState` Diff (D-08)

**Status:** RECOMMENDATION — planner copies into PLAN.md.

```python
# stonereader/models/game_state.py
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from stonereader.models.card import Card


@dataclass(frozen=True)
class Hero:
    """Represents a Hearthstone hero."""
    id: str
    name: str
    health: int
    armor: int
    hero_power: str
    # NEW (Phase 2): hero class for matchup announcements (LIVE-08, GameStarted payload)
    hero_class: str = ""  # "MAGE", "WARRIOR", etc. (matches Card.card_class enum)


@dataclass(frozen=True)
class GameEntity:
    """Represents an entity on board/hand at a snapshot."""
    entity_id: int
    card_id: str
    base_card: Optional[Card]
    name: str
    cost: int
    current_attack: int
    current_health: int
    card_type: str
    zone: str
    zone_position: int
    controller: int
    exhausted: bool = False
    enchantment_names: Tuple[str, ...] = ()
    tags: Dict[str, Any] = field(default_factory=dict)
    # NEW (Phase 2): turn the entity was drawn into hand (for DIFF-01 deferred,
    # but cheap to capture now). 0 = mulligan; -1 = unknown (opponent hidden).
    drawn_turn: int = -1


@dataclass(frozen=True)
class PlayedCard:
    """A card played during the game, with the turn it was played on.

    Mirrors HDT's CardsPlayedThisMatch entry and Firestone's ShortCardWithTurn.
    Used to drive LIVE-04 (opponent played-in-order).
    """
    entity_id: int                  # the entity at time of play (may have left board)
    card_id: str                    # current card_id at time of play
    base_card: Optional[Card]       # resolved Card (None if hidden at play time)
    name: str                       # convenience for speech
    turn: int                       # the turn the play happened (0 = mulligan-into-hand, irrelevant for plays)
    controller: int                 # 1 = friendly, 2 = opponent (matches PlayerID semantics)


@dataclass(frozen=True)
class GameState:
    """Represents a moment in game time."""
    turn: int
    active_player_id: int

    # Zone snapshots (existing)
    player_board: Tuple[GameEntity, ...]
    opponent_board: Tuple[GameEntity, ...]
    player_hand: Tuple[GameEntity, ...]
    opponent_hand: Tuple[Optional[GameEntity], ...]   # Optional preserves "hidden card" semantics
    player_hero: Hero
    opponent_hero: Hero
    player_weapon: Optional[GameEntity] = None
    opponent_weapon: Optional[GameEntity] = None
    player_secrets: Tuple[GameEntity, ...] = ()
    opponent_secrets: Tuple[GameEntity, ...] = ()
    player_mana: int = 0
    player_max_mana: int = 0
    opponent_mana: int = 0
    opponent_max_mana: int = 0
    player_deck_count: int = 0
    opponent_deck_count: int = 0

    # NEW (Phase 2) — drives LIVE-02 player remaining deck
    player_deck: Tuple[GameEntity, ...] = ()
    # opponent_deck NOT exposed — Hearthstone never reveals it; count only.

    # NEW (Phase 2) — drives LIVE-04 opponent played in order
    player_played: Tuple[PlayedCard, ...] = ()
    opponent_played: Tuple[PlayedCard, ...] = ()

    # NEW (Phase 2) — drives LIVE-03 cards-drawn history
    player_drawn: Tuple[PlayedCard, ...] = ()       # uses PlayedCard for shape parity (turn = draw turn)
    opponent_drawn: Tuple[PlayedCard, ...] = ()     # opponent draws may have unknown card_id

    # NEW (Phase 2) — drives game lifecycle queries
    game_state: str = "RUNNING"     # "RUNNING" | "COMPLETE"
    game_type: str = ""             # "RANKED" | "CASUAL" | "ARENA" | "BATTLEGROUNDS" | ""
    format_type: str = ""           # "STANDARD" | "WILD" | "CLASSIC" | "TWIST" | ""
    player_playstate: str = ""      # "" | "PLAYING" | "WON" | "LOST" | "TIED"
    opponent_playstate: str = ""

    # NEW (Phase 2) — drives auto-deck-detect (LIVE-08, deferred to Phase 3 but cheap to capture)
    player_starting_hand: Tuple[GameEntity, ...] = ()
```

**Why these names:**
- `player_*` / `opponent_*` matches the existing convention (`player_hand`, `opponent_hand`).
- `*_played` plural-noun list parallels HDT's `CardsPlayedThisMatch` and Firestone's `cardsPlayedThisMatch`.
- `*_drawn` list pattern matches Firestone's `cardsDrawnByTurn` semantics.
- `game_state` (string) chosen over an enum to keep stdlib-only and avoid leaking `hearthstone.enums.State` into the model layer (engine translates).

**Why no opponent deck list:** Hearthstone's Power.log doesn't expose the opponent deck contents. HDT and Firestone show *predicted* opponent decks, which is well beyond v1 scope (deferred DIFF features in REQUIREMENTS.md).

**Backward compatibility:** All new fields have defaults, so existing test fixtures and callers continue to construct `GameState` without breakage.

**Memory bound:** `player_played + opponent_played + player_drawn + opponent_drawn` grow O(game length). 100 cards/game × 4 lists × ~200 bytes/PlayedCard = ~80 KB per snapshot. With each meaningful tag-change producing a new snapshot (~1000/game), if subscribers retain snapshots that's ~80 MB/game. **Mitigation:** D-15 caps raw lines at 100k but doesn't bound snapshots. Subscribers must not retain old snapshots; the engine itself should hold only the latest. Document this in the engine docstring.

## Architecture Recommendation: `GameTracker` Facade

### System Architecture Diagram

```
                      ┌─────────────────────────────────────────────┐
                      │            stonereader.app                  │
                      │  ┌────────────────┐                         │
                      │  │ StoneReaderApp │  on OnInit:             │
                      │  │     OnInit     │  1. logging.basicConfig │
                      │  └────────┬───────┘  2. GameTracker(...)    │
                      │           │          3. .start(parent=frame)│
                      └───────────┼─────────────────────────────────┘
                                  │
                                  ▼
                  ┌─────────────────────────────────────┐
                  │   stonereader.services.GameTracker  │
                  │   (public facade — Phase 3 import)  │
                  │                                      │
                  │  + start(parent: wx.Window)         │
                  │  + stop()                            │
                  │  + subscribe(callback)              │
                  │  + unsubscribe(callback)            │
                  │  + current_state -> Optional[GameState]
                  └────────────┬────────────────────────┘
                               │ owns
            ┌──────────────────┼──────────────────┬─────────────────┐
            ▼                  ▼                  ▼                 ▼
     ┌─────────────┐    ┌──────────────┐  ┌─────────────┐  ┌────────────────┐
     │ LogConfig   │    │ ProcessDetect│  │ LogPath     │  │ PowerLogWatcher│
     │ Bootstrapper│    │              │  │ Discoverer  │  │  + wx.Timer    │
     │ (one-shot)  │    │ psutil scan  │  │ winreg/proc │  │  + offset      │
     └─────────────┘    └──────────────┘  └─────────────┘  └────────┬───────┘
                                                                     │ feeds bytes
                                                                     ▼
                                                            ┌────────────────┐
                                                            │ utf8 buffered  │
                                                            │ line splitter  │
                                                            └────────┬───────┘
                                                                     │ feeds str lines
                                                                     ▼
                                                            ┌────────────────┐
                                                            │   Parser       │
                                                            │ (hslog wrapper)│
                                                            │ emits Packet*  │
                                                            └────────┬───────┘
                                                                     │ Packet stream
                                                                     ▼
                                                            ┌────────────────┐
                                                            │   GameEngine   │
                                                            │ frozen state + │
                                                            │ typed events   │
                                                            └────────┬───────┘
                                                                     │ event + state
                                                                     ▼
                                                            ┌────────────────┐
                                                            │  subscribers   │
                                                            │  (Phase 3)     │
                                                            └────────────────┘
```

### Why a single facade

**For:**
- Phase 3 imports one symbol: `from stonereader.services import GameTracker`.
- Subscriber/unsubscribe API lives in one place.
- Lifecycle (start/stop, process gone, file rotated) is orchestrated by one object — Phase 3 doesn't need to know whether the watcher or the engine resets state when Hearthstone exits.
- HDT's open-source reference implementation uses exactly this pattern (`HearthWatcher.LogWatcher` orchestrates `LogFileWatcher` + dispatcher).

**Against:**
- Tests can mock the facade but lose granularity. **Mitigation:** internal components are independently importable from `stonereader.services._watcher`, `_parser`, `_engine` (underscore-prefixed = "internal but testable"). Tests construct each in isolation.

**Recommended public API:**

```python
# stonereader/services/__init__.py
from stonereader.services._tracker import GameTracker
from stonereader.services._events import (
    GameEvent, GameStarted, GameEnded, TurnChanged, MulliganDone,
    CardDrawn, CardPlayed, CardRevealed, CardRemoved,
    AttackStarted, MinionDied, DamageDealt,
)

__all__ = [
    "GameTracker",
    "GameEvent",
    "GameStarted", "GameEnded",
    "TurnChanged", "MulliganDone",
    "CardDrawn", "CardPlayed", "CardRevealed", "CardRemoved",
    "AttackStarted", "MinionDied", "DamageDealt",
]
```

Underscore-prefixed internal modules (`_watcher.py`, `_parser.py`, etc.) signal "implementation detail; importable for tests but not part of the stable API." This is a Pythonic convention; HDT/Firestone use file-private classes for the same purpose.

## Algorithms

### Backward-scan for `CREATE_GAME` (D-13)

**Reference:** HDT `LogFileWatcher.cs` `FindInitialOffset` method, lines 274-310.

**Algorithm:**
1. `open(path, "rb")`, `seek(0, SEEK_END)`, capture `file_size`.
2. Walk backward in 4 KB chunks: `chunk_size = 4096`, `read_offset = max(0, file_size - n*chunk_size)`.
3. Read the chunk. Find lines within it (split on `b"\n"`, careful at chunk boundary).
4. From the chunk's last line backward, look for `b"GameState.DebugPrintPower() - CREATE_GAME"`.
5. If found, set `self._offset = absolute byte offset of the line start`. Done.
6. If not found in current chunk, advance one chunk earlier and repeat.
7. Hard cap: 256 chunks (1 MB). If still not found, set `self._offset = file_size` (start at EOF, wait for new game).

**Why bytes not chars:** `os.path.getsize()` returns bytes; `seek()` and `tell()` use bytes. Decoding to str only happens *after* we've sliced clean lines from the byte buffer.

**File-can-grow-during-scan handling:** Snap `file_size = os.fstat(fd).st_size` once at the start. New writes after that point are caught by the next normal poll tick. We never want to chase a moving target during the initial scan.

**Memory bound:** 1 MB peak buffer (256 chunks × 4 KB). Even on a 500 MB log file from a long BG session, we read at most 1 MB.

**Why not "read the whole file":** A 500 MB Power.log read into memory is a 1-2 second hitch. HDT measured this in 2015 and adopted backward-chunked-scan; we follow the same.

### UTF-8 boundary-safe decode

**Pattern:**

```python
import codecs

class _LineReader:
    def __init__(self):
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._partial = ""  # buffer for partial line (no trailing \n)

    def feed(self, chunk: bytes) -> list[str]:
        """Feed raw bytes from the file; return zero or more complete lines.

        Trailing partial line is buffered until the next call.
        """
        text = self._decoder.decode(chunk, final=False)
        text = self._partial + text
        if "\n" not in text:
            self._partial = text
            return []
        *lines, self._partial = text.split("\n")
        # Strip any trailing \r (Windows line endings)
        return [line.rstrip("\r") for line in lines]

    def reset(self):
        self._decoder.reset()
        self._partial = ""
```

**Why IncrementalDecoder, not `chunk.decode(errors='replace')`:** UTF-8 multi-byte sequences (2-4 bytes) split across chunk boundaries get replaced with `�` if we use simple decoding on each chunk. Card names like "Sí:7'i'rí" or "Élise" contain multi-byte chars. IncrementalDecoder buffers partial sequences across calls. [VERIFIED: docs.python.org/3/library/codecs.html — IncrementalDecoder.decode(input, final=False) — buffers incomplete sequences].

**Why `errors="replace"` and not `"strict"`:** Power.log occasionally has truncation under reconnect, and we want to keep tailing rather than crash. `errors="strict"` would raise `UnicodeDecodeError`; `"replace"` substitutes `�` and continues.

### Duplicate / PowerTaskList filtering

**Single layer is sufficient:** hslog drops `PowerTaskList.*` lines silently (verified above).

**Optional pre-filter for performance:**
```python
def _is_gamestate_line(line: str) -> bool:
    # After 'D HH:MM:SS.fffffff ' — 19 chars including trailing space
    if len(line) < 20 or not line.startswith("D "):
        return False
    return line[20:].startswith("GameState.")
```

This drops ~50% of incoming lines before they reach hslog. Optional optimization, not required for correctness. The watcher should pre-filter; the parser should still defensively skip non-`GameState` lines (in case the watcher's filter has a bug — defense in depth).

### File rotation / reset detection (LOG-03)

**Trigger condition:** `current_size = os.fstat(fd).st_size; current_size < self._offset` — file shrunk since last tick. Hearthstone truncated on restart.

**Action:**
1. `self._offset = 0`
2. `self._line_reader.reset()` (drop partial decode buffer)
3. Construct fresh `LogParser` instance (drop hslog state)
4. Engine: emit `GameEnded` if a game was in progress; reset `current_state = None`
5. Emit nothing else; let next tick start re-reading from offset 0

**Edge case: file deleted between ticks** — `FileNotFoundError` from `os.stat`. Same handler: reset offset/state, wait for file to reappear.

**Edge case: file replaced (atomic rename) and same size** — extremely unlikely for Power.log (Hearthstone always truncates in-place). If it happened, mtime would jump backward; we *could* check mtime as a defensive secondary trigger. **Recommendation:** size-shrink only for v1, simpler and sufficient.

### Process detection cadence (D-03)

Run `psutil.process_iter(["name"])` once per Timer tick (150ms). Cost on Windows: ~5ms. Cache last result with a 2-second TTL to drop the cost; HDT does this (`_lastCheck` field, 5-second TTL in C# code).

```python
# services/_process_detect.py
import psutil, time

_HEARTHSTONE_EXE = "Hearthstone.exe"  # case-insensitive on Windows

class ProcessDetector:
    def __init__(self, cache_ttl_seconds: float = 2.0):
        self._ttl = cache_ttl_seconds
        self._last_check = 0.0
        self._last_result: tuple[bool, Optional[psutil.Process]] = (False, None)

    def is_running(self) -> tuple[bool, Optional[psutil.Process]]:
        now = time.monotonic()
        if now - self._last_check < self._ttl:
            return self._last_result
        self._last_check = now
        for p in psutil.process_iter(["name"]):
            try:
                if (p.info["name"] or "").lower() == _HEARTHSTONE_EXE.lower():
                    self._last_result = (True, p)
                    return self._last_result
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self._last_result = (False, None)
        return self._last_result

    def get_install_dir(self) -> Optional[Path]:
        running, proc = self.is_running()
        if not running or proc is None:
            return None
        try:
            return Path(proc.exe()).parent
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
```

[CITED: github.com/giampaolo/psutil/blob/master/docs/recipes.md — find_procs_by_name recipe]

## Test Fixture Capture Procedure (D-17)

### What we need

| Fixture | Drives Test | Approx. size |
|---------|-------------|--------------|
| `match_start.log` | LOG-01: detect new lines, GameStarted event, mulligan packets | 30–50 KB |
| `mid_game.log` | LOG-01: parse cards drawn/played, turn changes, full snapshot | 80–150 KB |
| `game_end.log` | GameEnded event, PLAYSTATE WON/LOST | 100–200 KB |
| `reconnect.log` | Mid-game reconnection: full re-dump as new CREATE_GAME | 150–250 KB |
| `battlegrounds.log` | Stress: 25+ minute BG game, ensure no crash | 1–5 MB |
| `corrupt_partial.log` | Synthesized: file ends mid-line — assert no crash | 5–10 KB |
| `truncation.log` | Synthesized pair: full game then truncated to 0 — drives LOG-03 | (n/a) |

### Capture procedure (manual, one-time, on the user's Windows machine)

1. **Enable Power.log via the standard HDT-style log.config.** This is what our own `log_config.py` will write — but for fixture capture, we set it up by hand once:
   ```ini
   ; %LOCALAPPDATA%\Blizzard\Hearthstone\log.config
   [Power]
   LogLevel=1
   FilePrinting=True
   ConsolePrinting=False
   ScreenPrinting=False
   Verbose=True
   ```
2. **Confirm location:** `%LOCALAPPDATA%\Blizzard\Hearthstone\Logs\Hearthstone_YYYY_MM_DD_HH_MM_SS\Power.log` (newest subdirectory while Hearthstone is running).
3. **Restart Hearthstone** (forces a fresh log directory).
4. **Play a short Casual match against the AI Innkeeper.** Concede early for `match_start.log` (~30s); play to game end for `game_end.log`.
5. **For `reconnect.log`:** Start a Casual match, force-quit Hearthstone mid-game (Task Manager), restart, reconnect. Hearthstone re-dumps full state — captures the reconnection edge case.
6. **For `battlegrounds.log`:** Play one BG match to top-4 minimum.
7. **Copy** the resulting `Power.log` files into `tests/fixtures/log/` with the names above.
8. **Anonymize:** scan for `PlayerName=` lines and replace with `PlayerName=Player1` / `PlayerName=Player2` to avoid leaking BattleTags. Use `sed` (Linux/WSL) or Notepad++ regex find-replace.
9. **Truncate to size budget** if needed: `head -c 200000 game_end.log > game_end_trimmed.log` — but only at a `\n` boundary.
10. **Synthesized fixtures (`corrupt_partial.log`, `truncation.log`):** craft these in tests using `tmp_path` rather than committing — test code writes deliberately broken bytes, then feeds them through the watcher.
11. **Commit fixtures.** They contain only public Hearthstone game data; no PII once anonymized. Note any Battlegrounds fixture above 1 MB should be `git lfs` if available, else trim.

### How tests will use fixtures

```python
# tests/test_services/test_engine.py — sketch
from pathlib import Path
from stonereader.services._parser import Parser
from stonereader.services._engine import GameEngine
from stonereader.services._events import GameStarted, CardPlayed

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "log"

def test_match_start_emits_game_started_with_classes():
    parser = Parser()
    engine = GameEngine(card_db=...)
    events: list = []
    engine.subscribe(events.append)

    text = (FIXTURE_DIR / "match_start.log").read_text(encoding="utf-8")
    for line in text.splitlines():
        for packet in parser.feed_line(line):
            engine.apply(packet)

    started = [e for e in events if isinstance(e, GameStarted)]
    assert len(started) == 1
    assert started[0].player_class in {"MAGE", "WARRIOR", ...}
    assert started[0].opponent_class in {"MAGE", "WARRIOR", ...}
    assert started[0].game_type in {"CASUAL", "RANKED", ...}
    assert started[0].format_type in {"STANDARD", "WILD"}
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BLOCK_START / BLOCK_END / FULL_ENTITY regex matching | Custom regex | `hslog.LogParser.read_line()` | hslog has 5+ regex variants per opcode for historical Hearthstone patches (BLOCK_START_12051_RE, BLOCK_START_20457_RE, BLOCK_START_20457_TRIGGER_KEYWORD_RE…). Maintaining these is a perpetual upstream-tracking treadmill. |
| PowerTaskList vs GameState filtering | Manual line filter | Trust hslog's `_game_state_processor = "GameState"` | Already verified via source inspection. |
| Friendly-player identification | Heuristics | `hslog.export.FriendlyPlayerExporter` | Uses revealed-card heuristics; correct edge cases for spectator mode and old logs. |
| Dormant minions / hidden entities | Special-case handling | `EntityTreeExporter.handle_cached_tag_for_dormant_change` | Dormant minions (Galakrond, etc.) need queue-and-apply ordering; hslog does this. |
| Process detection | EnumProcesses + win32api boilerplate | `psutil.process_iter(["name"])` | psutil has dealt with Windows-specific edge cases (zombie PIDs, AccessDenied) for a decade. |
| INI parsing for `log.config` | Custom parser | `configparser.RawConfigParser` | INI format has surprising rules; stdlib handles them. |
| UTF-8 partial-byte handling | bytes-buffer + decode at line boundaries | `codecs.getincrementaldecoder('utf-8')` | Built for exactly this; handles surrogate pairs and 4-byte chars correctly. |
| Logging file rotation | Custom rotation | `logging.handlers.RotatingFileHandler` | Phase 2 doesn't need rotation (the `~/.stonereader/stonereader.log` is for diagnosis, not production volume). Stdlib has it ready when we want it. |
| Backward-line-reading | Reverse iteration | Manual chunk-from-end (HDT pattern) | No mature stdlib utility; copy HDT's documented algorithm. |
| Dataclass validation | `attrs` migration | Stdlib `@dataclass(frozen=True)` | D-18 lock; CLAUDE.md lock. Parser layer owns coercion. |

## Common Pitfalls

### Pitfall 1: Reading from stale offset after Hearthstone restart
**What goes wrong:** Watcher tracks byte offset across ticks. Hearthstone truncates `Power.log` on restart. Next tick: offset is 5 MB, file is now 100 KB; `seek(5_000_000)` succeeds (Windows allows seek beyond EOF), `read()` returns empty bytes — silent no-op forever, watcher appears alive but parses nothing.
**Why it happens:** Treating `read() == b""` as "no new data" without checking file size first.
**How to avoid:** Every tick, `os.fstat(fd).st_size`. If `size < self._offset`, that's a truncation — reset to 0 and reset parser.
**Warning sign:** Logs go silent for >30s during normal play.

### Pitfall 2: Process detection blocks the GUI thread
**What goes wrong:** `psutil.process_iter()` enumerates all processes; on a heavily loaded Windows box this can take 50-200ms. At 150ms tick interval, that's 30%+ of every tick blocked.
**How to avoid:** Cache result with 2-second TTL (HDT does 5s). Inside the cache window, the detector returns the previous result without re-enumerating.
**Warning sign:** Visible UI lag while StoneReader is running.

### Pitfall 3: Subscriber callback raises an exception
**What goes wrong:** Phase 3 presenter throws `KeyError` in its event handler. Engine's emit loop bubbles up, kills the Timer, watcher dies silently.
**How to avoid:** Engine wraps each `callback(event)` in `try/except Exception` and logs at WARNING. One bad subscriber must not poison the others. (D-04 covers tick errors but is silent on subscriber errors — same mitigation, different layer.)
**Warning sign:** One subscriber works, another silently never receives events.

### Pitfall 4: Frozen `GameState` deep-copy footgun
**What goes wrong:** `@dataclass(frozen=True)` blocks attribute assignment but Python lists/dicts inside the dataclass remain mutable. If the engine builds the next state by `dataclasses.replace(prev, player_played=prev.player_played + (new,))`, that's correct. But if it does `prev.player_played.append(new)`, it raises (because we use Tuples) — but a `field(default_factory=list)` would silently allow the mutation, breaking the immutability contract.
**How to avoid:** Use `Tuple[...]` not `List[...]` for all collection fields on `GameState`. The proposed diff above already does this. Type-check enforces it.
**Warning sign:** Multiple subscribers see different snapshots when they shouldn't.

### Pitfall 5: log.config writer destroys other tools' settings
**What goes wrong:** User has HDT or Firestone installed; their `log.config` has 6 sections. We open the file, write only `[Power]`, blow away the rest. Other tools break.
**How to avoid:** `RawConfigParser.read(path)` first, then `set("Power", "LogLevel", "1")` etc., then `write(path)`. This preserves untouched sections.
**Warning sign:** User reports HDT or BG-tracker stops working after StoneReader runs.

### Pitfall 6: hslog `NoSuchEnum` crashes on enum drift
**What goes wrong:** Hearthstone patch adds `GameTag.SOME_NEW_TAG`. hslog hasn't been updated. `NoSuchEnum` exception propagates up, kills tick, then D-04 logs and we keep going — but every line of every game now hits this exception. CPU pegged on logging.
**How to avoid:** Catch `NoSuchEnum` in `parser.py` (inside the `read_line` wrapper); log once per unique `(enum, value)` tuple via a `set` cache; continue. hslog itself does this for the HearthstoneAccess `EOE` value (line 1162) — same pattern.
**Warning sign:** Log file grows to GB after a Hearthstone patch lands.

### Pitfall 7: Mid-game reconnect creates duplicate `CREATE_GAME`
**What goes wrong:** Player loses connection, Hearthstone reconnects, server re-dumps full game state as a fresh `CREATE_GAME` block. Engine sees this as "new game" and emits `GameEnded` for the old one (wrongly), then `GameStarted` for what's actually the same game.
**How to avoid:** Two strategies, pick one:
1. **Treat it as a new game** (simpler) — emit GameEnded + GameStarted, accept that LIVE-04 history list resets. Document this behavior.
2. **Detect via PlayerID continuity** — if the new CREATE_GAME's PlayerIDs match the current game's, treat as state refresh. Complex; defer.
**Recommendation for v1:** Strategy 1. Document in engine docstring. Phase 3 can show "reconnected mid-game" cue if desired.
**Warning sign:** "Game over" announcement during normal play.

### Pitfall 8: Forgetting to reset partial-line decoder on reset
**What goes wrong:** File rotation: offset reset to 0, parser reset, but `_LineReader._partial` still contains "ate.DebugPrintPower() - TAG_CHA" from the old file's last truncated line. Next read combines this with the new file's first bytes, produces gibberish, hslog raises RegexParsingError on every line.
**How to avoid:** `_LineReader.reset()` is mandatory whenever the watcher resets. Test this case explicitly with a `truncation.log` synthesized fixture.

### Pitfall 9: wx.Timer started before parent window is shown
**What goes wrong:** If we call `Timer.Start(150)` before `wx.Frame.Show()`, on Windows the Timer can fire before the message loop is running, leading to events delivered to a half-constructed frame.
**How to avoid:** `GameTracker.start()` should be called *after* `frame.Show()` and `app.MainLoop()` is about to begin. Our integration point is `StoneReaderApp.OnInit()` — call `tracker.start()` as the last action before `return True` (after `self._frame.Show()`).

### Pitfall 10: Logging configured twice (once in __main__, once in app)
**What goes wrong:** `__main__.py` calls `logging.basicConfig(...)`, then `app.py` `OnInit` calls `logging.basicConfig(...)` again — the second call is a no-op (basicConfig only configures the root logger if no handlers are present), so we get whichever runs first. Inconsistent depending on entry path (CLI vs IDE).
**How to avoid:** Configure logging in exactly one place. Recommend `__main__.py` immediately after the `from stonereader.app import ...` line, before `app = StoneReaderApp()`. Use `logging.basicConfig(...)` once with explicit handlers.

## Code Examples

### Stdlib logging setup (D-16)

```python
# stonereader/services/_logging_config.py  — called from __main__.py once
import logging
import logging.handlers
import os
from pathlib import Path

LOG_DIR = Path.home() / ".stonereader"
LOG_FILE = LOG_DIR / "stonereader.log"


def configure_logging() -> None:
    """Configure root logger. Must be called exactly once at app entry."""
    LOG_DIR.mkdir(exist_ok=True)
    level = logging.DEBUG if os.environ.get("STONEREADER_DEBUG") == "1" else logging.INFO

    fmt = logging.Formatter(
        "%(asctime)s %(name)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    # Idempotent: don't add duplicates if called twice.
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        root.addHandler(file_handler)
    if not any(isinstance(h, logging.StreamHandler) and h is not file_handler for h in root.handlers):
        root.addHandler(console_handler)
```

### Idempotent log.config writer

```python
# stonereader/services/_log_config.py
import configparser
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

REQUIRED_POWER_SECTION = {
    "LogLevel": "1",
    "FilePrinting": "True",
    "ConsolePrinting": "False",
    "ScreenPrinting": "False",
    "Verbose": "True",
}


def log_config_path() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Blizzard" / "Hearthstone" / "log.config"


def ensure_log_config(path: Path | None = None) -> bool:
    """Write or update [Power] section in log.config. Returns True if changed."""
    path = path or log_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    parser = configparser.RawConfigParser()
    parser.optionxform = str  # preserve key case (Hearthstone is case-sensitive on some)
    if path.exists():
        parser.read(path, encoding="utf-8")

    changed = False
    if not parser.has_section("Power"):
        parser.add_section("Power")
        changed = True
    for key, value in REQUIRED_POWER_SECTION.items():
        if parser.get("Power", key, fallback=None) != value:
            parser.set("Power", key, value)
            changed = True

    if changed:
        with path.open("w", encoding="utf-8") as f:
            parser.write(f)
        logger.info("Updated log.config at %s", path)
    return changed
```

### Watcher tick loop (skeleton)

```python
# stonereader/services/_watcher.py
import logging
import os
from pathlib import Path
from typing import Callable, Optional

import wx

from stonereader.services._line_reader import _LineReader

logger = logging.getLogger(__name__)

POLL_INTERVAL_MS = 150
MAX_BUFFERED_LINES = 100_000


class PowerLogWatcher:
    def __init__(
        self,
        path_provider: Callable[[], Optional[Path]],
        on_lines: Callable[[list[str]], None],
        on_reset: Callable[[], None],
    ):
        self._path_provider = path_provider
        self._on_lines = on_lines
        self._on_reset = on_reset
        self._timer: Optional[wx.Timer] = None
        self._line_reader = _LineReader()
        self._offset = 0
        self._current_path: Optional[Path] = None

    def start(self, parent: wx.EvtHandler) -> None:
        self._timer = wx.Timer(parent)
        parent.Bind(wx.EVT_TIMER, lambda evt: self._tick())
        self._timer.Start(POLL_INTERVAL_MS)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.Stop()
            self._timer = None
        self._line_reader.reset()
        self._offset = 0
        self._current_path = None

    def _tick(self) -> None:
        try:
            self._do_tick()
        except Exception:
            logger.exception("watcher tick failed")  # D-04: log and continue

    def _do_tick(self) -> None:
        path = self._path_provider()
        if path is None or not path.exists():
            if self._current_path is not None:
                # File disappeared — reset state
                self._handle_reset()
            return

        if path != self._current_path:
            # New log file (Hearthstone restarted with new subdirectory)
            self._handle_reset()
            self._current_path = path
            self._maybe_backward_scan(path)  # D-13

        size = path.stat().st_size
        if size < self._offset:
            # Truncation
            self._handle_reset()
            self._maybe_backward_scan(path)
            size = path.stat().st_size
        if size == self._offset:
            return

        with path.open("rb") as fp:
            fp.seek(self._offset)
            chunk = fp.read(size - self._offset)

        lines = self._line_reader.feed(chunk)
        # Filter to GameState lines only (defense in depth; hslog also filters)
        lines = [ln for ln in lines if _is_gamestate_line(ln)]
        if len(lines) > MAX_BUFFERED_LINES:
            logger.warning("dropping %d lines beyond cap", len(lines) - MAX_BUFFERED_LINES)
            lines = lines[-MAX_BUFFERED_LINES:]

        self._offset = size
        if lines:
            self._on_lines(lines)

    def _handle_reset(self) -> None:
        self._offset = 0
        self._line_reader.reset()
        self._on_reset()

    def _maybe_backward_scan(self, path: Path) -> None:
        # See "Backward-scan for CREATE_GAME" algorithm above
        ...


def _is_gamestate_line(line: str) -> bool:
    if len(line) < 22 or not line.startswith("D "):
        return False
    return "GameState." in line[:80]  # cheap substring check before full match
```

(Production version expands the backward-scan helper; this skeleton illustrates the control flow only.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `FileSystemWatcher` / `inotify` | Stat-polling at 100-200ms | HDT 2015, Firestone 2019 | Required because Hearthstone holds Power.log open with write-lock; FS watchers fire unreliably. |
| Single `Logs/Power.log` flat path | Newest `Logs/Hearthstone_YYYY_MM_DD_HH_MM_SS/Power.log` subdirectory | Hearthstone v18+ (~2020) | Each Hearthstone session = new subdir. Old flat path remains as fallback for very old installs. |
| Hand-rolled regex parsing | `hslog` library | HearthSim open-sourced 2014 | hslog 1.18.0 (Jun 2025) is current; tracks Hearthstone patches. |
| `log_parser/` directory name | `services/` directory name | This phase (D-14) | Multi-phase plan unifies LogWatcher + ReplayEngine + GlobalHotkeyService under one folder. |
| Threaded log reader | wx.Timer on GUI thread | This phase (D-01) | Per-tick work is microseconds; threads buy nothing and add complexity. HDT moved to single-thread for the same reason in 2017. |

**Deprecated/outdated:**
- The `log_parser/` directory name from `docs/superpowers/specs/2026-04-08-stonereader-design.md` — superseded by D-14.
- The `wx.Timer at 100-200ms` recommendation in `docs/superpowers/research/2026-04-08-powerlog-parsing.md` — narrowed to 150ms by D-01.
- STATE.md's "hslog already installed transitively" — verified false; D-09 explicitly adds it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `Hearthstone.exe` binary name is the canonical Windows process name (case-insensitive). [ASSUMED based on HDT and Firestone usage; not verified against current Battle.net launcher] | Process detection | Auto-start fails silently if Battle.net renamed the exe. Mitigation: planner adds an `Hearthstone.exe` constant with a clear log line on detection. Post-launch verify on the user's machine. |
| A2 | Hearthstone still writes timestamped subdirectories `Hearthstone_YYYY_MM_DD_HH_MM_SS/` as of 2026. [ASSUMED — last verified by the in-repo research doc dated 2026-04-08; nothing newer.] | Path discovery | Path discovery fails. Mitigation: D-12 includes the flat-path fallback. |
| A3 | The `[Power]` section in `log.config` is sufficient to enable Power.log output (no other sections required for our use case). [VERIFIED via HDT's azeier gist — they write 6 sections, but only `[Power]` is required for Power.log output specifically.] | log.config bootstrap | None — gist verification was explicit. |
| A4 | hslog 1.18.0 will not change its `LogParser.read_line(str)` signature in a 1.x patch. [ASSUMED based on semantic versioning; hslog's PyPI doesn't pin a stability policy] | Parser API | Pin to `hslog>=1.18.0,<2`. Mitigation: lockfile via `uv add hslog`. |
| A5 | Subscribers will not retain multiple `GameState` snapshots. [ASSUMED of Phase 3 design.] | Memory bound | Memory growth unbounded if Phase 3 keeps history. Mitigation: document in engine docstring; Phase 3 spec follows. |
| A6 | The `~/.stonereader/` directory is writable when the app runs. [PARTIALLY VERIFIED — Phase 1 already writes the SQLite DB there; if that worked, log writing will too.] | Logging file | Logging silently disabled. Mitigation: `logging.basicConfig` falls back to console-only on file-handler failure. |
| A7 | Reconnection produces a new `CREATE_GAME` packet that hslog handles cleanly. [VERIFIED by in-repo research doc; HDT relies on this.] | Pitfall 7 | Reconnect is treated as new game per Strategy 1 above. Acceptable behavior for v1. |
| A8 | `wx.Timer.Notify` on Windows fires on the GUI thread synchronously with `app.MainLoop()`. [VERIFIED — wxPython documentation; standard event loop semantics.] | Threading | None. |
| A9 | Backward-scan ceiling of 1 MB (256×4KB) is sufficient to find `CREATE_GAME` even in long sessions. [ASSUMED based on HDT's same value.] | Backward scan | If a CREATE_GAME is more than 1 MB back in the file, we miss it and start from EOF — which is fine: the next CREATE_GAME triggers a new game. Worst case: we miss the *current* game's start until the next one. Mitigation: D-13 says "if no CREATE_GAME found in file, jump to EOF and wait" — this is exactly the fallback. |

**If user disagreement with any of A1–A9:** the planner should turn it into an explicit decision before plans are written. A1 (process name case) and A2 (timestamped subdirs) are highest risk for "looks like it works in tests but fails on real Hearthstone."

## Open Questions (RESOLVED)

1. **`GameStarted` payload — should it include the player's saved-deck match?**
   - What we know: LIVE-08 (auto-detect saved deck) is a Phase 3 requirement, not Phase 2.
   - What's unclear: Should `GameStarted.player_deck_match: Optional[DeckSummary]` be on the event in Phase 2, or should Phase 3 do the matching against `cardsDrawnThisGame` independently?
   - RESOLVED: **Phase 2 emits raw `GameStarted` with hero classes, game_type, format_type only**. Phase 3 watches `CardDrawn` events and runs match logic against saved decks. Keeps Phase 2 free of `db.py` coupling.

2. **Should the engine retain previous `GameState` snapshots for diffing in Phase 3?**
   - What we know: D-15 says "no packet history retained." Doesn't address state history.
   - What's unclear: Phase 3 will want diffs ("the new card on opponent's board is X"). Should the engine compute diffs and emit them as part of events, or should subscribers diff the snapshots they receive?
   - RESOLVED: **Engine emits `(event, state)` tuples to subscribers (Plan 02-07). No internal snapshot history retained — subscribers diff if they need to.**

3. **What's the behavior on `CorruptLogError` (NUL bytes)?**
   - What we know: hslog raises this; we catch in `parser.py`.
   - What's unclear: Skip the line and continue, or invalidate the entire current game?
   - RESOLVED: **Plan 02-05 — skip line, log at ERROR level, continue parsing. Raise `ParserError` only on uncaught exceptions from hslog.**

4. **Process name on Battle.net cloud-stream / GeForce Now installs?**
   - What we know: Local Hearthstone is `Hearthstone.exe`.
   - What's unclear: Cloud streams might run as `Hearthstone-Win64-Shipping.exe` or similar. Out of scope for v1 per "Windows-only, screen-reader-only" but worth a note.
   - RESOLVED: **Plan 02-03 — assume `Hearthstone.exe` only. Document the limitation in `_process_detect.py` docstring; cloud-streaming installs are out of v1 scope.**

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.12 | — |
| `hearthstone` library | Existing usage + hslog transitive | ✓ | 9.20.2 | — |
| `wxPython` | wx.Timer | ✓ | 4.2.5 | — |
| `hslog` | Parser (D-09) | ✗ | — | None — must install. `uv add hslog` |
| `psutil` | Process detect (D-03) | ✗ | — | `pywin32` (already installed) — but recommend installing psutil |
| `pywin32` | Fallback for psutil; winreg always-available transitively | ✓ | 311 (transitive via accessible-output2) | n/a |
| `Hearthstone.exe` | Auto-start trigger | n/a (runtime check) | n/a | Not blocking — watcher idle until detected |
| `%LOCALAPPDATA%\Blizzard\Hearthstone\` | log.config + Logs/ | n/a (runtime check) | n/a | Not blocking — bootstrap creates if absent |

**Missing dependencies with no fallback:**
- `hslog` — D-09 explicit requirement. Install via `uv add hslog`.
- `psutil` — D-03 says "or win32api"; Claude's-discretion settled by this RESEARCH on `psutil`. Install via `uv add psutil`.

**Missing dependencies with fallback:**
- None blocking. If `psutil` install were to fail in CI, falling back to win32api is a planner-discretion swap; `pywin32` is already installed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (existing, in pyproject `[dependency-groups] dev`) |
| Config file | None — pytest uses defaults; `tests/conftest.py` provides `MockSpeechService` |
| Quick run command | `uv run pytest tests/test_services/ -x` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOG-01 | Watcher detects new bytes appended to a fixture file within one tick | unit (with file fixtures) | `uv run pytest tests/test_services/test_watcher.py::test_appended_lines_picked_up_within_one_tick -x` | ❌ Wave 0 |
| LOG-01 | Real Power.log fixture (`mid_game.log`) is parsed end-to-end into events + final GameState | integration | `uv run pytest tests/test_services/test_engine.py::test_mid_game_fixture_emits_expected_events -x` | ❌ Wave 0 |
| LOG-01 | LogParser receives only `GameState.*` lines (PowerTaskList filtered out) | unit | `uv run pytest tests/test_services/test_watcher.py::test_powertasklist_lines_filtered -x` | ❌ Wave 0 |
| LOG-02 | Feeding hslog the same log file twice in sequence does NOT produce duplicate events (hslog's PowerTaskList drop is verified) | unit | `uv run pytest tests/test_services/test_parser.py::test_powertasklist_dropped_by_hslog -x` | ❌ Wave 0 |
| LOG-02 | A fixture containing both PowerTaskList and GameState versions of every line produces exactly N events, where N matches the GameState-only line count | integration | `uv run pytest tests/test_services/test_engine.py::test_dual_source_fixture_no_duplicates -x` | ❌ Wave 0 |
| LOG-03 | Watcher detects file truncation (size shrinks) and resets offset + parser state | unit | `uv run pytest tests/test_services/test_watcher.py::test_truncation_resets_offset_and_parser -x` | ❌ Wave 0 |
| LOG-03 | After reset, lines from the new file are parsed correctly without picking up partial decode buffer from previous file | unit | `uv run pytest tests/test_services/test_watcher.py::test_reset_clears_partial_line_buffer -x` | ❌ Wave 0 |
| LOG-03 | When `hearthstone.exe` disappears from process list, watcher pauses and resets parser state | unit (mock psutil) | `uv run pytest tests/test_services/test_tracker.py::test_process_gone_resets_state -x` | ❌ Wave 0 |
| LOG-04 | `ensure_log_config` creates file with `[Power]` section when none exists | unit (tmp_path) | `uv run pytest tests/test_services/test_log_config.py::test_creates_file_when_absent -x` | ❌ Wave 0 |
| LOG-04 | `ensure_log_config` updates `[Power]` keys without destroying other sections | unit (tmp_path) | `uv run pytest tests/test_services/test_log_config.py::test_preserves_other_sections -x` | ❌ Wave 0 |
| LOG-04 | `ensure_log_config` is idempotent — second call returns False (no change) | unit | `uv run pytest tests/test_services/test_log_config.py::test_idempotent_when_correct -x` | ❌ Wave 0 |
| LOG-05 (D-19) | `tracker.start()` then `tracker.stop()` does not leak Timer or threads | unit (with wx.App fixture) | `uv run pytest tests/test_services/test_tracker.py::test_start_stop_clean -x` | ❌ Wave 0 |
| LOG-05 (D-19) | A 1000-line fixture processed in a single tick completes in under 50ms (proxy for "doesn't block UI") | unit (timing) | `uv run pytest tests/test_services/test_engine.py::test_tick_under_50ms -x` | ❌ Wave 0 |

**Manual-only validations (not automated):**
- Real Hearthstone game runs with the real watcher hooked up — captured by HVC items in `verification.md` post-Phase-2.
- log.config persistence across machine reboots.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_services/ -x` (services-only, fast feedback during phase work)
- **Per wave merge:** `uv run pytest tests/ -v` (full suite — ensures Phase 2 didn't break Phase 1)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

The following must exist before Wave 1 begins:

- [ ] `tests/test_services/__init__.py` — empty package marker
- [ ] `tests/test_services/test_log_config.py` — covers LOG-04 (3 tests above)
- [ ] `tests/test_services/test_log_path.py` — covers D-12 path discovery
- [ ] `tests/test_services/test_process_detect.py` — covers D-03 (mock psutil)
- [ ] `tests/test_services/test_watcher.py` — covers LOG-01, LOG-03 (file polling + reset)
- [ ] `tests/test_services/test_parser.py` — covers LOG-02 (hslog wrapper)
- [ ] `tests/test_services/test_engine.py` — covers integration: LOG-01/02 end-to-end with fixtures
- [ ] `tests/test_services/test_tracker.py` — covers LOG-05/D-19 (facade lifecycle)
- [ ] `tests/test_services/conftest.py` — fixture loaders, mock wx.App, mock psutil
- [ ] `tests/fixtures/log/match_start.log` — D-17 capture
- [ ] `tests/fixtures/log/mid_game.log` — D-17 capture
- [ ] `tests/fixtures/log/game_end.log` — D-17 capture
- [ ] `tests/fixtures/log/reconnect.log` — D-17 capture
- [ ] `tests/fixtures/log/battlegrounds.log` — D-17 capture (optional v1, stress test)
- [ ] Framework install: `uv add hslog psutil` — required before any test runs

**No conftest changes** to existing `tests/conftest.py` are required — `MockSpeechService` is unchanged. New `tests/test_services/conftest.py` adds local fixtures only.

## Project Constraints (from CLAUDE.md)

- **Tech stack lock:** wxPython + accessible_output2 + hearthstone library. **No framework changes.** ✓ (Phase 2 adds hslog + psutil — both supporting libraries, not framework-level swaps.)
- **Platform: Windows only.** ✓ Phase 2 uses `winreg` (stdlib), `psutil` (cross-platform), and Windows-style paths (`%LOCALAPPDATA%`). Tests must mock paths and `winreg` cleanly so they run on the WSL/Linux CI environment.
- **EVT_CHAR_HOOK rule.** ✓ Not relevant — Phase 2 has no UI.
- **Architecture: MVP.** ✓ Phase 2 is headless service; the boundary at `services.GameTracker` is the M (model) for Phase 3's P (presenter) and V (view).
- **Immutability: frozen dataclasses for game state.** ✓ D-07/D-18 lock; proposed `GameState` diff uses `frozen=True` and `Tuple[...]` for all collections.
- **Speech rule: views never call SpeechService directly — only presenters call `self._speech`.** ✓ Phase 2 has no views and no presenters; the bootstrap one-line "log.config created" announcement (D-11) is fired from `app.py` (which is the integration shell, owns SpeechService). The service itself never imports SpeechService.

## Sources

### Primary (HIGH confidence — verified this session)
- `https://raw.githubusercontent.com/HearthSim/python-hslog/master/hslog/parser.py` — LogParser, ParsingState, PowerHandler implementations. Confirms `read_line(str)` signature, `_game_state_processor = "GameState"` filtering, "ignore until CREATE_GAME" line 1132.
- `https://raw.githubusercontent.com/HearthSim/python-hslog/master/hslog/tokens.py` — Regex catalogue (POWERLOG_LINE_RE, BLOCK_START variants, TAG_CHANGE_RE, etc.).
- `https://raw.githubusercontent.com/HearthSim/python-hslog/master/hslog/exceptions.py` — Exception hierarchy.
- `https://raw.githubusercontent.com/HearthSim/python-hslog/master/hslog/export.py` — BaseExporter dispatch dict, EntityTreeExporter pattern.
- `https://pypi.org/pypi/hslog/json` (JSON API) — confirmed hslog 1.18.0 published 2025-06-04, requires_dist `aniso8601`, `hearthstone`.
- `https://raw.githubusercontent.com/HearthSim/Hearthstone-Deck-Tracker/master/HearthWatcher/LogReader/LogFileWatcher.cs` — Reference implementation: 100ms polling, byte-offset, FileShare.ReadWrite, MAX_LOG_LINE_BUFFER=100_000, FindInitialOffset backward-scan.
- `https://github.com/HearthSim/Hearthstone-Deck-Tracker/blob/master/Hearthstone%20Deck%20Tracker/Hearthstone/Player.cs` — HDT Player property list (Hand, Deck, Board, Graveyard, CardsPlayedThisMatch, etc.).
- `https://github.com/Zero-to-Heroes/firestone/blob/master/libs/game-state/src/lib/models/deck-state.ts` — Firestone DeckState shape (hand, deck, board, cardsPlayedThisMatch, cardsDrawnByTurn).
- `https://docs.python.org/3/library/codecs.html#codecs.IncrementalDecoder` — Buffered UTF-8 decode contract.
- `https://gist.githubusercontent.com/azeier/60b525890b3bd772a60d/raw` — Canonical Hearthstone log.config contents (6 sections, all keys verified).
- `docs/superpowers/research/2026-04-08-powerlog-parsing.md` (in-repo) — Power.log line format, packet types, file behavior, edge cases.
- Source code reads of `stonereader/models/game_state.py`, `stonereader/db.py`, `stonereader/app.py`, `stonereader/__main__.py` — current state verified locally.

### Secondary (MEDIUM confidence — verified via Context7 / docs)
- psutil recipes via Context7 ID `/giampaolo/psutil` — `process_iter(["name"])` idiom. Source: `github.com/giampaolo/psutil/blob/master/docs/recipes.md`.
- psutil API: `Process.exe()` returns absolute path, cached. Source: `github.com/giampaolo/psutil/blob/master/docs/api.md`.

### Tertiary (LOW confidence — flagged in Assumptions Log)
- A1 — Hearthstone.exe canonical name: not formally verified against current Battle.net launcher.
- A2 — Timestamped subdirs as of 2026: relies on in-repo research doc dated 2026-04-08.
- A4 — hslog 1.18.0 → 1.x stability: assumed via semver convention.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — hslog source verified line-by-line; psutil docs verified; Python stdlib well-known.
- Architecture: **HIGH** — HDT and Firestone open-source code verified; D-01 through D-19 already lock most decisions.
- Pitfalls: **MEDIUM** — pitfalls 1-6 are widely-documented (HDT issue tracker, hslog source); pitfalls 7-10 are inferences from the codebase + general wxPython/Python knowledge.
- GameState diff (D-08): **MEDIUM** — backed by HDT/Firestone shape mappings, but the planner should review naming conventions against existing `models/game_state.py` style before locking.

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (hslog/psutil are stable; HDT/Firestone unlikely to refactor in 30 days; Hearthstone client patches may shift log format details — re-verify if a major patch lands)
