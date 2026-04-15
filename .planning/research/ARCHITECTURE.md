# Architecture Research

**Domain:** Accessible Hearthstone deck tracker / replay viewer (wxPython desktop app)
**Researched:** 2026-04-14
**Confidence:** HIGH

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                           │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ DeckManager  │ │ LiveTracker  │ │   ReplayViewer        │   │
│  │ Presenter    │ │ Presenter    │ │   Presenter           │   │
│  │ + View       │ │ + View       │ │   + View              │   │
│  └──────┬───────┘ └──────┬───────┘ └───────────┬───────────┘   │
│         │                │                      │               │
├─────────┴────────────────┴──────────────────────┴───────────────┤
│                     Application Services                         │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ GameEngine   │ │ GlobalHotkey │ │   ReplayEngine        │   │
│  │ (state from  │ │ Service      │ │   (turn navigation)   │   │
│  │  log events) │ │ (Win32 API)  │ │                       │   │
│  └──────┬───────┘ └──────┬───────┘ └───────────┬───────────┘   │
│         │                │                      │               │
├─────────┴────────────────┴──────────────────────┴───────────────┤
│                     Infrastructure Layer                         │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ LogWatcher   │ │ InputLayer   │ │   SpeechService       │   │
│  │ (file tail   │ │ (EVT_CHAR_   │ │   (accessible_        │   │
│  │  + parser)   │ │  HOOK routing│ │    output2)           │   │
│  └──────┬───────┘ └──────────────┘ └───────────────────────┘   │
│         │                                                       │
├─────────┴───────────────────────────────────────────────────────┤
│                     Data Layer                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ Power.log    │ │ SQLite DB    │ │ .hsreplay XML files   │   │
│  │ (Hearthstone)│ │ (decks,games)│ │ (saved replays)       │   │
│  └──────────────┘ └──────────────┘ └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| **LogWatcher** | Tail Power.log, detect new lines, feed to parser | threading.Thread + file seek/read polling loop |
| **GameEngine** | Parse log lines into game state snapshots, track remaining deck, opponent plays | hslog LogParser + custom state reducer producing frozen GameState |
| **LiveTrackerPresenter** | Zone navigation over live game zones (deck, opponent played, hand tracking), speech announcements | ZoneNavigationMixin + BasePresenter, receives GameState via callback |
| **LiveTrackerView** | Passive wx.Panel with ListCtrl zones for deck/opponent/hand | Standard MVP view, updated via presenter callbacks |
| **GlobalHotkeyService** | Register system-wide hotkeys (e.g. Ctrl+Alt+D for deck), announce via speech even when Hearthstone has focus | wx.Frame.RegisterHotKey + win32con + EVT_HOTKEY binding |
| **DeckManagerPresenter** | Import deckstrings, browse saved decks, select active deck for tracking | ZoneNavigationMixin + BasePresenter, CRUD via SQLite |
| **DeckManagerView** | Passive panel with deck list, card list, import dialog | wx.Panel + ListCtrl |
| **ReplayEngine** | Load .hsreplay XML, build ordered GameState snapshots, navigate turns | python-hsreplay parser + EntityTreeExporter |
| **ReplayViewerPresenter** | Turn-by-turn and action-by-action navigation with board/hand/log zones | ZoneNavigationMixin + BasePresenter |
| **ReplayViewerView** | Passive panel with turn list, board state, action log | wx.Panel + ListCtrl zones |

## Recommended Project Structure

```
stonereader/
├── models/
│   ├── card.py              # Card, CardDatabase (existing)
│   ├── deck.py              # Deck (existing)
│   ├── game_state.py        # GameState, GameEntity, Hero (existing)
│   └── replay.py            # ReplayState (existing)
├── services/
│   ├── log_watcher.py       # LogWatcher thread — tails Power.log
│   ├── game_engine.py       # GameEngine — log lines to GameState
│   ├── global_hotkeys.py    # GlobalHotkeyService — Win32 RegisterHotKey
│   └── replay_engine.py     # ReplayEngine — .hsreplay to GameState sequence
├── presenters/
│   ├── base.py              # BasePresenter, ZoneNavigationMixin (existing)
│   ├── card_browser.py      # CardBrowserPresenter (existing)
│   ├── deck_manager.py      # DeckManagerPresenter (new)
│   ├── live_tracker.py      # LiveTrackerPresenter (new)
│   └── replay_viewer.py     # ReplayViewerPresenter (new)
├── views/
│   ├── base.py              # View helpers (existing)
│   ├── card_browser.py      # CardBrowserPanel (existing)
│   ├── deck_manager.py      # DeckManagerPanel (new)
│   ├── live_tracker.py      # LiveTrackerPanel (new)
│   └── replay_viewer.py     # ReplayViewerPanel (new)
├── app.py                   # MainWindow, StoneReaderApp (existing)
├── input_layer.py           # InputLayer (existing)
├── speech_service.py        # SpeechService (existing)
└── db.py                    # SQLite schema (existing, extended)
```

### Structure Rationale

- **services/**: New directory for components that are neither models, presenters, nor views. LogWatcher, GameEngine, GlobalHotkeyService, and ReplayEngine are application services that sit between the data layer and the presenters. They do not touch wx widgets and are independently testable.
- **models/ stays flat**: The existing frozen dataclass models (GameState, GameEntity, Deck) already cover the domain. No new model files needed -- the existing models are sufficient for live tracking and replay viewing.
- **presenters/ and views/ expand in parallel**: Each new tab gets one presenter and one view file. The established pattern (CardBrowserPresenter + CardBrowserPanel) is repeated for DeckManager, LiveTracker, and ReplayViewer.

## Architectural Patterns

### Pattern 1: Worker Thread with wx.CallAfter Bridge

**What:** LogWatcher runs in a daemon thread, reads new log lines via file polling, and posts game state updates to the main thread via `wx.CallAfter`.

**When to use:** Any long-running or blocking I/O that must not freeze the wxPython event loop. Log file tailing is the primary use case.

**Trade-offs:**
- Pro: Simple, proven wxPython pattern. No locks needed for GUI updates since wx.CallAfter marshals the call to the main thread.
- Pro: Daemon thread auto-terminates when main thread exits.
- Con: Must be careful not to flood wx.CallAfter during rapid log bursts (batch lines, emit snapshots not individual changes).
- Con: Thread shutdown must be clean -- set a stop event, join with timeout.

**Example:**
```python
import threading
import wx

class LogWatcher(threading.Thread):
    """Tail Power.log and emit game state updates to the main thread."""

    def __init__(self, log_path: str, callback: Callable[[GameState], None]) -> None:
        super().__init__(daemon=True)
        self._log_path = log_path
        self._callback = callback
        self._stop_event = threading.Event()

    def run(self) -> None:
        with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)  # Seek to end -- only read new lines
            while not self._stop_event.is_set():
                line = f.readline()
                if line:
                    new_state = self._engine.process_line(line)
                    if new_state is not None:
                        wx.CallAfter(self._callback, new_state)
                else:
                    self._stop_event.wait(0.1)  # Poll every 100ms

    def stop(self) -> None:
        self._stop_event.set()
```

### Pattern 2: State Snapshot Pipeline (Immutable State Flow)

**What:** Log lines flow through a pipeline: raw text -> parsed packets -> entity mutations -> frozen GameState snapshot. Each stage is pure (or nearly pure). The final GameState is an immutable frozen dataclass. Presenters never see intermediate state.

**When to use:** Converting continuous log output into discrete UI-renderable snapshots.

**Trade-offs:**
- Pro: Matches existing immutable model pattern (`@dataclass(frozen=True)`).
- Pro: Thread-safe by construction -- the snapshot posted via wx.CallAfter is immutable.
- Pro: Testable -- feed known lines, assert known GameState output.
- Con: Constructing a new frozen GameState on every meaningful change has allocation overhead, but this is negligible for the event rate (a few events per second at peak).

**Example:**
```python
@dataclass(frozen=True)
class TrackerState:
    """Live tracking view model derived from GameState."""
    turn: int
    remaining_deck: Tuple[Tuple[Card, int], ...]  # Cards left, with counts
    opponent_played: Tuple[Tuple[Card, int], ...]  # What opponent has played
    opponent_hand: Tuple[OpponentHandCard, ...]     # Cards in hand + turn drawn
    player_hero: Hero
    opponent_hero: Hero
```

### Pattern 3: Global Hotkey as Service (Not InputLayer Extension)

**What:** Global hotkeys use `wx.Frame.RegisterHotKey` with `win32con` constants, bound via `wx.EVT_HOTKEY`. This is a separate service from InputLayer because: (a) global hotkeys work when the app is not focused, while InputLayer handles in-app keyboard routing, and (b) global hotkeys call SpeechService directly for announcements, bypassing presenters.

**When to use:** Any hotkey that must work while Hearthstone has focus and StoneReader is in the background.

**Trade-offs:**
- Pro: wxPython has built-in `RegisterHotKey` support on Windows -- no need for ctypes or separate message loops.
- Pro: EVT_HOTKEY events arrive on the main thread, so speech calls are thread-safe.
- Con: Windows-only (but project is Windows-only by design).
- Con: Some key combinations may conflict with other apps or the OS. Must handle registration failure gracefully.
- Con: `win32con` import required -- pywin32 dependency.

**Example:**
```python
import win32con

class GlobalHotkeyService:
    HOTKEY_REMAINING_DECK = 1
    HOTKEY_OPPONENT_PLAYED = 2

    def __init__(self, frame: wx.Frame, speech: SpeechService) -> None:
        self._frame = frame
        self._speech = speech
        self._game_engine: Optional[GameEngine] = None
        self._register_hotkeys()

    def _register_hotkeys(self) -> None:
        self._frame.RegisterHotKey(
            self.HOTKEY_REMAINING_DECK,
            win32con.MOD_CONTROL | win32con.MOD_ALT,
            win32con.VK_F1
        )
        self._frame.Bind(
            wx.EVT_HOTKEY, self._on_remaining_deck,
            id=self.HOTKEY_REMAINING_DECK
        )

    def _on_remaining_deck(self, evt: wx.KeyEvent) -> None:
        if self._game_engine and self._game_engine.current_state:
            state = self._game_engine.current_state
            remaining = state.player_deck_count
            self._speech.speak(f"{remaining} cards remaining in deck")
```

### Pattern 4: Presenter-per-Tab with Shared Services

**What:** Each tab (DeckManager, LiveTracker, ReplayViewer) gets its own Presenter + View pair, but they share services (GameEngine, SpeechService, DB connection) injected through the constructor. Services are owned by MainWindow and passed down during tab construction.

**When to use:** Always. This is the existing pattern (CardBrowserPresenter receives SpeechService and CardDatabase).

**Trade-offs:**
- Pro: Clean dependency injection. Services are testable with mocks.
- Pro: Tab isolation -- each presenter manages its own zone navigation state independently.
- Con: Cross-tab communication (e.g. "select deck in DeckManager, use it in LiveTracker") requires a coordination mechanism. Use a simple callback or shared reference, not events.

## Data Flow

### Live Game Tracking Flow

```
Power.log (Hearthstone writes continuously)
    |
    | [file seek + readline, 100ms poll]
    v
LogWatcher (daemon thread)
    |
    | [raw line string]
    v
GameEngine.process_line()
    |
    | [regex parse, entity tracking, state mutation]
    v
GameState (frozen dataclass snapshot)
    |
    | [wx.CallAfter posts to main thread]
    v
LiveTrackerPresenter._on_game_state_updated(state)
    |
    ├──> Derives TrackerState (remaining deck, opponent played, etc.)
    ├──> Calls self._speech.speak() for auto-announcements (turn change, draw)
    ├──> Calls self._notify_view() to sync ListCtrl display
    |
    v
LiveTrackerView._on_state_changed(tracker_state)
    |
    └──> Updates ListCtrl items
```

### Global Hotkey Announcement Flow

```
User presses Ctrl+Alt+F1 (Hearthstone has focus)
    |
    | [Windows WM_HOTKEY message]
    v
wx.Frame receives EVT_HOTKEY (even when minimized/background)
    |
    v
GlobalHotkeyService._on_remaining_deck()
    |
    ├──> Reads current GameState from GameEngine
    ├──> Formats speech text
    ├──> Calls SpeechService.speak()
    |
    v
Screen reader announces "12 cards remaining in deck"
    (NVDA/JAWS speak even though Hearthstone has focus)
```

### Replay Viewing Flow

```
User selects .hsreplay file (or game from history)
    |
    v
ReplayEngine.load(path)
    |
    | [XML parse via python-hsreplay]
    | [EntityTreeExporter builds game entity tree]
    | [Walk tree, emit GameState per turn boundary]
    v
ReplayState (frozen dataclass: tuple of GameState snapshots)
    |
    v
ReplayViewerPresenter._load_replay(replay_state)
    |
    ├──> Zones: turns, board, hand, action_log
    ├──> Navigate turns with left/right
    ├──> Drill into turn with down arrow (action-by-action)
    ├──> Zone switch keys (1-4) for board/hand/log within a turn
    |
    v
ReplayViewerView._on_state_changed(turn_data)
    |
    └──> Updates ListCtrl per zone
```

### Deck Management Flow

```
User pastes deckstring in DeckManager tab
    |
    v
DeckManagerPresenter.import_deck(deckstring)
    |
    ├──> Deck.from_deckstring(deckstring, card_db)
    ├──> Persists to SQLite via db.save_deck()
    ├──> Announces "Imported: Aggro Paladin, 30 cards"
    ├──> Calls _notify_view()
    |
    v
DeckManagerView._on_state_changed(deck_list, cursor)
    |
    └──> Updates deck ListCtrl, card ListCtrl
```

### Key Data Flows

1. **Log to Speech:** Power.log -> LogWatcher thread -> GameEngine -> wx.CallAfter -> Presenter -> SpeechService -> Screen reader. The critical path for live tracking. Latency budget: under 500ms from log write to speech output.
2. **Hotkey to Speech:** Win32 hotkey -> EVT_HOTKEY -> GlobalHotkeyService -> SpeechService. Bypasses presenters entirely. Must work even when StoneReader window is not focused.
3. **Deck to Tracker:** DeckManagerPresenter sets active deck -> GameEngine references it -> Remaining deck calculation uses it as baseline. Cross-presenter communication via shared GameEngine reference.

## Threading Model

### Critical Constraint

wxPython is NOT thread-safe. All GUI operations (widget updates, speech calls, focus changes) MUST happen on the main thread. The only safe way to cross the thread boundary is `wx.CallAfter`.

### Thread Architecture

```
Main Thread (wxPython event loop)
    ├── InputLayer (EVT_CHAR_HOOK dispatch)
    ├── All Presenters (state, zone navigation, speech)
    ├── All Views (wx widgets)
    ├── GlobalHotkeyService (EVT_HOTKEY handler)
    ├── SpeechService (accessible_output2 calls)
    └── wx.CallAfter receives from:
            └── LogWatcher daemon thread

LogWatcher Thread (daemon)
    ├── File I/O (readline from Power.log)
    ├── GameEngine.process_line() (pure computation)
    └── wx.CallAfter(callback, new_state) to cross boundary
```

### Why Not watchdog?

Watchdog (file system watcher library) uses ReadDirectoryChangesW on Windows, which detects file modifications but does not tell you which bytes were appended. For log tailing, you still need to seek and read. A simple polling loop with `readline()` is simpler, more predictable, and sufficient given Hearthstone's log write rate (dozens of lines per second at peak, not thousands). Watchdog adds a dependency and complexity for no benefit here.

### Why Not wx.Timer Instead of a Thread?

wx.Timer runs on the main thread. If the file read or parsing takes more than a few milliseconds, it blocks the GUI. A daemon thread with wx.CallAfter keeps the GUI responsive regardless of I/O timing. Additionally, if Hearthstone is writing a burst of log lines (e.g. a complex spell chain), the thread can batch-process them before posting a single state update, while wx.Timer would need to interleave reads with event processing.

### Thread Safety Rules

1. **LogWatcher thread** may only call `wx.CallAfter`. No direct GUI or SpeechService access.
2. **GameEngine** is instantiated on the main thread but called from LogWatcher thread for `process_line()`. It must not hold references to wx objects. Its internal state (entity tracking dict) is only accessed from the LogWatcher thread -- no concurrent access.
3. **GameState snapshots** are frozen dataclasses. Once constructed and posted via wx.CallAfter, they are immutable and safe to read from the main thread.
4. **LogWatcher.stop()** is called from the main thread (on window close). It sets a `threading.Event` which is thread-safe by design.

## Build Order (Dependency Graph)

The build order is dictated by component dependencies. Build bottom-up:

```
Phase 1: Deck Management
    No new infrastructure needed. Uses existing:
    - Deck model (from_deckstring)
    - SQLite db (extend schema for deck CRUD)
    - ZoneNavigationMixin, BasePresenter
    - InputLayer, SpeechService
    Produces: DeckManagerPresenter + DeckManagerView + db extensions
    WHY FIRST: Simplest feature. No threading. Validates the
    tab-registration pattern. Produces the "active deck" that
    LiveTracker needs.

Phase 2: Log Parser + Game Engine (no UI)
    New infrastructure:
    - LogWatcher (threading.Thread, file polling)
    - GameEngine (log line processing, entity tracking, state snapshots)
    Dependencies: hslog package (new), hearthstone.entities
    Produces: Given raw Power.log lines, emits GameState snapshots
    WHY SECOND: Core plumbing that LiveTracker and Replay both need.
    Can be built and tested headlessly (no wx dependency in tests).

Phase 3: Live Game Tracker
    Dependencies: GameEngine (Phase 2), DeckManager's active deck (Phase 1)
    New: LiveTrackerPresenter, LiveTrackerView, GlobalHotkeyService
    Produces: Live tracking tab + background hotkey announcements
    WHY THIRD: The core value proposition. Requires both Phase 1
    (active deck) and Phase 2 (game engine).

Phase 4: Replay Viewer
    Dependencies: GameEngine's state snapshot logic (Phase 2)
    New: ReplayEngine, ReplayViewerPresenter, ReplayViewerView
    Can reuse: python-hsreplay for XML parsing, EntityTreeExporter
    WHY LAST: Least critical feature. Reuses Phase 2 infrastructure.
    Can be built independently after Phase 2.
```

## Anti-Patterns

### Anti-Pattern 1: Parsing Log Lines on the Main Thread

**What people do:** Use wx.Timer to periodically read and parse Power.log on the main thread.
**Why it is wrong:** During complex turns (e.g. Shudderwock), Hearthstone can write hundreds of log lines in under a second. Parsing them synchronously blocks the event loop, freezing the UI and causing speech output to stutter or queue up.
**Do this instead:** Daemon thread reads and parses lines. Posts only completed GameState snapshots via wx.CallAfter. The main thread receives pre-computed state and just updates the UI.

### Anti-Pattern 2: Mutable Shared State Between Thread and Main Loop

**What people do:** GameEngine holds a mutable `current_state` dict that the LogWatcher thread writes to and the presenter reads from.
**Why it is wrong:** Race conditions. The presenter might read a half-updated state (e.g. board is updated but hand is not yet). Symptoms: ghost cards, wrong counts, intermittent crashes.
**Do this instead:** GameEngine produces frozen dataclass snapshots. The snapshot is constructed entirely in the worker thread, then posted via wx.CallAfter. The main thread sees only complete, consistent states.

### Anti-Pattern 3: Extending InputLayer for Global Hotkeys

**What people do:** Try to add global hotkeys to InputLayer's key_map, expecting them to work when the app is not focused.
**Why it is wrong:** InputLayer uses EVT_CHAR_HOOK, which only fires when StoneReader's window has focus. Global hotkeys require RegisterHotKey (Win32 API), which delivers WM_HOTKEY messages even when the window is in the background.
**Do this instead:** Create a separate GlobalHotkeyService that uses wx.Frame.RegisterHotKey. Keep InputLayer for in-app keyboard routing. The two systems are orthogonal and should not be merged.

### Anti-Pattern 4: Presenter Directly Reads Power.log

**What people do:** LiveTrackerPresenter opens and reads Power.log itself, mixing I/O with presentation logic.
**Why it is wrong:** Violates MVP separation. Makes the presenter untestable (needs a real log file). Mixes threading concerns with UI state management.
**Do this instead:** LogWatcher and GameEngine are services injected into the presenter. In tests, mock the GameEngine and feed it known states.

### Anti-Pattern 5: Building Custom Log Parser Instead of Using hslog

**What people do:** Write regex-based line parsing from scratch for Power.log.
**Why it is wrong:** Power.log format is complex (nested blocks, multi-line entities, obfuscated opponent cards). HearthSim's hslog library has handled edge cases across years of Hearthstone patches. Rolling your own parser means re-discovering every edge case.
**Do this instead:** Use `hslog` for the heavy lifting. If hslog does not expose a line-by-line API suitable for streaming, wrap it: accumulate lines in a buffer, periodically call `parser.read(StringIO(buffer))` and `parser.flush()`, then export the entity tree.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Power.log** (Hearthstone) | File tail via seek+readline polling | Requires log.config in `%LOCALAPPDATA%/Blizzard/Hearthstone/`. StoneReader should auto-create this file if missing. Log resets on each game launch. |
| **hslog** (PyPI package) | `from hslog import LogParser` | Separate package from `hearthstone`. Must add `hslog` to dependencies. Parser's `read()` accepts file-like objects; wrap accumulated lines in StringIO for incremental feeding. |
| **python-hsreplay** (PyPI) | `from hsreplay import HSReplayDocument` | For loading .hsreplay XML files for replay viewing. Provides `from_log_file()` and document parsing. Add to dependencies. |
| **win32con** (pywin32) | `import win32con` for VK_* and MOD_* constants | Required for RegisterHotKey. pywin32 is a common Windows Python package. Add to dependencies. |
| **accessible_output2** | Already integrated via SpeechService | No changes needed. Global hotkeys call SpeechService.speak() like everything else. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| LogWatcher -> Main Thread | `wx.CallAfter(callback, frozen_state)` | Only crossing point. GameState is immutable. |
| GameEngine <-> ActiveDeck | GameEngine holds reference to active Deck | Set by DeckManagerPresenter when user selects deck. Used to compute remaining cards. |
| Presenter <-> View | Callback functions set via `set_on_*_changed()` | Existing pattern from CardBrowserPresenter. Views call presenter methods; presenters call view callbacks. |
| GlobalHotkey -> SpeechService | Direct call in EVT_HOTKEY handler | Bypasses presenters. Reads from GameEngine's last posted state (main-thread-safe since EVT_HOTKEY runs on main thread). |
| MainWindow -> Tab Registration | `add_tab(panel, name, presenter, focus_target)` | Existing pattern. Each new feature calls this once during startup. |

## Scaling Considerations

This is a single-user desktop app, so traditional web scaling does not apply. The relevant scaling axis is **event throughput** from Power.log.

| Scenario | Events/sec | Architecture Impact |
|----------|------------|---------------------|
| Normal gameplay | 5-20 lines/sec | No concern. Poll loop handles easily. |
| Complex turn (Shudderwock, OTK combos) | 100-500 lines/sec | Batch processing in worker thread. Post one snapshot per meaningful state change, not per line. |
| Rapid log rotation (game restart) | N/A (file reset) | LogWatcher must detect log file truncation/replacement and re-open. |
| Multiple games in a session | N/A | GameEngine resets state on CREATE_GAME packet. LogWatcher continues tailing. |

### First Bottleneck

Speech queue saturation. If the tracker announces every card draw and play as they happen during a complex turn, the screen reader queues up dozens of messages. **Mitigation:** Only auto-announce turn changes and significant events (your draw, opponent play). Detailed state is available on-demand via zone navigation or global hotkeys.

### Second Bottleneck

GameState construction during burst parsing. Creating frozen dataclasses with tuples of entities is cheap but not free. **Mitigation:** Only construct and post a new GameState when a "meaningful" change occurs (zone transitions, tag changes to tracked tags). Ignore MetaData packets and animation-only events.

## Sources

- [HearthSim/python-hslog](https://github.com/HearthSim/python-hslog) -- Power.log parser library (HIGH confidence)
- [HearthSim/python-hsreplay](https://github.com/HearthSim/python-hsreplay) -- HSReplay XML parser (HIGH confidence)
- [HearthSim Game State Protocol](https://hearthsim.info/docs/gamestate-protocol/) -- Official protocol documentation (HIGH confidence)
- [wxPython RegisterHotKey Wiki](https://wiki.wxpython.org/RegisterHotKey) -- Global hotkey pattern for wxPython (HIGH confidence)
- [wxPython LongRunningTasks Wiki](https://wiki.wxpython.org/LongRunningTasks) -- Threading patterns for wxPython (HIGH confidence)
- [wxPython wx.Timer docs](https://docs.wxpython.org/wx.Timer.html) -- Timer API reference (HIGH confidence)
- [HDT log.config setup](https://github.com/HearthSim/Hearthstone-Deck-Tracker/wiki/Setting-up-the-log.config) -- Hearthstone logging configuration (HIGH confidence)
- [watchdog PyPI](https://pypi.org/project/watchdog/) -- File system watcher library, evaluated and rejected for this use case (MEDIUM confidence)
- [Tim Golden - System-wide hotkeys](https://www.timgolden.me.uk/python/win32_how_do_i/catch_system_wide_hotkeys.html) -- Win32 hotkey patterns (MEDIUM confidence)

---
*Architecture research for: StoneReader accessible Hearthstone deck tracker*
*Researched: 2026-04-14*
