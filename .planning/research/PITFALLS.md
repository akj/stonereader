# Pitfalls Research

**Domain:** Accessible Hearthstone deck tracker / real-time game state viewer (wxPython desktop app)
**Researched:** 2026-04-14
**Confidence:** HIGH (multiple sources cross-verified: HearthSim docs, HDT issue tracker, wxPython wiki, NVDA project, accessible_output2 source)

## Critical Pitfalls

### Pitfall 1: PowerTaskList Duplication Corrupts Game State

**What goes wrong:**
Blizzard logs every game event twice in Power.log: once in `GameState DebugPrintPower` (logged when the client receives the data) and again in `PowerTaskList DebugPrintPower` (logged when the animation queue executes the action on screen). Naive parsers that process both streams double-count every entity creation, tag change, and zone transition. The result is phantom entities, doubled card counts in hand/board, and incorrect remaining-deck numbers.

**Why it happens:**
Developers read Power.log line by line and see the same events appearing twice without understanding the two subsystems. The line prefixes are similar enough (`GameState DebugPrintPower` vs `PowerTaskList DebugPrintPower`) that a loose regex matches both. The PowerTaskList stream is delayed by animation timing, so duplicates appear slightly later, making them harder to detect in small test files.

**How to avoid:**
Filter lines strictly by prefix. Only parse lines starting with `GameState DebugPrintPower` for state tracking. Ignore `PowerTaskList` entirely -- it represents the visual animation queue, not authoritative game state. Use python-hslog if possible, which already handles this separation. If writing a custom parser, add an explicit test with a real Power.log file that contains both streams and assert entity counts match expected values.

**Warning signs:**
- Card counts in deck/hand are 2x expected values
- Entity IDs appear twice in state tracking
- Board state shows entities that should not exist
- Tests pass with hand-crafted log snippets but fail with real Power.log files

**Phase to address:**
Phase 1 (Power.log parsing foundation) -- this must be correct from day one or every downstream feature (deck tracking, opponent tracking, replay) inherits the bug.

---

### Pitfall 2: Power.log File Reset on Hearthstone Restart Loses Game Context

**What goes wrong:**
Hearthstone erases Power.log every time the client restarts. If StoneReader starts watching mid-session, the log already contains data from previous games. If Hearthstone restarts during a StoneReader session, the log file is truncated/recreated and the file handle may become stale. The watcher misses the reset, continues reading from the old file position, and either reads garbage or blocks forever.

**Why it happens:**
Developers test with a single game session and never encounter the file reset. They use `seek(0, SEEK_END)` once at startup and poll for new data, but never check if the file was truncated (file size smaller than last known position) or replaced entirely (inode changed on Unix, but on Windows the file is typically truncated in-place or deleted and recreated).

**How to avoid:**
On every poll cycle: (1) check if the file still exists, (2) compare current file size against the last-read position -- if size < position, the file was truncated, so reset to position 0 and reinitialize parser state. (3) On Windows, also handle the case where the file is deleted and recreated by catching FileNotFoundError and retrying after a brief delay. Detect `CREATE_GAME` packets as game boundaries to reset per-game state without losing session-level data (game history). Store the previous game result before resetting parser state.

**Warning signs:**
- StoneReader stops updating after the user restarts Hearthstone
- Parser throws seek/read errors after a long session
- Game state from a previous game bleeds into the current game
- Tests only run against static log files, never against simulated file truncation

**Phase to address:**
Phase 1 (log watcher implementation) -- the file watcher must handle reset from the start. Retrofitting is painful because every consumer of game state events assumes continuity.

---

### Pitfall 3: wx.CallAfter Race with Window Destruction Causes Segfault

**What goes wrong:**
The Power.log watcher thread uses `wx.CallAfter()` to dispatch game state updates to the main thread. If the user closes StoneReader while a game is in progress, the background thread may call `wx.CallAfter()` after the window has been destroyed. This causes a segmentation fault -- wxWidgets processes the queued callable, tries to touch a destroyed C++ object, and the process crashes silently. On Windows with a screen reader running, this can also freeze NVDA briefly.

**Why it happens:**
wxPython is not thread-safe. `wx.CallAfter` is the approved mechanism for cross-thread communication, but it only queues a callable on the main event loop -- there is no built-in check that the target window still exists. Developers test the happy path (app running, game active) but not the shutdown path (user closes window while background work is in progress).

