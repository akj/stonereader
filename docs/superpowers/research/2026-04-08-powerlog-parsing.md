# Power.log Parsing Research

Research findings for the Log Parser slice of StoneReader. Three areas investigated: the `hslog` Python library, the Power.log format itself, and how HDT/Firestone approach the problem.

## Decision: Use hslog + Custom Watcher

**Use `hslog.LogParser.read_line()` for parsing, build our own file watcher.**

hslog is already available — it ships as a separate package but is installed alongside the `hearthstone` dependency we already have. It provides exactly what we need: line-by-line incremental parsing (`read_line()`), a packet tree structure, and an entity exporter that builds full game state with zone tracking. No point reimplementing the regex-heavy log parsing when a battle-tested, actively maintained library does it.

What hslog does NOT provide is a file watcher or a live game state tracker with event emission. That's our `watcher.py` and `engine.py`.

### Architecture

```
Power.log  →  watcher.py (file poller)  →  parser.py (hslog wrapper)  →  engine.py (game state)
                wx.Timer 100-200ms            LogParser.read_line()         GameState snapshots
                byte-offset tracking          PacketTree + export()         event emission
```

## hslog Library (HearthSim/python-hslog)

### What It Provides

- **`LogParser`** — line-by-line incremental parser. Key methods:
  - `read_line(line)` — parse a single log line, maintaining state across calls
  - `read(fp)` — parse a file-like object (calls `read_line` per line)
  - `flush()` — finalize any pending state
  - `games` — list of completed `PacketTree` objects
- **`PacketTree`** — hierarchical packet structure (CreateGame, FullEntity, TagChange, Block, etc.)
- **`EntityTreeExporter`** — converts a PacketTree into a `hearthstone.entities.Game` with full entity state
  - Handles all packet types: FULL_ENTITY, SHOW_ENTITY, HIDE_ENTITY, CHANGE_ENTITY, TAG_CHANGE
  - Handles dormant minions (`handle_cached_tag_for_dormant_change`)
  - Zone tracking via `Game.in_zone(zone)` method
- **`FriendlyPlayerExporter`** — identifies which player is "us" by analyzing revealed cards

### Entity Model (from `hearthstone.entities`)

- `Game` — root entity, contains `_entities: Dict[int, Entity]`, `players` list
  - `in_zone(zone)` — query entities by zone
  - `find_entity_by_id(id)` — lookup by entity ID
  - `current_player` — whose turn it is
- `Player` — extends Entity, represents a player
- `Card` — extends Entity, represents a card/minion/hero
  - `card_id` — current card ID (changes on transform)
  - `initial_card_id` — original card ID
  - `zone` — current zone (from tags)
  - `controller` — owning player
  - `reveal()`, `hide()`, `change()` — state mutations

### Verified Available

```python
# Already importable in our venv
from hslog import LogParser
from hslog.export import EntityTreeExporter, FriendlyPlayerExporter
from hearthstone.entities import Game, Player, Card
from hearthstone.enums import Zone, GameTag, BlockType, GameType, FormatType
```

Key zones: `PLAY=1, DECK=2, HAND=3, GRAVEYARD=4, SETASIDE=6, SECRET=7`
Key block types: `ATTACK=1, POWER=3, TRIGGER=5, DEATHS=6, PLAY=7, FATIGUE=8`
Game types: `GT_RANKED=7, GT_CASUAL=8, GT_ARENA=5, GT_BATTLEGROUNDS=23`

## Power.log Format

### Enabling Logging

A `log.config` file must exist. StoneReader should check for it and offer to create it.

- **Windows:** `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config`
- **macOS:** `~/Library/Preferences/Blizzard/Hearthstone/log.config`

Minimum contents:
```ini
[Power]
LogLevel=1
FilePrinting=True
ConsolePrinting=False
ScreenPrinting=False
Verbose=True
```

### Log Location

- **Windows:** `C:\Program Files (x86)\Hearthstone\Logs\Power.log`
- **macOS:** `/Applications/Hearthstone/Logs/Power.log`

