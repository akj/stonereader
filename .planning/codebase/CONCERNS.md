# Codebase Concerns

**Analysis Date:** 2026-04-14

## Tech Debt

**Broad Exception Handling in SpeechService:**
- Issue: Silent catch-all `except Exception:` blocks mask potential errors and make debugging harder
- Files: `stonereader/speech_service.py` (lines 29, 40)
- Impact: If accessible_output2 import fails for a specific reason (version mismatch, API change, missing system libraries), the fallback to stdout silently activates without any logging, making it difficult to diagnose why screen reader output stopped working
- Fix approach: Catch specific exceptions (ImportError, AttributeError), log them with context, and provide explicit fallback messaging. Consider adding a debug log level with exception details

**Unimplemented Abstract Method in BasePresenter:**
- Issue: `get_zone_items()` raises NotImplementedError but is called by zone navigation logic
- Files: `stonereader/presenters/base.py` (line 50)
- Impact: Any presenter that inherits ZoneNavigationMixin but forgets to override `get_zone_items()` will crash at runtime when navigation methods are invoked. No type system enforcement
- Fix approach: Make ZoneNavigationMixin a Protocol or ABC with `@abstractmethod` decorator. Or move `get_zone_items()` as a required protocol method to enable static type checking

**Late Runtime Imports in app.py:**
- Issue: Card library tab imports (CardDatabase, CardBrowserPresenter, CardBrowserPanel) happen inside OnInit() at lines 106-108
- Files: `stonereader/app.py` (lines 106-108)
- Impact: Import errors or circular dependency issues won't be caught until app startup (too late). Makes testing harder; feature tabs can't be loaded in isolation
- Fix approach: Move imports to module level. If circular imports occur, refactor to break cycles. Lazy import only if there's measurable startup cost

**CardDatabase.load() Has No Error Handling:**
- Issue: `load()` calls `hearthstone.cardxml.load()` without catching failures
- Files: `stonereader/models/card.py` (line 176)
- Impact: If Hearthstone data files are corrupted, missing, or the hearthstone-data package is outdated, the entire app fails to start with a cryptic error from the hearthstone library
- Fix approach: Wrap in try-except, log the error, provide fallback empty database or user-facing error message with recovery steps

**Missing Database Error Recovery:**
- Issue: `get_connection()` and `init_db()` have minimal error handling
- Files: `stonereader/db.py` (lines 35-62)
- Impact: If .stonereader directory can't be created (permission denied), or if database file is corrupted, the app crashes silently without user feedback. Database schema migration has no rollback
- Fix approach: Add explicit error handling with user-facing messages. Log failures with context. For migrations, add version tracking and rollback logic

## Known Bugs

**Text Mode State Leaks Between Windows:**
- Symptoms: If user loses focus to another window while in text mode (searching cards), InputLayer doesn't auto-exit text mode. Text mode flag remains true until the app window regains focus and user clicks outside the TextCtrl
- Files: `stonereader/input_layer.py` (lines 95-102)
- Trigger: Focus in search TextCtrl > Switch to another app (Alt+Tab) > Return to StoneReader > Press a hotkey — hotkey is silently ignored
- Workaround: Click outside TextCtrl to exit text mode, or press Tab/Enter
- Proper fix: On `wx.EVT_ACTIVATE` with `activate=False`, force exit text mode immediately instead of just in the `_on_activate` handler

**CardBrowserPanel Clipboard May Silently Fail:**
- Symptoms: "Copied X" announcement happens but clipboard is empty
- Files: `stonereader/views/card_browser.py` (lines 114-116)
- Trigger: User runs copy command when clipboard is locked or unavailable (some accessibility tools lock clipboard)
- Workaround: Retry copy after unlocking clipboard
- Proper fix: Check `wx.TheClipboard.Open()` return value and announce failure explicitly

**Zone Navigation Cursor Can Get Out of Sync:**
- Symptoms: Cursor position doesn't match announced item after rapid zone switching
- Files: `stonereader/presenters/base.py` (lines 63-75, 85-98)
- Trigger: Rapidly switch zones with up/down arrows while view hasn't updated yet, then view updates — cursor position may be higher than result set size
- Workaround: Wait for zone to stabilize before navigating
- Proper fix: Clamp cursor on every announce, not just on zone entry. Add defensive checks before accessing items[cursor]

## Security Considerations

**Database File Permissions:**
- Risk: SQLite database at `~/.stonereader/stonereader.db` is created world-readable/writable by default (depending on umask)
- Files: `stonereader/db.py` (lines 38-40)
- Current mitigation: None; relies on OS umask
- Recommendations: Explicitly set file mode to 0o600 after creating database. Never store sensitive data (API keys, passwords) in database

**No Input Validation in Deckstring Parsing:**
- Risk: User can pass malformed deckstrings to `Deck.from_deckstring()` which raises ValueError
- Files: `stonereader/models/deck.py` (lines 47-78)
- Current mitigation: ValueError with message listing missing DBF IDs
- Recommendations: Add try-except around `deckstrings.parse_deckstring()` to catch malformed input. Return user-friendly error instead of raw exception