**How to avoid:**
Use a `threading.Event` stop signal. In `MainWindow.OnClose`, set the stop event, then `join()` the watcher thread before calling `Destroy()`. The watcher thread must check the stop event on every iteration and exit cleanly. The CallAfter callback should guard against destroyed widgets with `if not self.IsBeingDeleted()` or an equivalent check. Never assume the window exists when a CallAfter fires. Pattern:

```python
# In watcher thread
if self._stop_event.is_set():
    return
wx.CallAfter(self._on_game_update, state)

# In OnClose
self._stop_event.set()
self._watcher_thread.join(timeout=2.0)
self.Destroy()
```

**Warning signs:**
- Intermittent segfaults when closing StoneReader during a game
- NVDA freezes briefly when StoneReader closes
- Crash reports with no Python traceback (C-level crash)
- Works fine in testing because tests do not close windows during background operations

**Phase to address:**
Phase 1 (threading architecture) -- this pattern must be established when the watcher thread is first created. Every feature that adds background work must follow the same pattern.

---

### Pitfall 4: Global Hotkeys Conflict with Screen Reader Key Bindings

**What goes wrong:**
StoneReader registers global hotkeys via `RegisterHotKey` (Win32 API) so users can query game state while Hearthstone has focus. But NVDA uses Insert+key combinations extensively, JAWS uses Insert+key and Caps Lock+key, and HearthstoneAccess itself uses F-keys and letter keys for in-game navigation. If StoneReader registers a hotkey that collides with a screen reader binding, one of two things happens: (1) the screen reader command stops working, breaking the user's primary accessibility tool, or (2) the hotkey registration silently fails because the screen reader already holds it, and StoneReader's hotkey never fires.

**Why it happens:**
Developers test without a screen reader or with only one screen reader. NVDA and JAWS use different modifier keys, so a hotkey safe for NVDA may collide with JAWS. HearthstoneAccess uses a separate set of bindings that the developer may not know about. The `RegisterHotKey` API returns FALSE on failure, but many implementations do not check the return value.