Recent Hearthstone versions may write logs to timestamped subdirectories. HDT handles this by checking which directory is locked by the game process.

### Line Format

```
D HH:MM:SS.ttttttt Source.Method() - content
```

**Critical:** Every line is logged twice — once by `GameState.DebugPrintPower()` (immediate) and once by `PowerTaskList.DebugPrintPower()` (at animation time). Parse only `GameState` lines. hslog handles this — it understands both sources.

Timestamps have no date component. Must handle midnight rollover.

### Key Log Packets

| Packet | Meaning |
|--------|---------|
| `CREATE_GAME` | Game start. Followed by GameEntity, Player, and FULL_ENTITY for all initial entities |
| `FULL_ENTITY` | New entity created. `CardID=` blank means hidden (opponent's deck) |
| `TAG_CHANGE` | Single tag mutation on an entity. This is how zone changes, turn changes, game end are expressed |
| `SHOW_ENTITY` | Reveals a previously hidden entity (card drawn by effect, jousted card) |
| `HIDE_ENTITY` | Conceals a known entity (shuffled back to deck) |
| `CHANGE_ENTITY` | Transform effect (Shifter Zerus). New CardID on existing entity |
| `BLOCK_START/END` | Groups related changes. BlockType tells you what caused them |
| `META_DATA` | Animation/targeting info, non-mutative |

### Detecting Game Events

| Event | Log Signal |
|-------|-----------|
| Game start | `CREATE_GAME` |
| Game end | `TAG_CHANGE Entity=GameEntity tag=STATE value=COMPLETE` |
| Win/loss | `TAG_CHANGE tag=PLAYSTATE value=WON/LOST` on player entities |
| Card drawn | `TAG_CHANGE tag=ZONE value=HAND` (from DECK zone) |
| Card played | `BLOCK_START BlockType=PLAY` + `TAG_CHANGE tag=ZONE value=PLAY` |
| Turn change | `TAG_CHANGE tag=CURRENT_PLAYER value=1` |
| Attack | `BLOCK_START BlockType=ATTACK` |
| Minion death | Inside `BLOCK_START BlockType=DEATHS`, `TAG_CHANGE tag=ZONE value=GRAVEYARD` |
| Secret played | `TAG_CHANGE tag=ZONE value=SECRET` |
| Secret triggered | `BLOCK_START BlockType=TRIGGER` with secret entity |
| Discover/Choose | `EntityChoices` lines with `ChoiceType=GENERAL` |
| Transform | `CHANGE_ENTITY` or new `FULL_ENTITY` + original to SETASIDE |
| Token created | `FULL_ENTITY` with `CardID` inside a gameplay `BLOCK_START` (not during CREATE_GAME) |
| Game mode | `CREATE_GAME` tags: `GAME_TYPE` (7=Ranked, 8=Casual, 23=BG), `FORMAT_TYPE` (1=Wild, 2=Standard) |

### File Behavior

- **Truncated on client restart**, appended within a session
- Grows without bound during a session (long BG games can be huge)
- Multiple games appear sequentially — detect boundaries via `CREATE_GAME`
- Flushed line-by-line by Unity (real-time tailing works)
- **Reconnection:** dumps full state as a new `CREATE_GAME` block

### Edge Cases

- **Opponent hand:** Cards arrive with blank `CardID`. Only known when revealed via `SHOW_ENTITY`
- **Generated cards:** `FULL_ENTITY` with `CardID` appearing inside gameplay blocks (not CREATE_GAME)
- **Shuffle into deck:** `TAG_CHANGE tag=ZONE value=DECK` or new `FULL_ENTITY` in DECK mid-game
- **Joust/reveal:** `BLOCK_START BlockType=JOUST` with `SHOW_ENTITY` then `HIDE_ENTITY`
- **Multiple games per session:** Each starts with `CREATE_GAME`, no explicit separator needed

## HDT & Firestone Approach Analysis

### File Watching — Universal Pattern

Both trackers use **stat-based file polling**, NOT filesystem event watchers. `FileSystemWatcher`/`fs.watch` are unreliable on Windows when another process holds a write lock.

- **HDT (C#):** 100ms polling interval. Opens file with `FileShare.ReadWrite`. Tracks byte offset, reads only new bytes.
- **Firestone (TypeScript):** 200ms polling interval via `fs.watchFile` (stat-polling). Same byte-offset pattern.

**For StoneReader:** Use `wx.Timer` at 100-200ms to poll file size/read new bytes. This stays on the GUI thread (no threading needed), matches the spec's design.

### Incremental Parsing — Line-Level

Both parse incrementally at the line level, never re-parsing the full file.

- **Line completeness guard:** Only process lines ending with `\n`. If a read returns a partial line, buffer it and wait for the next poll.
- **Startup optimization:** HDT scans backward from end-of-file to find the current game boundary, skipping old data.
- **Line filtering at watcher level:** HDT rejects irrelevant lines (not `GameState.` or `PowerTaskList.`) before they reach the parser. Performance-critical for large logs.

### Game State Model

- **HDT:** Mutable `Dictionary<int, Entity>`. Each entity has tags dict. State mutated in-place on each TAG_CHANGE.
- **hslog:** Builds immutable `PacketTree`, then `EntityTreeExporter.export()` produces a `Game` with mutable entities. Designed for post-hoc analysis, not streaming.

**Implication for StoneReader:** hslog's `LogParser.read_line()` supports streaming, but the export step is designed to run once on a complete game. For live tracking, we have two options:
1. Re-export after each meaningful batch of lines (simple but potentially wasteful)
2. Maintain our own mutable game state, using hslog only for parsing lines into structured packets, then applying changes ourselves

Option 2 is what HDT does and is more appropriate for a live tracker. Use hslog to parse log lines into packets, then apply those packets to our own `GameState` model (which we already have in `stonereader/models/game_state.py`).

### Key Patterns to Adopt

1. **Byte-offset polling with shared file access** — 100-200ms via wx.Timer
2. **Line completeness guard** — buffer partial lines between polls
3. **Backward scan on startup** — find the current game, skip old data
4. **Line filtering before parsing** — reject non-`GameState.DebugPrintPower` lines early
5. **Deferred tag processing** — queue tag changes during entity creation, apply after player determination
6. **Buffer size cap** — limit buffered lines to prevent OOM in long BG games (HDT uses 100K)
7. **log.config management** — check for it on startup, offer to create/update it

### Pitfalls to Avoid

- **Don't use filesystem watchers** — unreliable on Windows with locked files
- **Don't re-parse the full file** — byte-offset tracking is essential
- **Don't split on bytes naively** — partial UTF-8 characters at chunk boundaries can corrupt card names
- **Don't ignore `PowerTaskList` vs `GameState` distinction** — everything is logged twice
- **Don't assume stable log format** — BLOCK_START regex has changed across patches; hslog handles historical variants

## Implementation Plan for `log_parser/`

### `watcher.py` — File Poller

- `wx.Timer` at 150ms interval
- Track byte offset into Power.log
- Open with shared read access on each tick
- Read new bytes, split into complete lines (buffer incomplete trailing line)
- Filter: only pass `GameState.DebugPrintPower` lines to parser
- Detect file truncation (size < offset) — reset offset to 0
- Auto-detect Power.log path from standard locations
- Configurable path override

### `parser.py` — hslog Wrapper

- Thin wrapper around `hslog.LogParser`
- Feed lines via `read_line()`
- After each batch of lines, check `parser.games` for completed games
- For live tracking: access the in-progress packet tree and extract structured events
- Emit typed event objects: `CardDrawn`, `CardPlayed`, `TurnChanged`, `GameStarted`, `GameEnded`, etc.

### `engine.py` — Game State Builder

- Maintains running `GameState` (our frozen dataclass model)
- Consumes events from parser
- Produces new `GameState` snapshots on meaningful changes
- Tracks which player is "us" via `FriendlyPlayerExporter` logic
- Handles game boundaries (new `CREATE_GAME` = new game)
- On game end: emit completed `GameRecord` for persistence to SQLite
