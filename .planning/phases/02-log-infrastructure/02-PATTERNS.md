# Phase 2: Log Infrastructure - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 18 (12 source + 6 test/fixture)
**Analogs found:** 17 / 18 (one no-analog: `_parser.py` hslog wrapper — first parser layer in repo)

## Scope and Source of File List

Files were enumerated from CONTEXT.md §"New code shape" (lines 130–143) and RESEARCH.md §"Recommended public API" (lines 478–500) plus §"Architecture Recommendation: GameTracker Facade" (lines 432–465). Internal modules use the leading-underscore convention from RESEARCH.md (`_tracker.py`, `_watcher.py`, etc.) — `services/__init__.py` re-exports the public API.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `stonereader/services/__init__.py` | barrel | re-export | `stonereader/models/__init__.py` | exact |
| `stonereader/services/_tracker.py` | facade / orchestrator | event-driven (subscriber dispatch) | `stonereader/presenters/deck_manager.py` (callback-set + `_notify_view`) | role-match |
| `stonereader/services/_watcher.py` | watcher / poller | streaming (file tail via `wx.Timer`) | `stonereader/input_layer.py` (event-routing module, no UI) | partial (event-routing shape) |
| `stonereader/services/_line_reader.py` | utility | transform (bytes → lines) | `stonereader/models/card.py` `_strip_tags` (pure-string utility) | partial |
| `stonereader/services/_parser.py` | parser / library wrapper | transform (line → packets) | none (no existing parser-wrapper layer) | NO ANALOG — use RESEARCH.md |
| `stonereader/services/_engine.py` | service | event-driven (packets → state + events) | `stonereader/presenters/base.py` `BasePresenter` + `ZoneNavigationMixin` (state-holder pattern) | partial |
| `stonereader/services/_events.py` | model (frozen events) | data | `stonereader/models/game_state.py` (frozen `@dataclass` family) | exact |
| `stonereader/services/_log_path.py` | service | one-shot (path discovery) | `stonereader/db.py` `get_connection` (path discovery + `~/.stonereader` mkdir) | role-match |
| `stonereader/services/_log_config.py` | service | one-shot (idempotent INI bootstrap) | `stonereader/db.py` `init_db` (idempotent schema bootstrap) | role-match |
| `stonereader/services/_process_detect.py` | service | request-response (cached lookup) | `stonereader/speech_service.py` `SpeechService.__init__` (resilience-on-import + cached state) | role-match |
| `stonereader/services/_logging_config.py` | config | one-shot | `stonereader/db.py` `get_connection` (`~/.stonereader/` dir mkdir) | role-match |
| `stonereader/models/game_state.py` (modified — D-08) | model | data | self (extending existing `GameState`/`Hero`/`GameEntity`) | exact |
| `stonereader/app.py` (modified — integration) | integration | one-shot | self (`StoneReaderApp.OnInit` lines 350–459 — adding GameTracker wiring after CardDatabase load) | exact |
| `stonereader/__main__.py` (modified — logging bootstrap) | integration | one-shot | self (entry point — call `configure_logging()` before `StoneReaderApp()`) | exact |
| `pyproject.toml` (modified — add `hslog`, `psutil`) | config | data | self | exact |
| `tests/test_services/conftest.py` | fixture | test infra | `tests/conftest.py` (`MockSpeechService` test double pattern) | exact |
| `tests/test_services/test_*.py` | test | test infra | `tests/test_speech_service.py` + `tests/test_db.py` (capsys + tmp_path patterns) | exact |
| `tests/fixtures/log/*.log` | fixture | data | none (first binary/text fixture set) | NO ANALOG — capture procedure in RESEARCH.md §"Test Fixture Capture Procedure" |

---

## Pattern Assignments

### `stonereader/services/__init__.py` (barrel, re-export)

**Analog:** `stonereader/models/__init__.py`

