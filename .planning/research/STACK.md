# Technology Stack: Live Game Tracking, Global Hotkeys, and Replay Parsing

**Project:** StoneReader (accessible Hearthstone deck tracker)
**Researched:** 2026-04-14
**Scope:** New libraries needed for Milestone 2 features only. Existing stack (wxPython, accessible_output2, hearthstone, SQLite) is not re-evaluated.

## Recommended Stack

### Power.log Parsing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| hslog | 1.18.0 | Deserialize Power.log into packet trees | HearthSim's official parser. Regex-based line-by-line parsing with PacketTree abstraction. EntityTreeExporter builds full game state from packets. Already installed as transitive dependency. Production-stable, MIT licensed. | HIGH |
| aniso8601 | 10.0.1 | ISO 8601 timestamp parsing (hslog dependency) | Required by hslog for parsing log timestamps. Already installed. | HIGH |

**How it works:** hslog reads Power.log line-by-line, building a PacketTree of game events (CREATE_GAME, FULL_ENTITY, TAG_CHANGE, SHOW_ENTITY, BLOCK_START/END). Calling `packet_tree.export()` produces a `hearthstone.entities.Game` object with full entity state -- every card's zone, tags, and history. The app already depends on the `hearthstone` library which provides the entity/enum layer that hslog exports into.

**Key classes:**
- `hslog.LogParser` -- feeds log lines, produces PacketTree
- `hslog.export.EntityTreeExporter` -- simulates packets into entity tree (default)
- `hslog.export.FriendlyPlayerExporter` -- identifies the local player
- `hearthstone.entities.Game` -- exported game state with entity list
- `hearthstone.enums.Zone` -- DECK, HAND, PLAY, GRAVEYARD, SECRET, etc.

### Replay File Parsing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| hsreplay | 1.16.2 | Read/write HSReplay XML files | HearthSim's official HSReplay format library. Provides `HSReplayDocument.from_xml_file()` for reading and `to_packet_tree()` for lossless conversion to PacketTree (same format hslog produces). Already installed as transitive dependency. | HIGH |
| lxml | 6.0.2 | Fast XML parsing (hsreplay dependency) | Used by hsreplay for XML parsing. Falls back to stdlib xml.etree if absent, but lxml is already installed and significantly faster for large replay files. | HIGH |

**How it works:** HSReplay files are XML documents mirroring the game protocol. `hsreplay.document.HSReplayDocument.from_xml_file(fp)` parses the XML, then `.to_packet_tree()` converts to a PacketTree identical to what hslog produces from live logs. This means the replay viewer and live game tracker share the same entity model -- build the game state renderer once, use it for both.

### Real-Time File Watching

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| watchdog | 6.0.0 | Monitor Power.log for new data | Uses Windows ReadDirectoryChangesW API for event-driven file monitoring. Fires `on_modified` callback when Power.log is written to. More responsive than polling (sub-second latency). Mature, well-maintained (Apache 2.0). | MEDIUM |

**Architecture decision: watchdog + seek-and-read tail**

The file watcher does NOT parse the log itself. The architecture is:
1. **watchdog** detects that Power.log was modified (via OS event)
2. **Tail reader** seeks to last-read position, reads new bytes, splits into lines
3. **hslog.LogParser** processes new lines incrementally
4. **EntityTreeExporter** updates game state
5. **Presenter** receives state change, announces via speech

**Why watchdog over alternatives:**
- **vs. simple polling loop:** Polling with `time.sleep()` + `readline()` works but adds 0.5-1s latency per poll interval. During fast game actions (discover, combat), this delay compounds. Watchdog fires within milliseconds of a write.
- **vs. stdlib only:** Python has no built-in file system event API. `os.stat()` polling is what watchdog's PollingObserver does internally, but less elegantly.
- **vs. pyinotify/inotify:** Linux-only. StoneReader targets Windows.

**Caveat (why MEDIUM confidence):** Watchdog can fire duplicate `on_modified` events on Windows because ReadDirectoryChangesW sometimes reports multiple events per write. The tail reader must be idempotent -- track file position with `file.tell()` and only process genuinely new bytes. This is a known pattern, not a blocker.

**Fallback:** If watchdog proves unreliable for the single-file use case, a simple `threading.Timer`-based poll at 200ms intervals with `file.seek(last_pos)` + `file.read()` is a reliable fallback that adds only ~200ms latency. The architecture's separation of "detect change" from "read new data" makes swapping trivial.