**How to avoid:**
(1) Use modifier combinations that screen readers do not claim: `Ctrl+Alt+key` or `Ctrl+Shift+key` are safest because screen readers primarily use Insert+key and Caps Lock+key. (2) Never use Insert, Caps Lock, or unmodified F-keys as global hotkeys. (3) Consult the HearthstoneAccess keyboard commands (https://www.hearthstoneaccess.com/commands.html) to avoid collision with their bindings -- they use F1, F8, letter keys, Shift+letter, Ctrl+letter during gameplay. (4) Always check the return value of `RegisterHotKey` and announce failure to the user via speech. (5) Make all global hotkeys user-configurable so users can remap around their specific screen reader setup. (6) Document which hotkeys HearthstoneAccess uses so users know what is safe.

**Warning signs:**
- Users report "hotkey does nothing" with JAWS but works with NVDA (or vice versa)
- Screen reader commands stop working when StoneReader is running
- HearthstoneAccess controls break after StoneReader registers hotkeys
- `RegisterHotKey` returns FALSE but the app does not report it

**Phase to address:**
Phase 2 (global hotkeys) -- but the hotkey scheme must be designed in Phase 1 so the architecture supports configurable bindings from the start.

---

### Pitfall 5: Speech Flooding During Rapid Game Events Makes App Unusable

**What goes wrong:**
During combat or animation-heavy turns (e.g., multiple deathrattles triggering), Power.log emits dozens of state changes per second. If each state change triggers a `speak()` call with `interrupt=True`, the user hears nothing useful -- each announcement cuts off the previous one before it finishes, resulting in rapid-fire partial words. If `interrupt=False` is used, announcements queue up and the speech output falls minutes behind the actual game state. Either way, the user cannot get timely, coherent information.

**Why it happens:**
Developers equate "accessible" with "announce everything." They process each Power.log event independently without considering speech as a constrained channel with limited bandwidth. NVDA's speech queue has no built-in debouncing -- it faithfully speaks (or interrupts) whatever it receives.

**How to avoid:**
(1) Distinguish between passive monitoring and active queries. Passive monitoring (background state tracking) should NOT produce speech output. Only user-initiated queries (pressing a global hotkey to ask "what's in my hand?") should produce speech. (2) For live event announcements (e.g., "Opponent played Fireball"), batch events per turn/action block rather than per log line. Consolidate: "Opponent played Fireball targeting your Loot Hoarder. Loot Hoarder died. You drew a card." rather than four separate interruptions. (3) Use a speech priority system: critical events (lethal, your turn) interrupt; informational events (opponent played a card) queue; minor events (animation triggers) are suppressed. (4) Add a configurable verbosity level so users can choose how much they hear during live play.

**Warning signs:**
- Users describe the app as "unusable during the opponent's turn"
- Speech output lags behind game state by several seconds
- Individual words are cut off mid-syllable during combat
- Testing with slow/simple games works fine but complex board states cause chaos

**Phase to address:**
Phase 2 (live game announcements) -- but the speech batching architecture should be designed in Phase 1 so the presenter layer supports it.

---

### Pitfall 6: Timestamp Parsing Performance Destroys Real-Time Responsiveness

**What goes wrong:**
Power.log lines include timestamps but no dates. The HearthSim team discovered that timestamp parsing was the single biggest performance bottleneck in their parser, consuming more CPU time than all other parsing logic combined. Using `dateutil.parser.parse` or similar general-purpose datetime parsers on every line made real-time tracking impossible -- the parser fell behind the rate of log output.

**Why it happens:**
Developers reach for standard library datetime parsing (`datetime.strptime` or `dateutil.parser.parse`) because it is the obvious approach. These parsers are flexible but slow because they handle many formats. Power.log timestamps have a fixed format, but developers do not optimize for it.

**How to avoid:**
(1) Parse timestamps only when needed (game boundaries, turn markers), not on every line. (2) Use manual string slicing for the fixed timestamp format instead of `strptime` -- Power.log timestamps follow `HH:MM:SS.fffffff` format. (3) Benchmark parsing throughput against a real Power.log file (not synthetic test data) to verify the parser can keep up with game event rate. HearthSim found that selective timestamp parsing reduced overall parsing time by over 70%. (4) If using python-hslog, verify its parsing strategy; it was designed with this optimization in mind.

**Warning signs:**
- Parser falls behind during fast game events (combat, discover chains)
- CPU usage spikes during opponent's turn
- Profiling shows datetime/timestamp functions dominating call stack
- Works fine in unit tests but lags during live play

**Phase to address:**
Phase 1 (parser implementation) -- performance characteristics are set at this layer and hard to fix later.

---

### Pitfall 7: log.config Not Managed Causes "Tracker Does Nothing" Experience

**What goes wrong:**
Hearthstone only writes Power.log if the correct `log.config` file exists at `%LocalAppData%/Blizzard/Hearthstone/`. Without it, Power.log either does not exist or contains no useful data. Hearthstone patches can reset or overwrite log.config. Other deck trackers (HDT, Firestone) also manage this file and may overwrite StoneReader's configuration. The result: StoneReader silently tracks nothing because there is no log data to parse. This is the single most common support issue for HDT (per their issue tracker).

**Why it happens:**
Developers always have log.config set up on their development machine and forget it is not a default Hearthstone configuration. They test against existing log files and never encounter the "no log file" scenario. Users install StoneReader, launch it, play a game, and nothing happens.

**How to avoid:**
(1) On startup, check if log.config exists with the required sections. If missing or incomplete, create/update it automatically (this is what HDT does). (2) Announce via speech on startup: "Log configuration verified" or "Warning: Hearthstone log configuration needs to be set up. StoneReader will configure it automatically." (3) Include the Power section at minimum. Format is INI-style:
```
[Power]
LogLevel=1
FilePrinting=True
ConsolePrinting=False
ScreenPrinting=False
Verbose=True
```
(4) After writing log.config, inform the user they need to restart Hearthstone for changes to take effect. (5) Check log.config periodically or on each app startup, because Hearthstone patches may reset it. (6) Do not overwrite sections that belong to other trackers -- merge/append instead.

**Warning signs:**
- Users report "StoneReader does nothing during games"
- Power.log file does not exist or is empty
- Works on developer machine but fails for new users
- First-run experience is silent failure

**Phase to address:**
Phase 1 (first-run setup / Power.log watcher) -- must be solved before any user testing.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Parsing Power.log with raw regex instead of python-hslog | No external dependency, full control | Must handle every format change, PowerTaskList duplication, block nesting manually. HDT's regex parser was rewritten multiple times | Only if python-hslog does not support streaming/incremental parsing needed for live tracking |
| Calling `speak()` directly from the watcher thread | Simpler code, no CallAfter needed | accessible_output2 thread safety is undocumented. May crash or produce garbled output with NVDA/JAWS COM objects | Never -- always dispatch speech to main thread via wx.CallAfter |
| Storing full game state history in memory for replay | Simple implementation, no serialization | Memory grows linearly with game length. Long Battlegrounds sessions can produce 1000+ state snapshots with 100+ entities each | Acceptable for standard/wild modes (30 turns). Need streaming/disk-backed storage for Battlegrounds |
| Polling Power.log with time.sleep() instead of watchdog | Zero dependencies, simple loop | Wastes CPU when no game is active. Misses rapid bursts if poll interval is too long. Cannot detect file deletion/recreation | Acceptable for MVP if poll interval is tuned (200-500ms). Switch to watchdog for production |
| Hardcoding global hotkey bindings | Ships faster | Users with non-standard screen reader configs cannot use the app. HearthstoneAccess key conflicts | Never -- must be configurable from the start for accessibility |
| Broad `except Exception` in speech/parser code | App does not crash | Silently masks bugs. User thinks feature works when it is broken. Already a known issue in current SpeechService | Never in new code. Fix existing instances as encountered |

## Integration Gotchas

Common mistakes when connecting to external services and libraries.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Power.log file access | Opening with exclusive lock, which conflicts with Hearthstone's write lock | Open with `open(path, 'r', encoding='utf-8')` in shared read mode. On Windows, use `FILE_SHARE_READ \| FILE_SHARE_WRITE` flags if using Win32 API directly |
| hearthstone-data package | Assuming card data is always up-to-date after a Hearthstone patch | Pin hearthstone-data version in pyproject.toml. Check for updates on app startup. Gracefully handle unknown card IDs (show "Unknown Card [ID]" instead of crashing) |
| accessible_output2 Auto() | Calling `Auto()` constructor multiple times (e.g., per-speak call) | Instantiate once at app startup. Cache the output object. The constructor probes all screen readers, which is expensive |
| log.config management | Overwriting the entire file, destroying other trackers' sections | Read existing file, parse as INI, merge required sections, write back |
| python-hslog (if used) | Feeding it incomplete lines during live tailing | Buffer lines until a complete log entry is detected (lines with proper timestamp prefix). Flush parser at game boundaries |
| RegisterHotKey Win32 API | Not checking return value; not unregistering on shutdown | Check return value, announce failure. Always call UnregisterHotKey in OnClose. Handle WM_HOTKEY messages in the message loop |
| wxPython EVT_CHAR_HOOK | Registering global hotkeys AND in-app hotkeys on the same keys | Keep in-app hotkeys (EVT_CHAR_HOOK) and global hotkeys (RegisterHotKey/WM_HOTKEY) in separate namespaces. Document which system each key belongs to |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Parsing every Power.log line with regex | CPU spikes during combat-heavy turns | Pre-filter lines by prefix (string startswith) before regex. Only regex-parse lines from `GameState DebugPrintPower` | 50+ events/second during complex turns with deathrattles/chain effects |
| Rebuilding full GameState on every tag change | UI freezes during rapid state changes | Batch tag changes within a single BLOCK into one state update. Only notify presenters at block boundaries | Any board with 7+ minions and buff/debuff chains |
| Announcing every zone transition to screen reader | Speech queue grows unboundedly, output lags minutes behind | Batch announcements per action block. Suppress minor transitions (SETASIDE, REMOVEDFROMGAME). Only announce player-visible events | Any game with discover/generation effects producing 5+ entities per turn |
| Storing all entity history for opponent hand tracking | Memory grows with game length | Track only current hand entities and their draw/creation turn. Prune entities that leave hand | 20+ turn games with heavy card generation |
| Full card database search during game state updates (for card name lookup) | Lag when resolving card IDs to display names | Pre-build a card_id-to-name lookup dict at startup. Use O(1) dict lookup, not O(n) search | First occurrence -- already 8000+ cards in database |

## Security Mistakes

Domain-specific security issues.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Running StoneReader as admin for RegisterHotKey | Escalated privileges for entire app; any code execution vulnerability becomes admin-level | RegisterHotKey does not require admin. Only request admin if writing to protected Hearthstone directory (log.config). Prefer writing to %LocalAppData% path which does not need elevation |
| Storing Hearthstone install path from user input without validation | Path traversal if used to construct file operations | Validate path exists and contains expected Hearthstone files. Use pathlib for safe path construction. Never pass raw user paths to os.system or subprocess |
| Auto-updating hearthstone-data without verification | Supply chain attack via compromised package | Pin versions in pyproject.toml. Use hash verification. Update manually after checking release notes |

## UX Pitfalls

Common user experience mistakes in this domain, specific to screen reader users.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Announcing card details with visual formatting ("2/3 stats, 2 mana") | Numbers without context are meaningless in speech. "Two three two" -- is that attack, health, cost? | Use explicit labels: "2 attack, 3 health, costs 2 mana" -- following HearthstoneAccess convention (name first, then type, then stats) |
| Using generic "item 3 of 7" announcements for zone navigation | User has to press another key to learn what item 3 is | Announce the item content directly: "Fireball, 3 of 7 in hand" -- the count is secondary to the content |
| Requiring multiple keypresses to get essential info | During a live game, every extra keypress is time lost from actual gameplay | Single keypress per info query: one key for "remaining deck summary," one key for "opponent's board," etc. Batch related info into one announcement |
| Silent failure when Power.log is unavailable | User plays an entire game thinking StoneReader is tracking, then discovers no data was captured | Announce tracking status changes: "Game detected, tracking started" / "Warning: no game data received. Check Hearthstone log configuration" |
| Not matching HearthstoneAccess conventions for card reading order | Users who already use HearthstoneAccess have muscle memory for how card info is structured. Different ordering causes cognitive overhead | Follow HearthstoneAccess card reading convention: Name, Type, Rarity, Set, Cost, Attack, Health/Durability, Card Text, Flavor Text. The existing `Card.to_speech_text()` returns name only -- detail lines should match this convention |
| Announcing opponent actions while user is reading their own hand | Speech interruption breaks the user's mental model of their hand | Use speech priority: user-initiated queries interrupt everything; passive opponent announcements queue and wait for silence |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Power.log parser:** Often missing handling for SHOW_ENTITY (reveals hidden card info) -- verify parser handles the transition from unknown to known entity when opponent plays from hand
- [ ] **Remaining deck display:** Often missing copy tracking (cards created by effects like Academic Espionage that add to your deck) -- verify deck count includes dynamically added cards
- [ ] **Opponent hand tracking:** Often missing distinction between drawn and created cards -- verify "card held since turn 3" correctly identifies created cards vs drawn cards
- [ ] **Global hotkeys:** Often missing UnregisterHotKey cleanup on exit -- verify all hotkeys are unregistered in OnClose, or they persist as orphaned system hotkeys until reboot
- [ ] **Game detection:** Often missing end-of-game detection -- verify parser detects game completion (TAG_CHANGE Entity=GameEntity tag=STATE value=COMPLETE) and resets state for next game
- [ ] **log.config setup:** Often missing validation that Hearthstone actually restarted after config change -- verify app detects whether log data is flowing after config setup
- [ ] **Thread shutdown:** Often missing join() on watcher thread -- verify closing StoneReader does not leave orphaned threads or produce segfaults
- [ ] **Speech output fallback:** Often missing verification that stdout fallback actually works when no screen reader is available -- verify print-to-console path is tested
- [ ] **Multi-game sessions:** Often missing parser state reset between games -- verify starting a second game does not carry entity state from first game
- [ ] **Deck selection detection:** Often missing detection of which deck the player selected -- verify deck tracking uses the actual selected deck, not the last-viewed deck

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| PowerTaskList duplication | MEDIUM | Add line-prefix filter to parser. Re-test all game state logic. Existing stored replays may have doubled entities -- add migration to clean them |
| File reset not detected | LOW | Add file-size check to poll loop. Reset parser state. No data loss if game history is stored independently of parser state |
| CallAfter segfault | MEDIUM | Add stop event + join pattern. Audit every CallAfter call site. Add try/except around widget access in all callbacks |
| Hotkey collision with screen reader | LOW | Change hotkey bindings. Add configuration UI/file. Announce new bindings to users |
| Speech flooding | MEDIUM | Refactor presenter layer to batch announcements. Add priority system to SpeechService. Requires touching every feature that calls speak() |
| Timestamp parsing bottleneck | LOW | Replace strptime with manual string slicing. Localized change in parser, no downstream impact |
| log.config missing | LOW | Add startup check and auto-creation. One-time fix, no architectural changes needed |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| PowerTaskList duplication | Phase 1 (Parser) | Unit test with real Power.log containing both streams; assert entity count matches expected |
| File reset/truncation | Phase 1 (Log Watcher) | Integration test that simulates file truncation mid-read; verify parser recovers |
| CallAfter segfault | Phase 1 (Threading) | Test that closes MainWindow while watcher thread is active; no crash, clean exit |
| Global hotkey collision | Phase 2 (Global Hotkeys) | Test RegisterHotKey return values with NVDA running; document safe key combinations |
| Speech flooding | Phase 2 (Live Announcements) | Play a game with chain deathrattles; verify speech output is coherent and not laggy |
| Timestamp performance | Phase 1 (Parser) | Benchmark parser against 10MB+ Power.log; verify parse rate exceeds event generation rate |
| log.config management | Phase 1 (First-Run) | Fresh install test: no prior Hearthstone config; verify app creates log.config and announces instructions |
| Opponent hand tracking accuracy | Phase 2 (Opponent Tracking) | Test with games involving card generation (Discover, Dredge); verify hand-tracking distinguishes drawn vs created |
| Game mode detection errors | Phase 2 (Game Tracking) | Test with Standard, Wild, and Battlegrounds games; verify mode is correctly identified and deck tracking adapts |
| hearthstone-data version mismatch | Phase 1 (Setup) | Test with outdated hearthstone-data; verify unknown cards show graceful fallback instead of crash |

## Sources

- [HearthSim: Fast Hearthstone Log Parsing](https://hearthsim.info/blog/fast-hearthstone-log-parsing/) -- PowerTaskList duplication, timestamp performance, parser architecture
- [HearthSim: Game State Protocol](https://hearthsim.info/docs/gamestate-protocol/) -- Entity management, zone transitions, packet types
- [python-hslog (GitHub)](https://github.com/HearthSim/python-hslog) -- Parser API, packet tree structure
- [HDT: Setting up log.config](https://github.com/HearthSim/Hearthstone-Deck-Tracker/wiki/Setting-up-the-log.config) -- Log configuration requirements
- [HDT: log.config constantly overwritten (Issue #3134)](https://github.com/HearthSim/Hearthstone-Deck-Tracker/issues/3134) -- log.config management problems
- [HDT: Patch breaks tracker (Issue #4466)](https://github.com/HearthSim/Hearthstone-Deck-Tracker/issues/4466) -- Hearthstone updates breaking trackers
- [wxPython Wiki: LongRunningTasks](https://wiki.wxpython.org/LongRunningTasks) -- Threading patterns, CallAfter usage
- [wxWidgets: CallAfter crash on destroy (Issue #11936)](https://github.com/wxWidgets/wxWidgets/issues/11936) -- Segfault on window destruction
- [wxPython Wiki: RegisterHotKey](https://wiki.wxpython.org/RegisterHotKey) -- Global hotkey registration on Windows
- [accessible_output2 (GitHub)](https://github.com/accessibleapps/accessible_output2) -- Speech API, supported readers
- [NVDA: Speech interrupt options (Issue #698)](https://github.com/nvaccess/nvda/issues/698) -- Speech interruption behavior
- [NVDA: Idle speech priority (Issue #13915)](https://github.com/nvaccess/nvda/issues/13915) -- Speech queue priority system
- [HearthstoneAccess: Keyboard Commands](https://www.hearthstoneaccess.com/commands.html) -- Blind player hotkey conventions
- [HearthstoneAccess: Community Version](https://hearthstoneaccess.com/) -- Accessibility mod overview and compatibility
- [Microsoft: RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey) -- Win32 global hotkey API
- StoneReader CONCERNS.md -- Existing tech debt and known bugs in current codebase

---
*Pitfalls research for: accessible Hearthstone deck tracker (wxPython + accessible_output2)*
*Researched: 2026-04-14*