**Whole-file pattern (`models/__init__.py:1-19`)** — copy verbatim shape:
```python
"""StoneReader domain models."""

from stonereader.models.card import Card, CardDatabase
from stonereader.models.deck import Deck, DeckSummary, MissingCardsError
from stonereader.models.game_state import GameEntity, GameState, Hero
from stonereader.models.replay import ReplayState

__all__ = [
    "Card",
    "CardDatabase",
    ...
]
```

**Adaptation:** Re-export `GameTracker` from `_tracker` and the event types from `_events` (full list in RESEARCH.md lines 482–496). Underscore-prefixed `_watcher`, `_engine`, `_parser` etc. are *not* re-exported — internal modules importable for tests but not part of the stable API (RESEARCH.md line 499).

**Gotcha:** Module-level docstring required (every existing `__init__.py` has one).

---

### `stonereader/services/_tracker.py` (facade, event-driven)

**Analog:** `stonereader/presenters/deck_manager.py` lines 28–98

**Subscriber registration pattern** (deck_manager.py lines 31–38, 68–93):
```python
self._on_state_changed: Callable[[list[DeckSummary], int], None] | None = None
self._on_open_deck: Callable[[Deck], None] | None = None
self._on_request_delete_confirm: Callable[[str], bool] | None = None

def set_on_open_deck(
    self, callback: Callable[[Deck], None]
) -> None:
    """Set callback invoked when user presses Enter to open a deck."""
    self._on_open_deck = callback
```

**Adaptation for D-02 (multiple subscribers, not one):** the existing pattern is single-callback (`set_on_*`); D-02 explicitly mandates multi-subscriber `subscribe()`/`unsubscribe()`. Keep the *type signature* idiom (`Callable[..., None]`, `| None` for unset) but store `list[Callable]` instead of a single optional. Shape:
```python
self._subscribers: list[Callable[[GameEvent, GameState], None]] = []

def subscribe(self, callback: Callable[[GameEvent, GameState], None]) -> None:
    if callback not in self._subscribers:
        self._subscribers.append(callback)

def unsubscribe(self, callback: Callable[[GameEvent, GameState], None]) -> None:
    if callback in self._subscribers:
        self._subscribers.remove(callback)
```

**Notify pattern** (deck_manager.py lines 95–98):
```python
def _notify_view(self) -> None:
    if self._on_state_changed is not None:
        cursor = self._zone_cursors.get(_DECKS_ZONE, 0)
        self._on_state_changed(self._decks, cursor)
```
**Adaptation:** Iterate the list and wrap each call in `try/except` per Pitfall 3 (RESEARCH.md line 727 — "Subscriber callback raises an exception" must not break the loop or starve other subscribers). Use `logger.exception("subscriber raised")` and continue — same pattern as the watcher's tick error handler.

**Gotcha:** `_tracker.py` *owns* lifecycle (start/stop, process-gone reset, file rotation reset). Phase 3 imports `from stonereader.services import GameTracker` and never touches `_watcher`/`_engine` directly (RESEARCH.md lines 470–476). Lifecycle integration point is `StoneReaderApp.OnInit()` — see "`stonereader/app.py` (modified)" below.

---

### `stonereader/services/_watcher.py` (watcher, streaming)

**Analog:** `stonereader/input_layer.py` (event-routing module with no UI dependencies, swallowed exceptions, single-method tick equivalent in `_on_char_hook`)

**Logger acquisition** (every analog uses `logging.getLogger(__name__)` per D-16; closest pre-existing equivalent is the resilience-on-failure pattern in speech_service.py:29-31):
```python
import logging
logger = logging.getLogger(__name__)
```