### Global Hotkeys (Windows)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| wxPython RegisterHotKey | (built into wx 4.2.5) | System-wide keyboard shortcuts | wxPython wraps Windows RegisterHotKey API directly on wx.Window. Integrates natively with the existing event loop via EVT_HOTKEY. No additional dependency. Uses WM_HOTKEY message passing (not low-level keyboard hooks), so it does NOT intercept or suppress keystrokes before screen readers see them. | HIGH |
| pywin32 (win32con) | 311 | VK_* and MOD_* constants | Provides `win32con.VK_F1`, `win32con.MOD_ALT`, etc. for RegisterHotKey calls. Already a dependency (required by accessible_output2 on Windows). | HIGH |

**How it works:**
```python
# In MainWindow.__init__ (existing wx.Frame)
self.hotkey_id_remaining_deck = 100
self.RegisterHotKey(
    self.hotkey_id_remaining_deck,
    win32con.MOD_ALT,
    win32con.VK_F1
)
self.Bind(wx.EVT_HOTKEY, self.on_remaining_deck, id=self.hotkey_id_remaining_deck)
```

**Why wxPython RegisterHotKey over alternatives:**

- **vs. `keyboard` library (v0.13.5):** Last updated March 2020 -- effectively abandoned. Uses low-level keyboard hooks (SetWindowsHookEx) which intercept ALL keystrokes before other applications see them. This WILL conflict with NVDA/JAWS keyboard handlers. Requires root on Linux. Classified as Beta. Do NOT use.

- **vs. `pynput` (v1.7.6):** Also uses low-level hooks on Windows. Listener callbacks run from the OS input thread, so blocking operations freeze input for ALL processes including the screen reader. Last released July 2023. Not designed for accessibility scenarios.

- **vs. `global-hotkeys` PyPI package:** Thin wrapper around ctypes RegisterHotKey. Would work, but adds a dependency for something wxPython already provides natively. No benefit.

- **vs. raw ctypes RegisterHotKey:** Works, but requires running a separate message pump thread (`GetMessageA` loop). wxPython's event loop already IS a message pump that handles WM_HOTKEY. Using ctypes means duplicating what wx already does and coordinating between two message loops.

**Screen reader safety:** RegisterHotKey works at the Windows message queue level, not the keyboard hook level. When the user presses a registered hotkey, Windows posts WM_HOTKEY to the registered window. The keystroke is consumed by Windows before it reaches any application -- this is the same mechanism Windows uses for its own hotkeys (Win+L, etc.). NVDA and JAWS use SetWindowsHookEx for keyboard input, which operates at a different layer. RegisterHotKey and screen reader hooks coexist without conflict, provided the chosen key combinations don't overlap with NVDA/JAWS modifier keys (Insert, Caps Lock + various).

**Recommended hotkey scheme (avoid screen reader conflicts):**
- Use Alt+F1 through Alt+F12 -- these don't conflict with NVDA (Insert+key) or JAWS (Insert+key)
- Use Ctrl+Shift+letter as secondary option
- NEVER use Insert+anything (NVDA modifier) or Caps Lock+anything (optional NVDA modifier)
- NEVER use unmodified keys (will be captured even during text input)

### Threading Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| threading (stdlib) | Python 3.12 | Background thread for log watcher | watchdog.Observer runs its own thread. The tail reader + hslog parser should also run on a background thread to avoid blocking the wxPython GUI event loop. | HIGH |
| wx.CallAfter | (built into wx 4.2.5) | Thread-safe GUI updates | Posts callable to wx main thread event queue. The background log parser thread calls `wx.CallAfter(presenter.update_game_state, new_state)` to safely update the UI. This is the canonical wxPython pattern for background-to-GUI communication. | HIGH |

**Architecture:**
```
[Background Thread]                    [Main Thread (wx event loop)]
watchdog detects modification    -->   (not involved)
tail reader reads new lines      -->   (not involved)
hslog parses new packets         -->   (not involved)
exporter builds game state       -->   wx.CallAfter(presenter.update, state)
                                       presenter receives state
                                       presenter calls self._speech
                                       view updates if visible
```

## Full Dependency Summary

### New Dependencies to Add

| Package | Version | Why Needed | Size Impact |
|---------|---------|------------|-------------|
| watchdog | >=6.0.0 | File system monitoring for Power.log | ~500 KB |

### Already Installed (No Changes Needed)

| Package | Version | Why Relevant |
|---------|---------|-------------|
| hslog | 1.18.0 | Power.log parser (transitive via hearthstone) |
| hsreplay | 1.16.2 | HSReplay XML parser (transitive via hearthstone) |
| aniso8601 | 10.0.1 | Timestamp parsing (transitive via hslog) |
| lxml | 6.0.2 | Fast XML parsing (transitive via hsreplay) |
| hearthstone | 9.17.0 | Card enums, entity model, deckstrings |
| pywin32 | 311 | Windows API constants for RegisterHotKey (installed on Windows, dependency of accessible_output2) |

### Explicitly NOT Adding