**No Rate Limiting on Card Search:**
- Risk: `CardBrowserPresenter.search()` iterates full card database on every keystroke with no caching
- Files: `stonereader/presenters/card_browser.py` (lines 33-48)
- Current mitigation: None
- Recommendations: Add search result caching with TTL, or debounce search requests to 300ms intervals to prevent excessive CPU use

## Performance Bottlenecks

**Card Search is O(n) Per Keystroke:**
- Problem: `CardDatabase.search_cards()` filters entire collectible_cards list on every search input
- Files: `stonereader/models/card.py` (lines 200-227)
- Cause: Full-table scan with regex matching. No index. Running ~8000+ cards through filter on each keystroke
- Current capacity: ~30ms per search with 8000+ cards at steady state
- Limit: Will degrade noticeably if card count grows significantly or search logic becomes more complex
- Improvement path: Implement simple prefix index (dict of name prefixes → card lists), or use trie structure for fast prefix matching. Cache recent searches

**CardDatabase.load() Blocks UI on Startup:**
- Problem: Synchronous load of 8000+ cards and building 7 indexes before MainWindow shows
- Files: `stonereader/app.py` (line 110), `stonereader/models/card.py` (lines 175-189)
- Cause: No async/threaded loading
- Current capacity: ~500ms on modern hardware
- Limit: Will become noticeable bottleneck on slower systems or if data grows
- Improvement path: Load database in background thread, show loading indicator, populate tab only after ready. Lazy-load indexes as needed

**Zone Navigation Item Formatting Happens Per Announcement:**
- Problem: `_format_item_speech()` called every time cursor moves, even if item hasn't changed
- Files: `stonereader/presenters/base.py` (lines 52-61, 74, 96)
- Cause: Formatting done at announce time, not cache time
- Impact: Minimal for current card count, but verbose formatting will compound with larger game states
- Improvement path: Cache formatted text in zone items, or memoize format function

## Fragile Areas