**Tick-error containment pattern** — adapt from `speech_service.py:38-41` (catch-everything-and-fall-back):
```python
# speech_service.py:38-41
try:
    self._output.speak(text, interrupt=interrupt)
except Exception:
    print(text)
```
**Adapt to D-04:** swap `print(text)` for `logger.exception("watcher tick failed")` and *return* (don't re-raise). The skeleton in RESEARCH.md lines 905–909 already encodes this:
```python
def _tick(self) -> None:
    try:
        self._do_tick()
    except Exception:
        logger.exception("watcher tick failed")  # D-04: log and continue
```

**Skeleton already provided in RESEARCH.md lines 858–963 — copy verbatim, then expand `_maybe_backward_scan` per RESEARCH.md lines 503–522.**

**Gotchas:**
- `wx.Timer` must be created with a `wx.EvtHandler` parent (`MainWindow` is one). Pitfall 9 (RESEARCH.md line 759): do not start the Timer before `frame.Show()` — `OnInit()` calls `Show()` last, so wire `start()` *after* `self._frame.Show()`.
- File reads are bytes (`open(path, "rb")`) — decoding is the `_LineReader`'s job. Don't decode at the watcher level (Pitfall 8, line 755: must reset partial-line decoder on file reset).

---

### `stonereader/services/_line_reader.py` (utility, transform)

**Analog:** `stonereader/models/card.py` `_strip_tags` lines 8–17 (pure stateless string utility — closest in tree)

**Pattern from card.py:8-17** (single-purpose utility, leading underscore = private to module):
```python
def _strip_tags(text: str) -> str:
    """Strip HTML tags, game markup, and normalize whitespace in card text."""
    text = re.sub(r"<[^>]+>", "", text)
    ...
    return text
```

**Adaptation:** `_LineReader` is *stateful* (carries an IncrementalDecoder and partial-line buffer across `feed()` calls), so it's a class, not a function. RESEARCH.md lines 528–553 provide the full implementation — copy verbatim. Class-name leading underscore = "module-private but importable for tests" (matches HDT/Firestone convention; RESEARCH.md line 499).

**Gotcha:** Pitfall 8 (RESEARCH.md line 755) — `reset()` must clear *both* the decoder state and `self._partial`. The skeleton's `reset()` already does this; do not regress it during refactor.

---

### `stonereader/services/_parser.py` (parser wrapper)

**Analog:** NONE in existing tree — first thin-wrapper-around-an-external-parser layer.

**Substitute pattern source:** Use RESEARCH.md §"Library Reference: hslog API Surface and Contract" (lines 137–225) as the authoritative spec for what `_parser.py` exports. Import isolation rule (D-10) — `hslog` is imported *only* in this file, and the engine consumes our `Packet`-shaped objects, never `hslog.PacketTree` nodes directly.

**Closest stylistic touchstone for the import-isolation pattern:** `stonereader/speech_service.py` lines 18–31 — defensive lazy import of `accessible_output2` inside `__init__`:
```python
def __init__(self) -> None:
    self._use_stdout = False
    try:
        from accessible_output2.outputs.auto import Auto

        candidate = Auto()
        ...
    except Exception:
        self._use_stdout = True
        self._output = None
```
**Adapt for `_parser.py`:** hslog is a hard dependency (D-09) — import it at module top, not lazily. But mirror the *exception-translation* spirit: catch `hslog.exceptions.RegexParsingError`/`CorruptLogError`/`NoSuchEnum` (per RESEARCH.md "Exceptions" table lines 184–192) and re-raise as our own typed errors so engine/tracker callers don't need to import hslog symbols.

**Gotcha:** Pitfall 6 (RESEARCH.md line 742) — `NoSuchEnum` from hslog can crash on Hearthstone enum drift. Catch it, log via `logger.warning("hslog NoSuchEnum: %s", exc)`, and skip the line. Don't let it bubble through to the watcher's tick handler.

---

### `stonereader/services/_engine.py` (service, event-driven)

**Analog:** `stonereader/presenters/base.py` `BasePresenter` (state-holder) + the existing presenters' "construct new immutable, never mutate" rhythm.

**Frozen-snapshot construction pattern** — adapt the "presenters never mutate models, they recompute" rhythm. Closest in-tree: `stonereader/presenters/deck_manager.py` reloads the entire `_decks` list on changes rather than mutating. Engine does the same with `GameState` per D-07.

**Logger pattern** (every Phase 2 module uses this — D-16):
```python
import logging
logger = logging.getLogger(__name__)
```

**State-management shape** — model after `BasePresenter.__init__` (base.py:21-22):
```python
class BasePresenter:
    def __init__(self, speech: SpeechService) -> None:
        self._speech = speech
```
**Adapt:**
```python
class GameEngine:
    def __init__(self, card_db: CardDatabase) -> None:
        self._card_db = card_db
        self._current_state: Optional[GameState] = None  # D-07: only the latest snapshot
        # Internal accumulators: _played_history, _drawn_history (per RESEARCH.md GameState diff)
```

**Gotchas:**
- D-07: every meaningful change → new `GameState(...)` construction. Never `dataclasses.replace()` and re-assign the same instance — be consistent with the codebase's "construct new" rhythm in `models/game_state.py`.
- Pitfall 4 (RESEARCH.md line 732): "Frozen GameState deep-copy footgun" — do not deep-copy on every snapshot; share `Tuple[...]` references for unchanged zones. Tuples are already immutable, so sharing is safe.
- Engine **must not import hslog** (D-10).
- Engine **must not import `wx`** — keeps it reusable by Phase 4 (replay XML) without a wx context.

---

### `stonereader/services/_events.py` (model)

**Analog:** `stonereader/models/game_state.py` lines 1-60 (the entire frozen-dataclass family is the canonical pattern)

**Frozen-dataclass shape** (game_state.py:1-16):
```python
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
```

**Apply per-event-class:**
```python
@dataclass(frozen=True)
class GameEvent:
    """Base type for all engine-emitted events."""
    timestamp: float  # monotonic seconds since engine start
    turn: int


@dataclass(frozen=True)
class CardDrawn(GameEvent):
    entity_id: int
    card_id: str
    base_card: Optional[Card]
    controller: int
```

**Gotchas:**
- D-18 locks `@dataclass(frozen=True)` — no `attrs` migration. Type hints throughout (`Optional[Card]`, `Tuple[..., ...]`).
- Default-value ordering: parent class fields without defaults must precede child fields with defaults (Python dataclass inheritance rule). If `GameEvent` has any non-default fields, child events that add non-default fields must list them *before* any defaulted fields.
- Use `Tuple[X, ...]` not `List[X]` for any collection field — matches `GameState.player_board: Tuple[GameEntity, ...]` convention (game_state.py:44).
- Event class list (D-06): `GameStarted, GameEnded, TurnChanged, MulliganDone, CardDrawn, CardPlayed, CardRevealed, CardRemoved, AttackStarted, MinionDied, DamageDealt`.

---

### `stonereader/services/_log_path.py` (service, one-shot)

**Analog:** `stonereader/db.py` `get_connection` lines 37–45 (path discovery + idempotent directory creation under `~/.stonereader/`)

**`db.py:37-45`:**
```python
def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection. Defaults to ~/.stonereader/stonereader.db."""
    if db_path is None:
        data_dir = Path.home() / ".stonereader"
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / "stonereader.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
```

**Adaptation:** `_log_path.py` doesn't *create* the Power.log directory (Hearthstone owns it). Pattern reuse is for shape only:
- Use `pathlib.Path` throughout (no `os.path.join`)
- Top-level `def discover_power_log_path() -> Optional[Path]:` returning `None` when not found (matches the codebase's `Optional` + early-return rhythm; e.g. `Card.get_card_by_id` returns `Optional[Card]`)
- Sub-helpers private (`_path_from_running_process`, `_path_from_registry`) — leading underscore convention

**Gotcha:** Pitfall 1 (RESEARCH.md line 716) — caller must call this *every tick* (cheap; mtime stat only) so a Hearthstone restart with new `Logs/Hearthstone_*/` subdirectory is picked up. Don't cache the path forever.

---

### `stonereader/services/_log_config.py` (service, one-shot)

**Analog:** `stonereader/db.py` `init_db` lines 57–64 (idempotent bootstrap — check current state, only write if changed)

**`db.py:57-64`:**
```python
def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist. Idempotent."""
    version = get_schema_version(conn)
    if version >= 1:
        return
    conn.executescript(_SCHEMA_V1)
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (1,))
    conn.commit()
```

**Adaptation:** RESEARCH.md lines 808–856 already provides the full `ensure_log_config(path)` implementation following the same idempotent-with-changed-flag rhythm. The `db.init_db` analog confirms the *control flow* (read current state, compare, only mutate if delta) is canonical in the codebase.

**Gotchas:**
- `parser.optionxform = str` (RESEARCH.md line 838) — preserves key case. Hearthstone's `[Power]` keys are case-sensitive.
- Pitfall 5 (RESEARCH.md line 737): use `RawConfigParser`, not `ConfigParser`, so other tools' `%`-containing values aren't corrupted by interpolation.
- Return `True` only when something was written — caller (`_tracker.py` or `app.py`) uses this to optionally `speech.speak("Hearthstone logging enabled")`.

---

### `stonereader/services/_process_detect.py` (service, request-response)

**Analog:** `stonereader/speech_service.py` lines 11–31 (cached-state-on-init + resilience-on-failure)

**`speech_service.py:18-31`:**
```python
def __init__(self) -> None:
    self._use_stdout = False
    try:
        from accessible_output2.outputs.auto import Auto

        candidate = Auto()
        if candidate.get_first_available_output() is None:
            self._use_stdout = True
            self._output = None
        else:
            self._output = candidate
    except Exception:
        self._use_stdout = True
        self._output = None
```

**Adaptation:** `ProcessDetector` similarly absorbs OS-API flakiness. RESEARCH.md lines 599–628 already provide the full implementation. Mirror these from `speech_service.py`:
- Constructor stores defensive defaults (`_last_check = 0.0`, `_last_result = (False, None)`)
- Per-call `try/except (psutil.NoSuchProcess, psutil.AccessDenied): continue` — same shape as the bare `except Exception` in speech_service.py:40

**Gotchas:**
- Pitfall 2 (RESEARCH.md line 722): `psutil.process_iter` is fast (~5ms) but called every 150ms tick; cache TTL of 2s (RESEARCH.md line 600) keeps amortized cost ~0.4ms/tick.
- `_HEARTHSTONE_EXE` constant uses `.lower()` comparison — Windows process names are case-insensitive.

---

### `stonereader/services/_logging_config.py` (config, one-shot)

**Analog:** `stonereader/db.py` `get_connection` lines 37–42 (`~/.stonereader/` directory pattern is the *exact* same dir D-16 reuses)

**Reused fragment from `db.py:39-41`:**
```python
data_dir = Path.home() / ".stonereader"
data_dir.mkdir(exist_ok=True)
```

**Apply verbatim** in `_logging_config.py` — RESEARCH.md lines 778–784 already does this (`LOG_DIR = Path.home() / ".stonereader"; LOG_DIR.mkdir(exist_ok=True)`). The two paths *must* agree (db file and log file in same dir) — the analog file is the source of truth.

**Gotchas:**
- Pitfall 10 (RESEARCH.md line 763): `configure_logging()` must be idempotent. RESEARCH.md lines 802–805 show the handler-deduplication check; do not skip this.
- Call site is `stonereader/__main__.py` *before* `StoneReaderApp()` so wx startup errors get logged (CONTEXT.md line 127).

---

### `stonereader/models/game_state.py` (modified — D-08)

**Analog:** itself (game_state.py lines 1-60) — extending in place

**Existing structure (game_state.py:1-16) is the spine to extend:**
```python
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
```

**Adaptation:** RESEARCH.md lines 290–392 propose the full diff. Apply it. Critical points:
- D-18 locks `@dataclass(frozen=True)` — no migration to `attrs`.
- All new fields have defaults (RESEARCH.md line 402) — backward-compat with existing fixtures.
- New `PlayedCard` class follows the same shape as existing `GameEntity` (card_id, base_card, name, controller).
- `Tuple[..., ...]` for collections — never `List[...]`.

**Gotcha:** `GameState.player_hand: Tuple[GameEntity, ...]` (line 46) is a non-defaulted positional. New defaulted fields go *after* all existing positional fields. The proposed diff in RESEARCH.md preserves this ordering — verify before committing.

---

### `stonereader/app.py` (modified — integration)

**Analog:** itself, `StoneReaderApp.OnInit()` lines 350–459 — adding GameTracker wiring after CardDatabase load.

**Existing integration shape (app.py:350-368):**
```python
def OnInit(self) -> bool:  # noqa: N802 -- wx override
    self._frame = MainWindow()
    nav = self._frame.nav
    speech = self._frame.speech
    input_layer = self._frame.input_layer
    db_conn = self._frame.db_conn

    # Load card database
    from stonereader.models.card import CardDatabase

    card_db = CardDatabase.load()

    # --- Home Screen ---
    from stonereader.presenters.home import HomePresenter
    from stonereader.views.home import HomePanel
    ...
```

**Adaptation:** insert tracker initialization between `card_db = CardDatabase.load()` and the first presenter wiring:
```python
# --- Game Tracker (Phase 2) ---
from stonereader.services import GameTracker
from stonereader.services._log_config import ensure_log_config

ensure_log_config()  # idempotent; D-11
self._tracker = GameTracker(card_db=card_db)
self._tracker.start(parent=self._frame)  # wx.Timer parented on the frame; D-01
```

**Gotchas:**
- Pitfall 9 (RESEARCH.md line 759): start the Timer *after* `self._frame.Show()` runs (line 458). Either move the `start()` call to a `wx.CallAfter` or place it after `self._frame.Show()`.
- `_on_close` (app.py:342-344) closes the DB; add `self._tracker.stop()` there too — symmetric lifecycle.
- Phase 3 will subscribe via `self._tracker.subscribe(presenter._on_event)` — leave a hook (`@property def tracker`) on `MainWindow` analogous to the existing `speech` / `input_layer` / `db_conn` properties (lines 251-265).

---

### `stonereader/__main__.py` (modified — logging bootstrap)

**Analog:** itself (`__main__.py`:1-13) — minimal entry point.

**Existing 13 lines** (verbatim from file):
```python
"""StoneReader entry point."""

from stonereader.app import StoneReaderApp


def main() -> None:
    app = StoneReaderApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
```

**Adaptation:** insert `configure_logging()` *first* (CONTEXT.md line 127: "captures startup errors before the wx app initializes"):
```python
"""StoneReader entry point."""

from stonereader.app import StoneReaderApp
from stonereader.services._logging_config import configure_logging


def main() -> None:
    configure_logging()
    app = StoneReaderApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
```

**Gotcha:** Do not `configure_logging()` again inside `app.py`. Pitfall 10 catches the duplicate-handler case but the right answer is "configure exactly once at the entry point."

---

### `tests/test_services/conftest.py` (fixture, test infra)

**Analog:** `tests/conftest.py` (whole file)

**Whole-file pattern (`tests/conftest.py:1-22`):**
```python
"""Shared test fixtures."""

from __future__ import annotations

from stonereader.speech_service import SpeechService


class MockSpeechService(SpeechService):
    """SpeechService that captures speech output for testing."""

    def __init__(self) -> None:
        self._use_stdout = True
        self._output = None
        self.spoken: list[tuple[str, bool]] = []

    def speak(self, text: str, interrupt: bool = True) -> None:
        self.spoken.append((text, interrupt))
```

**Adaptation:** create test doubles for the moving parts of Phase 2:
- `MockProcessDetector` — same shape as `MockSpeechService`: subclass `ProcessDetector`, override `is_running()` to return scripted values.
- `FakeClock` for time.monotonic-driven TTL caching (Pitfall 2 — process-detect TTL).
- pytest fixture `power_log_fixture(name)` that returns `tests/fixtures/log/{name}.log` as `Path` — feeds `_LineReader` / `_parser` directly without touching the real filesystem watcher.

**Gotcha:** The `MockSpeechService` overrides `__init__` to skip `super().__init__()` because the parent constructor probes for screen readers. Apply the same defensive override pattern in `MockProcessDetector` so tests don't actually call `psutil.process_iter`.

---

### `tests/test_services/test_*.py` (tests, test infra)

**Analogs:**
- `tests/test_speech_service.py` (capsys + simple-construction pattern)
- `tests/test_db.py` (`tmp_path` fixture for filesystem isolation, idempotency assertions)

**`tests/test_db.py:4-15` — `tmp_path` pattern for filesystem-touching code:**
```python
def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "decks" in tables
    ...
    conn.close()
```

**Apply to:**
- `test_log_config.py` — `tmp_path / "log.config"`, assert `[Power]` section present after `ensure_log_config(tmp_path / "log.config")`. Idempotency assertion: call twice, no error, return value flips True→False.
- `test_log_path.py` — `tmp_path` simulating `Logs/Hearthstone_2026_01_01_12_00_00/` subdirectories, assert newest-mtime selection.
- `test_watcher.py` — `tmp_path` log file, append bytes, drive `_tick()` manually, assert `on_lines` callback invoked.
- `test_engine.py`, `test_parser.py` — feed lines from `tests/fixtures/log/*.log` (D-17), assert event sequence and final `GameState`.

**`tests/test_speech_service.py:9-14` — capsys pattern for stdout-fallback tests:**
```python
def test_speak_does_not_raise(capsys):
    svc = SpeechService()
    svc.speak("hello")
    # On CI/dev without a screen reader, falls back to stdout
    captured = capsys.readouterr()
    assert "hello" in captured.out
```

**Apply to:** `test_logging_config.py` — assert `configure_logging()` writes to both file and stdout via capsys + `tmp_path` injection.

**Gotchas:**
- All filesystem tests must use `tmp_path` — never touch `~/.stonereader/`. The existing tests are 100% disciplined about this; do not regress.
- No-`__init__.py` style: existing `tests/` does not have an `__init__.py`. `tests/test_services/` should follow the same convention. Use pytest's auto-discovery, not packaging.
- Test names use plain `def test_xxx(...)`, no class wrapping. Match the existing style.

---

### `tests/fixtures/log/*.log` (data fixtures)

**Analog:** NONE — first text/binary fixture set in the repo.

**Substitute pattern source:** RESEARCH.md §"Test Fixture Capture Procedure (D-17)" (lines 632–698) provides the manual capture procedure. Required fixtures (RESEARCH.md lines 634–645): `match_start.log`, `mid_game.log`, `game_end.log`, `reconnect.log`, `battlegrounds.log`. Each ~50–200 KB.

**Gotcha:** D-17 commits these to the repo. Confirm each capture is from a real Hearthstone session (no synthesizing — synthetic fixtures don't catch real-world line variants). Consider scrubbing player names if any privacy concern; Hearthstone's Power.log includes `BnetID` values.

---

## Shared Patterns

### Logger acquisition (D-16)

**Source:** `stonereader/services/_logging_config.py` (new) — but every Phase 2 source file uses the same one-liner immediately after imports:
```python
import logging

logger = logging.getLogger(__name__)
```

**Apply to:** every new module under `stonereader/services/` *except* `__init__.py` and `_events.py` (pure dataclasses, nothing to log).

**Justification:** D-16 mandate. No existing in-tree analog because the codebase has no logging today (CONCERNS.md "No Logging System") — this *closes* that concern. Be the new pattern.

---

### Frozen-dataclass shape

**Source:** `stonereader/models/game_state.py:1-60`

**Verbatim shape to copy:**
```python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from stonereader.models.card import Card


@dataclass(frozen=True)
class Foo:
    """Single-line summary."""

    required_field: int
    optional_field: Optional[Card] = None
    collection: Tuple[Bar, ...] = ()
    mapping: Dict[str, Any] = field(default_factory=dict)
```

**Apply to:** all classes in `_events.py` and any new types in `_engine.py` exposed in snapshots, plus the D-08 extension to `models/game_state.py`.

**Gotcha:** `field(default_factory=dict)` for mutable defaults — never `= {}` (Python class-level mutable default footgun). Existing `GameEntity.tags` (game_state.py:35) already uses this idiom; mirror it.

---

### Resilience-on-external-failure

**Source:** `stonereader/speech_service.py:38-41`

```python
try:
    self._output.speak(text, interrupt=interrupt)
except Exception:
    print(text)
```

**Apply to:**
- Watcher tick (`_watcher.py._tick`) — `except Exception: logger.exception("watcher tick failed")` (D-04).
- Subscriber dispatch (`_tracker.py.notify`) — Pitfall 3, isolate each subscriber's exception so others still receive the event.
- Process detector (`_process_detect.py`) — `except (psutil.NoSuchProcess, psutil.AccessDenied): continue` per RESEARCH.md line 615.
- Parser (`_parser.py`) — translate hslog exceptions, swallow `NoSuchEnum` per Pitfall 6.

**Adaptation rule:** the analog catches *bare* `Exception` and falls back to stdout. New code catches *specific* exceptions where possible (e.g., `psutil.NoSuchProcess`, `hslog.exceptions.RegexParsingError`) and falls back to `logger.exception(...)` — bare `Exception` only at the outermost tick boundary.

---

### `~/.stonereader/` directory ownership

**Source:** `stonereader/db.py:39-41`

```python
data_dir = Path.home() / ".stonereader"
data_dir.mkdir(exist_ok=True)
```

**Apply to:** `_logging_config.py` for `~/.stonereader/stonereader.log`. The two callsites must agree on the path — when one creates the dir, the other can rely on its existence, but neither assumes order. Both call `mkdir(exist_ok=True)` independently. This is idiomatic Python; the existing analog gets it right.

**Gotcha:** Use `Path.home()` not `os.path.expanduser("~")` — matches existing convention.

---

### Absolute imports throughout

**Source:** every file in the codebase. Confirmed canonical via CLAUDE.md: "Absolute imports always used: `from stonereader.models.card import Card`. Never use relative imports."

**Apply to:** every new file. No `from . import ...` anywhere in `stonereader/services/`. Even within the package, use the full path (e.g., `from stonereader.services._line_reader import _LineReader`, not `from ._line_reader import _LineReader`).

**Gotcha:** This deviates from common Python conventions where intra-package relative imports are normal. The project picks absolute everywhere — do not regress.

---

## No Analog Found

| File | Role | Data Flow | Reason | Substitute Source |
|------|------|-----------|--------|-------------------|
| `stonereader/services/_parser.py` | parser wrapper | transform | First thin-wrapper-around-an-external-parser layer in tree | RESEARCH.md §"Library Reference: hslog API Surface and Contract" (lines 137–225) + speech_service.py's exception-translation spirit |
| `tests/fixtures/log/*.log` | data fixtures | data | First binary/text fixtures in tree | RESEARCH.md §"Test Fixture Capture Procedure (D-17)" (lines 632–698) — manual capture procedure |

---

## Metadata

**Analog search scope:**
- `stonereader/` (all subdirs: `models/`, `presenters/`, `views/`)
- `stonereader/__main__.py`, `app.py`, `db.py`, `input_layer.py`, `speech_service.py`
- `tests/` (top-level test files, `conftest.py`)

**Files scanned:** ~30 source/test files. Per-file Read calls: 11 distinct files (no re-reads).

**Pattern extraction date:** 2026-04-25

**Extraction notes:**
- Where the existing codebase has no analog (parser-wrapper layer, multi-subscriber bus, fixtures), RESEARCH.md is cited as the substitute pattern source.
- Where the existing codebase has a strong analog but Phase 2's requirements supersede it (single-callback `set_on_*` → multi-subscriber `subscribe()`), the analog's *type signature idiom* and *defensive shape* are extracted; the *cardinality* is adapted per D-02.
- D-16 (logging) has no in-tree analog because the codebase has no logging today — Phase 2 establishes the new pattern.