| Package | Why Not |
|---------|---------|
| keyboard 0.13.5 | Abandoned (last release 2020). Low-level hooks conflict with screen readers. Beta quality. |
| pynput 1.7.6 | Low-level hooks risk freezing screen reader input. Not designed for accessibility. |
| global-hotkeys | Unnecessary -- wxPython RegisterHotKey covers the same functionality with zero new deps. |
| pygtail | Overengineered for our use case (log rotation handling). Power.log doesn't rotate mid-game. |

## Installation

```bash
# Only one new dependency
uv add watchdog>=6.0.0
```

The existing `pyproject.toml` dependencies already pull in hslog, hsreplay, aniso8601, and lxml transitively through the `hearthstone` package. No changes needed for those.

Note: `pywin32` is platform-conditional -- it's installed on Windows where `accessible_output2` requires it. The development environment (WSL/Linux) won't have it, so RegisterHotKey code must be gated behind `sys.platform == "win32"` checks.

## Configuration Requirements

### Hearthstone log.config

Hearthstone needs a `log.config` file to enable Power.log output:

**Location:** `%LocalAppData%\Blizzard\Hearthstone\log.config`
(typically `C:\Users\<USER>\AppData\Local\Blizzard\Hearthstone\log.config`)

**Required content:**
```ini
[Power]
LogLevel=1
FilePrinting=True
ConsolePrinting=False
ScreenPrinting=False
Verbose=True
```

**Power.log location:** `<Hearthstone Install>\Logs\Power.log`
(typically `C:\Program Files (x86)\Hearthstone\Logs\Power.log`)

StoneReader should auto-detect these paths and prompt the user if log.config is missing or misconfigured. This is the same setup that HDT and Firestone require.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Log parsing | hslog 1.18.0 | Custom regex parser | hslog is battle-tested by HearthSim/HSReplay. Handles edge cases (nested blocks, PowerTaskList filtering, partial lines). Writing our own would be months of bug-fixing. |
| Replay parsing | hsreplay 1.16.2 | Direct XML parsing with lxml | hsreplay handles the HSReplay XML schema, version differences, and lossless PacketTree conversion. Rolling our own misses edge cases. |
| File watching | watchdog 6.0.0 | threading.Timer + file.seek poll | Watchdog is more responsive. But polling is an acceptable fallback -- architecture supports swapping. |
| File watching | watchdog 6.0.0 | asyncio file watching | wxPython has its own event loop. Mixing asyncio adds complexity with no benefit. Threads + wx.CallAfter is the established wxPython pattern. |
| Global hotkeys | wx.RegisterHotKey | keyboard/pynput/ctypes | wx.RegisterHotKey integrates with existing event loop, uses safe WM_HOTKEY (not hooks), zero new deps, proven NVDA-safe. |
| Global hotkeys | wx.RegisterHotKey | NVDA addon approach | An NVDA addon (like HearthstoneCardLookup) would only work with NVDA, not JAWS or other screen readers. RegisterHotKey works regardless of screen reader. |

## Sources

### HIGH Confidence (official docs, installed packages, Context7)
- hslog installed version verified: `uv run pip show hslog` -- 1.18.0
- hsreplay installed version verified: `uv run pip show hsreplay` -- 1.16.2
- wxPython RegisterHotKey docs: https://docs.wxpython.org/wx.Window.html
- wxPython RegisterHotKey wiki: https://wiki.wxpython.org/RegisterHotKey
- Windows RegisterHotKey API: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey
- HearthSim game state protocol: https://hearthsim.info/docs/gamestate-protocol/
- watchdog Context7 docs: /gorakhargosh/watchdog (v6.0.0)
- watchdog PyPI: https://pypi.org/project/watchdog/

### MEDIUM Confidence (verified with multiple sources)
- Hearthstone log.config setup: https://github.com/HearthSim/Hearthstone-Deck-Tracker/wiki/Setting-up-the-log.config
- Power.log file location: https://hearthsim.info/blog/fast-hearthstone-log-parsing/
- HSReplay format specification: https://hearthsim.info/hsreplay/
- Screen reader accessibility request for HDT: https://github.com/HearthSim/Hearthstone-Deck-Tracker/issues/4371
- Tim Golden ctypes hotkey reference: https://www.timgolden.me.uk/python/win32_how_do_i/catch_system_wide_hotkeys.html

### LOW Confidence (single source or training data)
- Specific NVDA/JAWS interaction with RegisterHotKey vs SetWindowsHookEx -- based on understanding of Windows input architecture, not direct testing. Should be validated on a Windows machine with NVDA running.
- watchdog duplicate event behavior on Windows -- reported in GitHub issues but not systematically tested with Hearthstone's specific write pattern.