**ZoneNavigationMixin Assumes List-Like Sequence:**
- Files: `stonereader/presenters/base.py` (lines 42-164)
- Why fragile: `get_zone_items()` must return indexable sequence (can't use generators or iterators). Assumes items are immutable. If a subclass returns dict.values() or generator, navigation breaks silently with IndexError
- Safe modification: Document that get_zone_items() must return a list or tuple (indexable). Add type hint with `Sequence[T]` but verify implementation returns concrete sequence. Test with various container types
- Test coverage: `tests/test_zone_navigation.py` covers list items but not edge cases like empty sequences or single-item zones being modified during navigation

**InputLayer Key Map Must Not Have Colliding Keys:**
- Files: `stonereader/input_layer.py` (lines 59, 86-93)
- Why fragile: No validation that key specs are unique. If two presenters accidentally register same key (e.g., both "left"), one silently overwrites the other at runtime
- Safe modification: Add key uniqueness validation in `activate_view()`. Log warnings if duplicate keys detected. Add test to ensure each presenter has unique hotkeys
- Test coverage: `tests/test_input_layer.py` covers single presenter; no multi-presenter conflict tests

**Detail Cursor Persists Across Item Changes:**
- Files: `stonereader/presenters/base.py` (lines 46, 94, 150-153)
- Why fragile: `_detail_cursor` is a simple int that doesn't reset when item changes within the same zone. If user reads down through card details, then moves to next card, cursor is still at previous line. If new card has fewer detail lines, cursor can be out of bounds
- Safe modification: Reset `_detail_cursor = -1` whenever zone cursor changes (in `move_in_zone()`, not just on zone switch). Add bounds check in `read_detail_lines()` before accessing lines[cursor]
- Test coverage: `tests/test_zone_navigation.py` has detail reading tests but no tests for cursor position after item change

**CardDatabase Name Lookup is Case-Insensitive but Inconsistent:**
- Files: `stonereader/models/card.py` (lines 182, 198)
- Why fragile: Cards indexed by `.lower()` name in `cards_by_name` dict, but if API caller passes mixed-case to `get_card_by_name()`, the lowercase conversion happens in the method, not at index time. If index and lookup use different case logic, lookups fail silently
- Safe modification: Add explicit test for mixed-case lookup. Document that all keys in cards_by_name are lowercase. Consider using enum or constant for case-sensitivity behavior
- Test coverage: No tests verify `get_card_by_name()` with mixed-case input

## Scaling Limits

**Single CardDatabase Instance in Memory:**
- Current capacity: ~100MB peak memory (8000 cards × 7 indexes)
- Limit: Will grow linearly with each new card set released (~300-400 cards per expansion)
- Scaling path: Lazy-load card indexes on first use. Implement database queries instead of in-memory indexes for large datasets

**No Pagination or Lazy Loading for Search Results:**
- Current capacity: Search returns all matching cards (currently max ~2000 for broad queries)
- Limit: If search returns 5000+ cards, view ListCtrl becomes slow to render and update
- Scaling path: Implement virtual scrolling or paginated result sets. Return top N results + "load more" button

**Linear Time Complexity for Every Zone Navigation Operation:**
- Current capacity: Smooth for 1-2 zones with 30-50 items per zone
- Limit: Game replays with 50+ game states × multiple zones will degrade
- Scaling path: Pre-compute frequently accessed zone data (e.g., cumulative indices)

## Dependencies at Risk

**accessible_output2 Version Pinning:**
- Risk: Pinned to 0.17+ but no upper bound. Future versions may have breaking API changes or drop Python 3.12 support
- Impact: Update to incompatible version = silent fallback to stdout (no screen reader output)
- Migration plan: Add upper bound in pyproject.toml (e.g., <1.0). Create integration tests that verify screen reader detection works. Consider switching to newer a11y library if accessible_output2 becomes unmaintained

**hearthstone Library Dependency Chain:**
- Risk: Transitive dependency on hearthstone-data (very large package, 50MB+). If hearthstone API changes, card loading fails
- Impact: App won't start if hearthstone-data is corrupt or incompatible
- Migration plan: Add explicit version bounds. Test against multiple hearthstone versions in CI. Consider vendoring critical data if upstream becomes unreliable

**wxPython Version Compatibility:**
- Risk: Pinned to 4.2.5+ but wx is slow to release major versions. Screen reader compatibility may vary across versions
- Impact: Newer wxPython versions may have different NVDA/JAWS integration; older versions may not work with Python 3.13+
- Migration plan: Test against multiple wxPython versions in CI. Document tested version matrix. Have deprecation plan if wx drops critical features

## Missing Critical Features

**No Deck Manager Presenter/View:**
- Problem: `Deck` model is fully implemented but no UI to display deck contents
- Blocks: Can't browse decks, can't compare cards in deck vs. full set
- Requires: DeckManagerPresenter (with ZoneNavigationMixin), DeckManagerPanel, deck search/filter logic
- Priority: High — core feature promised in README

**No Replay Viewer Presenter/View:**
- Problem: `ReplayState` and `GameState` models are implemented but no presenter or view
- Blocks: Can't view game turns, can't navigate board/hand, can't rewind game
- Requires: ReplayViewerPresenter (with multiple zones for board/hand/log), ReplayViewerPanel, game navigation logic
- Priority: High — core feature promised in README

**No Error Boundary / Crash Handler:**
- Problem: Any uncaught exception in presenter or view crashes entire app with no user-facing message
- Blocks: Users can't recover from edge cases without app restart
- Requires: Top-level exception handler in MainLoop, user-facing error dialog, recovery options
- Priority: Medium — affects user experience during exploration

**No Logging System:**
- Problem: No structured logging, no debug mode, no way for users to provide logs for bug reports
- Blocks: Hard to diagnose issues in production. Users see blank screen with no explanation
- Requires: Python logging setup, configurable log level, file or syslog output
- Priority: Medium — critical for debugging accessibility issues (NVDA/JAWS interactions)

## Test Coverage Gaps

**No Integration Tests for SpeechService Fallback:**
- What's not tested: Behavior when accessible_output2 is unavailable (import failure, no screen reader running). Currently only unit mocks in conftest
- Files: `stonereader/speech_service.py`, `tests/conftest.py`
- Risk: Fallback to stdout may be broken or announce different messages than expected. Real NVDA/JAWS integration never tested
- Priority: High — core accessibility feature

**No Tests for CardDatabase Load Failures:**
- What's not tested: Behavior when hearthstone-data is missing, corrupted, or hearthstone library API changes
- Files: `stonereader/models/card.py` (lines 174-189)
- Risk: App silently crashes on startup with unhelpful error message if data is missing
- Priority: High — affects first-run experience

**No Tests for InputLayer Text Mode Transitions:**
- What's not tested: Text mode flag behavior across focus loss, window activation, multiple TextCtrl widgets
- Files: `stonereader/input_layer.py` (lines 69-102)
- Risk: Text mode leaks (described above in Known Bugs) won't be caught by CI
- Priority: Medium — affects keyboard usability

**No Tests for Database Connection Failures:**
- What's not tested: Behavior when .stonereader directory can't be created (permission denied), database file is locked, disk is full
- Files: `stonereader/db.py` (lines 35-62)
- Risk: App crashes silently without user feedback if database initialization fails
- Priority: Medium — affects startup reliability

**No Tests for Rapid Zone Switching:**
- What's not tested: Cursor position consistency during rapid navigation (described above in Known Bugs)
- Files: `stonereader/presenters/base.py` (lines 85-110)
- Risk: Race conditions or out-of-bounds access during quick navigation won't be caught
- Priority: Medium — affects user experience with keyboard navigation

**No Accessibility Tests for UI Components:**
- What's not tested: Screen reader announces correct names/roles for widgets, tab order is correct, keyboard navigation reaches all elements
- Files: `stonereader/views/card_browser.py`, `stonereader/views/base.py`
- Risk: Violations of WCAG AA standards won't be caught automatically. Visual components may not be accessible
- Priority: High — entire project is accessibility-first

---

*Concerns audit: 2026-04-14*
