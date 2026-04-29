# Phase 3: Live Game Tracking - Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 13 (5 NEW source/tests, 6 MODIFY, 2 secondary MODIFY)
**Analogs found:** 13 / 13 (every file has a strong same-codebase analog)

## File Classification

| New/Modified File | Status | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `stonereader/services/_global_hotkey.py` | NEW | service | event-driven (WM_HOTKEY → callback) | `stonereader/services/_watcher.py` | role-match (private `_*` service that wires a wx-frame-bound timer/event into a callback bus) |
| `stonereader/presenters/live_game.py` | NEW | presenter | event-driven (subscribes to GameTracker) + zone navigation | `stonereader/presenters/card_browser.py` (zone nav) + `stonereader/presenters/deck_manager.py` (custom `_format_item_speech`) | exact (zone presenter) + adds tracker subscription |
| `stonereader/views/live_game.py` | NEW | view | request-response (passive panel) | `stonereader/views/card_browser.py` and `stonereader/views/deck_manager.py` | exact (passive virtual ListCtrl panel pattern) |
| `tests/test_global_hotkey.py` | NEW | test | event-driven | `tests/test_services/test_tracker.py` | role-match (subscribe/dispatch/cleanup test for a service) |
| `tests/test_live_game_presenter.py` | NEW | test | event-driven + zone navigation | `tests/test_card_browser.py` + `tests/test_deck_manager.py` | exact (presenter under MockSpeechService) |
| `tests/test_services/test_engine_friendly_player.py` | NEW | test | request-response (synthetic packet stream) | `tests/test_services/test_engine.py::test_card_drawn_controller_reflects_log_controller` | exact (synthetic CreateGamePacket / TagChangePacket / FullEntityPacket sequence) |
| `tests/test_services/test_engine_lineage.py` | NEW | test | request-response (synthetic packet stream) | `tests/test_services/test_engine.py` (same pattern as above) | exact |
| `stonereader/services/_engine.py` | MODIFY | service | request-response (Packet → events) | itself (extend existing `_record_entity` / `_on_create_game` / `_block_subjects` bookkeeping) | self |
| `stonereader/models/game_state.py` | MAYBE MODIFY | model | data structure | itself (existing `Hero.hero_class: str = ""` default-empty pattern at line 24) | self |
| `stonereader/presenters/home.py` | MODIFY | presenter | data structure (constant) | itself (line 13 `MENU_ITEMS`) | self |
| `stonereader/app.py` | MODIFY | composition root | startup wiring | itself (existing `OnInit` pattern that instantiates presenter+panel+`nav.register_panel`, lines 394-437; existing tracker wiring at 377-392; existing `_on_close` at 343-353) | self |
| `tests/test_services/test_engine.py` | MODIFY | test | (tuple-shape carry-forward only) | itself (lines 26-30, 56-61) | self |
| `tests/test_services/test_parser.py` | MODIFY | test | (tuple-shape carry-forward only) | itself (line 31 `Player EntityID=2 PlayerID=1 …`) | self |

## Pattern Assignments

### `stonereader/services/_global_hotkey.py` (NEW — service, event-driven)

**Analog:** `stonereader/services/_watcher.py` (closest existing `_*` service that owns a wx-frame-bound resource and dispatches via callback)
**Why this analog:** Both wrap a Windows/wx resource that is bound to a `wx.Frame`, expose `start/stop`-style lifecycle that must be paired (`Bind`/`Unbind`, `RegisterHotKey`/`UnregisterHotKey`), and route events to callers via injected callbacks. Both follow the `_*` private-module convention from CONVENTIONS.md and never leak wx types into the engine layer.

**Imports + module docstring + logger pattern** (`_watcher.py:1-15`):
```python
"""Watch Power.log via wx.Timer (D-01) — tail bytes, decode lines, detect rotation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional

import wx

from stonereader.services._line_reader import _LineReader

logger = logging.getLogger(__name__)
```

**Class shape — wx-frame-bound service with start/stop lifecycle** (`_watcher.py:29-62`):
```python
class PowerLogWatcher:
    """Tail Power.log via a wx.Timer; emit lines via on_lines callback."""

    def __init__(
        self,
        path_provider: Callable[[], Optional[Path]],
        on_lines: Callable[[List[str]], None],
        on_reset: Callable[[], None],
    ) -> None:
        self._path_provider = path_provider
        self._on_lines = on_lines
        self._on_reset = on_reset
        self._timer: Optional[wx.Timer] = None
        ...

    def start(self, parent: "wx.EvtHandler") -> None:
        """Create and start the Timer parented on `parent`. Pitfall 9: call AFTER frame.Show()."""
        if self._timer is not None:
            return  # already started
        self._timer = wx.Timer(parent)
        parent.Bind(wx.EVT_TIMER, lambda evt: self._tick(), self._timer)
        self._timer.Start(POLL_INTERVAL_MS)

    def stop(self) -> None:
        """Stop the Timer cleanly. D-19: idempotent."""
        if self._timer is not None:
            self._timer.Stop()
            self._timer = None
```

**What to replicate:**
- Module docstring + `from __future__ import annotations` + `logging.getLogger(__name__)`.
- Constructor takes the wx frame + injected callbacks; stash internal state on `self._*`.
- Idempotent lifecycle: `register`/`clear_all` mirror `start`/`stop` (early-return if already in target state; `clear_all` safe to call on close).
- `Bind` once on the frame inside `__init__` (analog to `parent.Bind(wx.EVT_TIMER, ...)`); use `wx.EVT_HOTKEY` instead of `wx.EVT_TIMER`.
- Per-tick exception isolation pattern (`_watcher.py:63-68` `_tick` wraps `_do_tick` in try/except and calls `logger.exception("watcher tick failed")`) — apply identically to the hotkey dispatch callback (`_on_hotkey` wraps `callback()` in try/except and `logger.exception("global hotkey callback raised; ignoring")`).

**What to change:**
- Replace `wx.Timer` resource with `RegisterHotKey`/`UnregisterHotKey` resource pair; track registered IDs in `Dict[int, Callable[[], None]]` instead of a single `_timer` handle.
- Add `failed: List[str]` accumulator (announced once at startup per Pitfall 4 — see RESEARCH.md §"Pitfall 4").
- Use `_next_id = 1000` and increment per registration (Win32 ID space 0x0000–0xBFFF per RESEARCH.md §"Pattern 7").
- OR `0x4000` (`MOD_NOREPEAT`) into the modifier flags by default to prevent held-key flood (Pitfall 5).

---

### `stonereader/presenters/live_game.py` (NEW — presenter, event-driven + zone navigation)

**Analog (primary, zone navigation):** `stonereader/presenters/card_browser.py`
**Analog (secondary, custom row formatting):** `stonereader/presenters/deck_manager.py` (`_format_item_speech` override for D-08 format)
**Why this analog:** `CardBrowserPresenter` is the canonical 3-key reference for `ZoneNavigationMixin + BasePresenter` composition (line 14), `_init_navigation` at construction (line 34), `get_zone_items` per-zone dispatch (lines 39-42), `move_in_zone`/`jump_to_first`/`jump_to_last` overrides that re-emit `_notify_view` (lines 95-105), and the `set_on_state_changed` callback wiring (lines 73-77). `DeckManagerPresenter` adds the override pattern for custom per-row speech (`_format_item_speech` lines 57-66) which Live Game needs three of (one per zone per D-13/D-14/D-15).

**Imports + class declaration pattern** (`card_browser.py:1-14`):
```python
"""Card Browser presenter -- browse and search cards within a category."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService

_RESULTS_ZONE = "results"


class CardBrowserPresenter(ZoneNavigationMixin, BasePresenter):
```

**`__init__` + `_init_navigation` + view-callback fields** (`card_browser.py:22-37`):
```python
def __init__(
    self,
    speech: SpeechService,
    card_db: CardDatabase,
    category_label: str = "All Cards",
    card_class_filter: str | None = None,
) -> None:
    super().__init__(speech)
    self._card_db = card_db
    self._category_label = category_label
    self._filters = {"card_class": card_class_filter} if card_class_filter else None
    self._results: list[Card] = self._card_db.search_cards(filters=self._filters)
    self._init_navigation([_RESULTS_ZONE])
    self._on_state_changed: Callable[[list[Card], int], None] | None = None
```

**`get_zone_items` + `_notify_view` + nav-override pattern** (`card_browser.py:39-105`):
```python
def get_zone_items(self, zone_name: str) -> Sequence[Any]:
    if zone_name == _RESULTS_ZONE:
        return self._results
    return []

def _notify_view(self) -> None:
    if self._on_state_changed is not None:
        cursor = self._zone_cursors.get(_RESULTS_ZONE, 0)
        self._on_state_changed(self._results, cursor)

def move_in_zone(self, delta: int) -> None:
    super().move_in_zone(delta)
    self._notify_view()

def jump_to_first(self) -> None:
    super().jump_to_first()
    self._notify_view()
```

**`announce_entry` zone-entry speech (D-17 maps directly to this)** (`card_browser.py:61-71`):
```python
def announce_entry(self) -> None:
    """Announce on entering the card browser for this category."""
    count = len(self._results)
    cursor = self._zone_cursors.get(_RESULTS_ZONE, 0)
    if not self._results:
        self._speech.speak(f"{self._category_label}: no cards")
        return
    item = self._results[cursor]
    self._speech.speak(
        f"{self._category_label}, {self._format_item_speech(item, cursor + 1, count)}"
    )
```

**`get_key_map` pattern** (`card_browser.py:118-126`):
```python
def get_key_map(self) -> dict[str, Callable[[], None]]:
    return {
        "left": lambda: self.move_in_zone(-1),
        "right": lambda: self.move_in_zone(1),
        "down": self._read_detail_down,
        "up": self._read_detail_up,
        "home": self.jump_to_first,
        "end": self.jump_to_last,
    }
```

**Custom `_format_item_speech` override pattern** (`deck_manager.py:57-66`):
```python
def _format_item_speech(
    self, item: Any, position: int, total: int
) -> str:
    """Override for D-08: 'Name, Class, Format, N of M'."""
    if isinstance(item, DeckSummary):
        return (
            f"{item.name}, {item.hero_class}, {item.format}, "
            f"{position} of {total}"
        )
    return super()._format_item_speech(item, position, total)
```

**Subscriber subscribe/unsubscribe pattern** (must be added — `_tracker.py:90-103` is the contract):
```python
# In LiveGamePresenter.__init__:
tracker.subscribe(self._on_game_event)

# In LiveGamePresenter.cleanup:
self._tracker.unsubscribe(self._on_game_event)
```

**What to replicate:**
- Class declaration `class LiveGamePresenter(ZoneNavigationMixin, BasePresenter):` (MRO-correct order — mixin first, base second; matches `card_browser.py:14`, `deck_manager.py:17`, `home.py:16`).
- `_init_navigation([...])` with three zone names matching D-05 (`["remaining_deck", "opponent_hand", "opponent_played"]`).
- View-callback field `self._on_state_changed: Callable[..., None] | None = None`; setter `set_on_state_changed`; emit from `_notify_view`; override `move_in_zone`/`jump_to_first`/`jump_to_last` to call `_notify_view` after `super()`.
- `get_zone_items(zone_name)` dispatch on the zone-name string (one branch per zone returning a list/tuple).
- `_format_item_speech` override matching D-13/D-14/D-15 (see RESEARCH.md §"Pattern 6" for the exact format strings).
- `get_key_map()` returning the standard left/right/up/down/home/end set; down = detail inspection via `read_detail_lines` (mixin already provides this — `base.py:143-153`).
- Module-level zone-name constants (mirrors `card_browser.py:11` `_RESULTS_ZONE = "results"`).

**What to change:**
- Constructor accepts `tracker: GameTracker` + `db_conn: sqlite3.Connection` (DeckManager pattern — `deck_manager.py:20-25`) + `card_db: CardDatabase`. Subscribe in `__init__`; unsubscribe in `cleanup()`.
- Add `_on_game_event(event, state)` handler that **never calls `self._speech.speak`** (D-07 silence rule; RESEARCH.md §"Anti-Patterns to Avoid"). Only updates `self._current_state` and calls `_notify_view()`.
- Add `_run_auto_detection(state)` (D-10/D-11; RESEARCH.md §"Pattern 5") — reads `db.get_all_decks(self._db_conn)`, multiset-matches against revealed `state.player_deck`, caches result on `self._detected_deck_name`. Reset `_detection_attempted` on every `GameStarted` (Pitfall 6).
- Add `jump_to_zone(zone_name)` public method (RESEARCH.md §"Pattern 6 / Example 3"): zone label + total-count + first-row-read concatenation (D-17 format).
- Add `announce_deck_counts()` speak-only method (RESEARCH.md §"Example 4"): `f"{state.player_deck_count} left, opponent {state.opponent_deck_count}."`.
- Three custom rows in `_format_item_speech` (per zone), not one (DeckManager has one).

---

### `stonereader/views/live_game.py` (NEW — view, request-response/passive)

**Analog:** `stonereader/views/card_browser.py` (and `views/deck_manager.py` — near-identical shape)
**Why this analog:** Both are passive `wx.Panel` shells with `wx.WANTS_CHARS`, a `_*ListCtrl` virtual `wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER` widget that overrides `OnGetItemText` and `AcceptsFocus` (returns False so keyboard nav stays on the presenter key map per CLAUDE.md), and wire presenter callbacks via `set_on_state_changed`. The Live Game panel needs three list zones plus a title `wx.StaticText` for matchup/detected-deck display (RESEARCH.md §"Open Question 4"); the analog shows the canonical single-list shape, replicate it three times in one BoxSizer.

**Virtual ListCtrl pattern** (`card_browser.py:14-41`):
```python
class _CardListCtrl(wx.ListCtrl):
    """Virtual ListCtrl displaying card results.

    Visible to NVDA object navigation but kept out of Tab order via
    AcceptsFocus() so keyboard navigation stays on the presenter key map.
    """

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self.AppendColumn("Card", width=400)
        self._cards: list[Card] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_cards(self, cards: list[Card]) -> None:
        self._cards = cards
        self.SetItemCount(len(cards))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._cards):
            return ""
        card = self._cards[item]
        return f"{card.name} -- {card.cost} mana -- {card.card_type}"
```

**Panel constructor: sizer + label-before-control + presenter callback wiring** (`card_browser.py:44-74`):
```python
class CardBrowserPanel(wx.Panel):
    """Card Browser panel showing filtered card list with search."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: CardBrowserPresenter,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # MSAA label for card list
        results_label = wx.StaticText(self, label="Cards:")
        sizer.Add(results_label, 0, wx.ALL, 4)
        self._list_ctrl = _CardListCtrl(self)
        sizer.Add(self._list_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

        # Wire presenter callbacks
        presenter.set_on_state_changed(self._on_state_changed)

        # Initial visual state
        self._list_ctrl.set_cards(list(presenter.get_zone_items("results")))
```

**State-change callback that re-selects the cursor row** (`card_browser.py:76-79`):
```python
def _on_state_changed(self, results: list[Card], cursor: int) -> None:
    self._list_ctrl.set_cards(results)
    if results:
        self._list_ctrl.Select(cursor)
```

**What to replicate:**
- `style=wx.WANTS_CHARS` on the outer panel so EVT_CHAR_HOOK still routes via InputLayer.
- Per-zone virtual `_*ListCtrl` (one for each of `remaining_deck`, `opponent_hand`, `opponent_played`) with `AcceptsFocus() -> False` and `OnGetItemText` returning a brief textual representation (different format per zone — see D-13/D-14/D-15).
- StaticText label immediately before each ListCtrl in the sizer (MSAA sibling-order labelling per CLAUDE.md "Semantic HTML before ARIA").
- `presenter.set_on_state_changed(self._on_state_changed)` wiring in `__init__`; the callback re-selects the current cursor row to fix Pitfall 3 (cursor-jump on re-render — RESEARCH.md §"Pitfall 3").

**What to change:**
- Add a top-of-panel `wx.StaticText` for matchup + detected-deck name (e.g. `"Mage vs Warrior — Reno Quest Mage"`); update from a separate presenter callback `set_on_title_changed` (RESEARCH.md §"Open Question 4 — recommendation: panel-level StaticText, not MainWindow.SetStatusText").
- Three sub-list-ctrl widgets (remaining_deck / opponent_hand / opponent_played); each with its own label + `set_*` setter on the panel; presenter's `_on_state_changed` callback signature carries `(zone_name, items, cursor)` rather than the single-zone `(results, cursor)` from `card_browser.py`.
- No search dialog; no context menu (Live Game is read-only). Drop `set_on_request_search` and `_on_context_menu` paths entirely.
- No text mode plumbing — `bind_text_mode` from `views/base.py:15-18` is unnecessary because there are no TextCtrls (CONTEXT.md §"Existing Code (required reading)" — `views/base.py` text mode "can be skipped").

---

### `tests/test_global_hotkey.py` (NEW — test, event-driven)

**Analog:** `tests/test_services/test_tracker.py`
**Why this analog:** Both test a service that wires a callback bus to a wx-bound resource. Test patterns are: subscribe/dispatch, exception isolation, idempotent start/stop. The tracker tests use `wx.App() / wx.Frame(None)` for the wx-required cases (`test_tracker.py:82-103`) and pure-Python fakes for the rest — exactly what `_global_hotkey` needs.

**`pytest.importorskip("wx") + wx.App() + frame` pattern for wx-bound tests** (`test_tracker.py:82-103`):
```python
def test_start_stop_clean():
    wx = pytest.importorskip("wx")
    from stonereader.services import GameTracker

    app = wx.App()
    try:
        frame = wx.Frame(None)
        try:
            tracker = GameTracker()
            tracker.start(frame)
            assert tracker._started is True

            tracker.stop()
            assert tracker._started is False

            # stop() is idempotent — second call must not raise.
            tracker.stop()
            assert tracker._started is False
        finally:
            frame.Destroy()
    finally:
        app.Destroy()
```

**Subscribe / dispatch / exception-isolation pattern** (`test_tracker.py:35-62`):
```python
def test_subscriber_exception_does_not_break_others(caplog):
    from stonereader.services import GameStarted, GameTracker

    tracker = GameTracker()
    good_called = []

    def bad(event, state):
        raise RuntimeError("boom")

    def good(event, state):
        good_called.append(event)

    tracker.subscribe(bad)
    tracker.subscribe(good)
    ...
    with caplog.at_level(logging.ERROR):
        tracker._dispatch(event, None)

    assert len(good_called) == 1, "good subscriber must still receive event after bad raises"
    assert any("subscriber raised" in rec.message for rec in caplog.records)
```

**What to replicate:**
- `pytest.importorskip("wx")` + `wx.App()` + `wx.Frame(None)` scaffolding inside a `try/finally` that calls `frame.Destroy()` and `app.Destroy()` for any test that constructs `GlobalHotkeyService(frame)`.
- Test idempotency of `clear_all` — call twice, second is no-op (mirrors `tracker.stop()` test at line 96-99).
- Use `caplog.at_level(logging.WARNING)` to verify the "RegisterHotKey failed" log line per RESEARCH.md §"Pitfall 4".

**What to change:**
- Don't actually register a real OS hotkey in tests — monkeypatch `wx.Frame.RegisterHotKey` to return a scriptable bool (or use a fake frame). RESEARCH.md §"Wave 0 Gaps" line 957 explicitly recommends "Mock `wx.Frame.RegisterHotKey` to return scriptable bool; assert callback dispatch."
- Cover three cases per RESEARCH.md §"Validation Architecture":
  - `test_register_returns_status` — register returns `True` on success and `False` on conflict; `failed` list accumulates labels.
  - `test_browse_open_dispatch` — `_on_hotkey(event)` looks up the callback by id and invokes it.
  - `test_clear_all_idempotent` — `clear_all()` unregisters every chord and is safe to call twice.

---

### `tests/test_live_game_presenter.py` (NEW — test, event-driven + zone navigation)

**Analog:** `tests/test_card_browser.py` (zone navigation + key-map + announce_entry pattern) and `tests/test_deck_manager.py` (presenter constructed against a sqlite connection)
**Why this analog:** `test_card_browser.py` is the canonical example of presenter-under-MockSpeechService — every test instantiates the presenter, drives it via `key_map["right"]()` or method calls, asserts on `speech.last_speech`. `test_deck_manager.py` adds the in-memory sqlite construction pattern (`_make_db(tmp_path)`) that auto-detection tests will need.

**MockSpeechService import + presenter test pattern** (`test_card_browser.py:1-9, 69-77`):
```python
from tests.conftest import MockSpeechService
from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.card_browser import CardBrowserPresenter

def test_search_with_query_announces_result_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("fire")

    assert "1 result" in speech.last_speech
```

**Driving presenter via `get_key_map()` returned dict** (`test_card_browser.py:140-150`):
```python
def test_right_arrow_announces_next_card():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["right"]()

    # Initial cursor is 0 (Arcane Intellect), right goes to 1 (Fireball)
    assert "Fireball" in speech.last_speech
    assert "2 of 4" in speech.last_speech
```

**View-callback assertion pattern** (`test_card_browser.py:241-254`):
```python
def test_view_callback_fires_on_search():
    ...
    received: list[tuple[int, int]] = []

    def on_state_changed(results: list[Card], cursor: int) -> None:
        received.append((len(results), cursor))

    presenter.set_on_state_changed(on_state_changed)
    presenter.search("fire")

    assert received == [(1, 0)]
```

**SQLite construction for detection tests** (`test_deck_manager.py:14-31`):
```python
def _make_db(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    return conn

def _seed_decks(conn: sqlite3.Connection) -> None:
    """Insert test decks. Oldest first so 'Aggro Paladin' is newest."""
    save_deck(conn, "Control Mage", "MAGE", "Standard", "AAECAf0EAA==")
    ...
```

**What to replicate:**
- Top-of-file `from tests.conftest import MockSpeechService` (the conftest already defines MockSpeechService at `tests/conftest.py:8-22` — no new fixture needed).
- One assertion per test on `speech.last_speech` or `speech.spoken` for speech expectations; use `received` list for view-callback expectations (`test_card_browser.py:241-254` pattern).
- `tmp_path` + `_make_db(tmp_path)` for sqlite-backed detection tests; reuse `tests/test_deck_manager.py::_seed_decks` shape (uses `save_deck` from `stonereader/db.py`).
- Drive zone navigation via `key_map = presenter.get_key_map()` then `key_map["right"]()` etc., not direct method calls — exercises the public surface.

**What to change:**
- Construct presenter with a **MockGameTracker** (RESEARCH.md §"Wave 0 Gaps" line 957: "exposes `subscribe`/`unsubscribe`/`current_state` without needing real wx + hslog. Add to `tests/conftest.py` or local conftest"). Drive `_on_game_event` directly with synthetic `(event, state)` tuples — don't try to feed real Power.log lines.
- Cover all rows from RESEARCH.md §"Phase Requirements → Test Map" for `test_live_game_presenter.py` (LIVE-01, LIVE-02 sort + drawn-to-zero, LIVE-04, LIVE-05, LIVE-06, LIVE-07, LIVE-08 detection 0/1/2+, D-07 silence, D-08 baseline, D-09 lifecycle silence).
- Assert no speech during `_on_game_event` (D-07): `assert speech.spoken == []` after firing a non-lifecycle event.
- Assert `_detection_attempted` resets on second `GameStarted` (Pitfall 6).

---

### `tests/test_services/test_engine_friendly_player.py` (NEW — test, request-response/synthetic packet stream)

**Analog:** `tests/test_services/test_engine.py::test_card_drawn_controller_reflects_log_controller` (lines 42-82) — exact same shape (synthetic CreateGamePacket → FullEntityPacket → TagChangePacket sequence asserting on a single emitted event).
**Why this analog:** Same packet types, same engine API, same assertion style. The existing test even documents WR-02 (line 47-51) and is explicitly carry-forward — RESEARCH.md §"Phase Requirements → Test Map" line 938 says this test "still passes (no regression)".

**Synthetic packet stream pattern** (`test_engine.py:42-82`):
```python
def test_card_drawn_controller_reflects_log_controller():
    """CardDrawn.controller is the raw CONTROLLER tag value from the log.

    WR-02: _friendly_player_id defaults to 1, so when the local player is
    assigned CONTROLLER=2 by the server (coin-flip), their CardDrawn events
    will show controller=2 — the engine currently cannot distinguish local
    from opponent in that scenario.
    """
    engine = GameEngine()
    engine.apply(
        CreateGamePacket(
            packet_id=0,
            game_entity_id=1,
            players=((2, "LocalPlayer", 144115198130930503, 1), (3, "Opponent", 144115198130930504, 2)),
        )
    )
    engine.apply(
        FullEntityPacket(
            packet_id=1,
            entity_id=10,
            card_id="CS2_023",
            tags={"CONTROLLER": 2, "ZONE": 0},
        )
    )
    events = engine.apply(
        TagChangePacket(packet_id=2, entity_id=10, tag="ZONE", value=3)
    )
    drawn = [e for e in events if isinstance(e, CardDrawn)]
    assert len(drawn) == 1, "Expected exactly one CardDrawn event"
    assert drawn[0].controller == 2, ...
```

**Captured-fixture integration pattern** (`test_engine.py:85-95`):
```python
def test_mid_game_fixture_emits_expected_events(power_log_fixture):
    path = power_log_fixture("mid_game.log")  # skips if absent
    parser = Parser()
    engine = GameEngine()
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        for pkt in parser.feed_line(line):
            events.extend(engine.apply(pkt))
    assert any(isinstance(e, GameStarted) for e in events), (
        "mid_game.log must contain CREATE_GAME and emit GameStarted"
    )
```

**What to replicate:**
- File header + import pattern (`pytest.importorskip("stonereader.services._engine")` then import engine + events + packets).
- Synthetic packet stream — assemble `CreateGamePacket`, `FullEntityPacket`, `TagChangePacket`, `ShowEntityPacket` directly; don't feed log lines except for fixture tests.
- Use `power_log_fixture` fixture (in `tests/test_services/conftest.py:47-61`) for captured-fixture cases.

**What to change:**
- Cover the four cases from RESEARCH.md §"Validation Architecture" lines 935-939:
  - `test_local_is_player_2` — synthetic CreateGame where AI heuristic flips `_friendly_player_id` to 2.
  - `test_ai_heuristic` — `lo == 0` is opponent, `lo != 0` is friendly.
  - `test_show_entity_fallback` — both players have `lo != 0`; first SHOW_ENTITY into HAND determines the friendly player.
  - `test_captured_fixtures_resolve` — all 4 fixtures resolve `friendly_player_id == 1` (regression lock).
- **Important:** the existing test uses `players=((2, "LocalPlayer", 144115198130930503, 1), …)` — **a 4-tuple**. Per RESEARCH.md §"Pattern 1" (line 263), the parser change retains `player_id` and the tuple becomes 5-element `(entity_id, player_id, name, hi, lo)`. New tests must use the new 5-tuple shape; existing test (`test_card_drawn_controller_reflects_log_controller`) needs the carry-forward update.

---

### `tests/test_services/test_engine_lineage.py` (NEW — test, request-response/synthetic packet stream)

**Analog:** Same as `test_engine_friendly_player.py` — `tests/test_services/test_engine.py` (synthetic packet stream + captured-fixture pattern). RESEARCH.md §"Pattern 2" provides the exact engine-side change to test against.

**Code excerpt — same as above** (`test_engine.py:42-95`).

**What to replicate:** Same synthetic packet stream + `power_log_fixture` pattern.

**What to change:**
- Cover the four cases from RESEARCH.md §"Validation Architecture" lines 940-943:
  - `test_lineage_recorded` — synthetic packet stream: BLOCK_START POWER subject=Cabal, FULL_ENTITY in HAND on opposite controller → entity has `creation_lineage="Cabal Shadow Priest"`.
  - `test_no_lineage_for_normal_draw` — BLOCK_START POWER + FULL_ENTITY in DECK (not HAND) → no lineage. Or normal turn-start draw (TAG_CHANGE outside POWER block) → no lineage.
  - `test_no_lineage_for_friendly` — same generation, friendly entity → no lineage.
  - `test_reconnect_drops_lineage` (integration) — feed `tests/fixtures/log/reconnect.log` and assert lineage is missing for any opponent-hand entity created in the second CREATE_GAME (Pitfall 7).
- Each test instantiates `GameEngine(card_db=...)` with a stub `CardDatabase` that knows about Cabal Shadow Priest / Wand of Disintegration — see `tests/test_card_browser.py::make_card_db` and `make_card` helpers (lines 13-66) for the exact pattern.

---

### `stonereader/services/_engine.py` (MODIFY — service)

**Analog:** itself — the modifications extend existing, well-established bookkeeping (`_block_stack`, `_block_subjects`, `_record_entity`, `_handle_zone_change`).

**WR-02 stub site to replace** (`_engine.py:77-85`):
```python
# Default friendly player_id is 1.
# TODO(WR-02): This stub is incorrect for the ~50 % of games where the
# local player is assigned CONTROLLER=2 by the server coin-flip.  To
# refine it we need the local player's BattleTag hi/lo (from the OS
# account APIs or a Hearthstone startup log line) and compare against
# CreateGamePacket.players hi/lo fields.  Until that data is wired in,
# card draw / play events for local-player-as-entity-2 games will have
# their controller attribution inverted.  See WR-02 in 02-REVIEW.md.
self._friendly_player_id = 1
```

**Existing CREATE_GAME players-iteration pattern** (`_engine.py:175-177` — needs the 5-tuple update):
```python
# Initialize entities for the GameEntity and Players
self._record_entity(p.game_entity_id, "", p.initial_tags)
for entity_id, name, _hi, _lo in p.players:
    self._record_entity(entity_id, "", {})
    self._entities[entity_id]["player_name"] = name
```

**Existing block-stack bookkeeping (extension target for D-19 lineage)** (`_engine.py:67-68, 371-392`):
```python
self._block_stack: List[str] = []  # block types currently open
self._block_subjects: List[int] = []  # entity_ids of current blocks

def _on_block_start(self, p: BlockStartPacket) -> List[GameEvent]:
    self._block_stack.append(p.block_type)
    self._block_subjects.append(p.entity_id)
    ...

def _on_block_end(self, _p: BlockEndPacket) -> List[GameEvent]:
    if self._block_stack:
        self._block_stack.pop()
    if self._block_subjects:
        self._block_subjects.pop()
    return []
```

**Existing `_record_entity` (lineage hook target)** (`_engine.py:139-144`):
```python
def _record_entity(self, eid: int, card_id: str, tags: Dict[str, int]) -> None:
    ent = self._entities.setdefault(eid, {})
    if card_id:
        ent["card_id"] = card_id
    for k, v in tags.items():
        ent[k] = v
```

**Existing `_refresh_state` (opponent-hand reconstruction target)** (`_engine.py:425-435`):
```python
def _refresh_state(self) -> None:
    """Rebuild the published snapshot from internal bookkeeping."""
    if self._current_state is None:
        return
    self._current_state = dataclasses.replace(
        self._current_state,
        player_played=tuple(self._player_played),
        opponent_played=tuple(self._opponent_played),
        player_drawn=tuple(self._player_drawn),
        opponent_drawn=tuple(self._opponent_drawn),
    )
```

**What to replicate:** All existing engine patterns — `dataclasses.replace` for frozen state updates, `try/except` per-packet wrapping in `apply` (line 109-129), `logger.exception(...)` for non-fatal errors.

**What to change (per CONTEXT.md D-18, D-19, RESEARCH.md §"Pattern 1", §"Pattern 2"):**
- **WR-02 fix (line 85):** replace `self._friendly_player_id = 1` constant with AI-heuristic resolution at CREATE_GAME (`lo == 0` is opponent, `lo != 0` is friendly) + SHOW_ENTITY-into-HAND fallback for both-real-player games. May briefly be `None` between CREATE_GAME and resolution; default to `1` and re-bucket on resolution per RESEARCH.md §"Pitfall 1".
- **Player tuple change (line 175):** update to 5-tuple destructure `for entity_id, player_id, name, _hi, _lo in p.players:` after `_packets.py` change. Engine uses `player_id` for the AI-heuristic mapping.
- **D-19 lineage (line 139):** extend `_record_entity` per RESEARCH.md §"Pattern 2" excerpt — when inside POWER block AND new entity ends up in HAND with controller != friendly, look up `_block_subjects[-1]` card and stash `ent["creation_lineage"] = subject_card.name` in the bookkeeping dict.
- **Opponent-hand reconstruction (line 425):** RESEARCH.md §"Pattern 2" line 328 explicitly notes "the engine never reconstructs hand `GameEntity` snapshots. Phase 3 must add opponent-hand `GameEntity` reconstruction in `_refresh_state` so the panel zone has data to display." Add a list comprehension over `self._entities` for any entity with `ZONE == HAND` and `CONTROLLER != self._friendly_player_id`, building frozen `GameEntity` snapshots with `creation_lineage` populated from the bookkeeping dict.

---

### `stonereader/models/game_state.py` (MAYBE MODIFY — model)

**Analog:** itself — the existing `Hero.hero_class: str = ""` (line 24) and `GameEntity.drawn_turn: int = -1` (line 47) are the canonical "additive optional field with a sentinel default" patterns.

**Existing additive-default pattern on a frozen dataclass** (`game_state.py:14-25`):
```python
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
```

**Existing additive default on `GameEntity`** (`game_state.py:27-48`):
```python
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
```

**What to replicate:** Comment style (`# NEW (Phase 3): …`), default-empty/sentinel value, frozen-dataclass invariant.

**What to change (planner picks per CONTEXT.md D-19 + RESEARCH.md §"Pattern 2 / Storage choice"):**
- **Option A (recommended in RESEARCH.md):** add `creation_lineage: str = ""` to `GameEntity` (after `drawn_turn`). Type-checked; clean presenter access via `entity.creation_lineage`.
- **Option B:** use existing `tags: Dict[str, Any]` (line 44) — store under key `"creation_lineage"`. No schema change but untyped (CLAUDE.md frowns on this — see CONTEXT.md line 142 "untyped — bug-prone").
- **Option C:** keep all lineage state inside the engine (`_creation_lineage: Dict[int, str]`) and expose via `GameTracker` accessor — no `GameEntity` change.

If Option A: also reflect that field in the planner's "what's exposed in `_refresh_state`" diff (the engine constructs `GameEntity` instances when reconstructing opponent_hand — see preceding row).

---

### `stonereader/presenters/home.py` (MODIFY — presenter)

**Analog:** itself (line 13).

**Code excerpt** (`home.py:11-13`):
```python
_MENU_ZONE = "menu"

# Menu items -- order matches UI-SPEC home screen ListBox
MENU_ITEMS = ["Card Library", "Deck Manager", "Import Deck"]
```

**What to replicate:** Just the constant.

**What to change:** Add `"Live Game"` to the list. Order is planner's call — RESEARCH.md §"Open Question 5" says "land on Remaining Deck zone immediately" when invoked from home menu, so the home selection callback in `app.py` must call `nav.show_panel("Live Game")` and then `live_presenter.jump_to_zone("remaining_deck")` (mirrors the existing card-library `_on_category_select` callback at `app.py:445-462`).

---

### `stonereader/app.py` (MODIFY — composition root)

**Analog:** itself — `OnInit` already follows a stable pattern of (presenter → panel → `nav.register_panel`) blocks separated by `# --- Section ---` comments.

**Existing per-feature wiring block pattern** (`app.py:412-418` — DeckManager case):
```python
# --- Deck Manager ---
from stonereader.presenters.deck_manager import DeckManagerPresenter
from stonereader.views.deck_manager import DeckManagerPanel

deck_presenter = DeckManagerPresenter(speech, db_conn, card_db)
deck_panel = DeckManagerPanel(self._frame, deck_presenter)
nav.register_panel("Deck Manager", deck_panel, deck_presenter, deck_panel)
```

**Existing tracker construction + stash + start-after-Show pattern** (`app.py:377-501`):
```python
from stonereader.services import GameTracker
...
self._tracker = GameTracker(card_db=card_db)
# Stash the tracker on the frame so MainWindow._on_close can stop it.
self._frame._tracker = self._tracker  # type: ignore[attr-defined]
...
self._frame.Show()

# Start tracker AFTER frame.Show() (Pitfall 9: Timer must not fire
# before the message loop is wired up to the visible frame).
try:
    self._tracker.start(parent=self._frame)
except Exception:
    logging.getLogger(__name__).exception(
        "tracker.start() failed; tracker disabled"
    )
```

**Existing `_on_close` pattern that calls `tracker.stop()` before `Destroy`** (`app.py:343-353`):
```python
def _on_close(self, event: wx.CloseEvent) -> None:
    # Stop the GameTracker (Phase 2) cleanly so the wx.Timer reference is
    # cleared before the frame is destroyed (D-19, T-2-LIFECYCLE).
    tracker = getattr(self, "_tracker", None)
    if tracker is not None:
        try:
            tracker.stop()
        except Exception:
            logging.getLogger(__name__).exception("tracker.stop() failed")
    self._db_conn.close()
    self.Destroy()
```

**Existing home-menu select callback shape** (`app.py:442-462`):
```python
home_presenter.set_on_select(lambda name: nav.show_panel(name))

# Card Library category selection -> create and show card browser
def _on_category_select(category_name: str) -> None:
    from stonereader.presenters.card_browser import CardBrowserPresenter
    ...
```

**What to replicate:**
- New `# --- Live Game ---` block after `# --- Import Deck ---` (around line 437): import presenter + panel, instantiate, `nav.register_panel("Live Game", ...)`. Mirrors the DeckManager block exactly.
- Stash live-game presenter on the frame (`self._frame._live_presenter = live_presenter # type: ignore[attr-defined]`) the same way the tracker is stashed at line 392, so `_on_close` can call `live_presenter.cleanup()` (which unsubscribes from the tracker) before `tracker.stop()`.
- Subscribe to tracker via `tracker.subscribe(live_presenter._on_game_event)` inside `LiveGamePresenter.__init__` (presenter does this itself; not in `OnInit`) — see CONTEXT.md line 140 "subscribers in its constructor and unsubscribes in `cleanup()`".
- Hotkey wiring goes after the existing `self._frame.Show()` and before `self._tracker.start(parent=self._frame)` — instantiate `GlobalHotkeyService(self._frame)`, register all chords, announce failures (RESEARCH.md §"Example 2").

**What to change:**
- Extend `_on_close` (line 343) to also call `self._hotkeys.clear_all()` and `self._live_presenter.cleanup()` — same try/except + log pattern as `tracker.stop()`. RESEARCH.md §"Runtime State Inventory" line 687 explicitly requires this ordering (clear hotkeys BEFORE Destroy).
- Extend home `_on_select` callback to dispatch to `nav.show_panel("Live Game")` + `live_presenter.jump_to_zone("remaining_deck")` for the `"Live Game"` entry (matches the existing `_on_category_select` shape at lines 445-462).

---

### `tests/test_services/test_engine.py` (CARRY-FORWARD MODIFY — test)

**Analog:** itself.

**Existing tuple-shape callsites** (`test_engine.py:26-29` and `:56-61`):
```python
engine.apply(
    CreateGamePacket(
        packet_id=0,
        game_entity_id=1,
        players=((2, "P1", 1, 1), (3, "P2", 2, 2)),
    )
)
...
players=((2, "LocalPlayer", 144115198130930503, 1), (3, "Opponent", 144115198130930504, 2)),
```

**What to change:** Update `players=((entity_id, name, hi, lo), …)` to the 5-tuple `players=((entity_id, player_id, name, hi, lo), …)` after `_packets.py:CreateGamePacket.players` is updated to retain `player_id`. RESEARCH.md §"Pattern 1" line 263: "small breaking change to `CreateGamePacket` that requires updating engine code and the existing engine tests in `tests/test_services/test_engine.py`".

---

### `tests/test_services/test_parser.py` (CARRY-FORWARD MODIFY — test)

**Analog:** itself.

**Existing parser CREATE_GAME emit test** (`test_parser.py:20-36`):
```python
def test_translates_create_game_packet():
    """A minimal CREATE_GAME sequence should emit at least one CreateGamePacket."""
    from stonereader.services._packets import CreateGamePacket
    from stonereader.services._parser import Parser

    parser = Parser()
    emitted: list = []
    for line in [
        "D 13:00:00.0000000 GameState.DebugPrintPower() - CREATE_GAME",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     GameEntity EntityID=1",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]",
        "D 13:00:00.0000000 GameState.DebugPrintPower() -     Player EntityID=3 PlayerID=2 GameAccountId=[hi=2 lo=2]",
    ]:
        emitted.extend(parser.feed_line(line))
    assert any(isinstance(p, CreateGamePacket) for p in emitted), ...
```

**What to change:** Add a positive assertion that the emitted `CreateGamePacket.players` tuple now contains `player_id` (e.g. `assert emitted[0].players[0] == (2, 1, "P1", 1, 1)` matching the 5-tuple shape).

---

## Shared Patterns

### Frozen-dataclass mutation rule
**Source:** `stonereader/services/_engine.py:222, 228, 355, 429`
**Apply to:** All engine extensions (D-19 lineage, D-18 friendly_player resolution, opponent-hand reconstruction)
```python
# Engine never mutates GameState — always rebuilds via dataclasses.replace
self._current_state = dataclasses.replace(self._current_state, turn=p.value)
self._current_state = dataclasses.replace(
    self._current_state,
    player_played=tuple(self._player_played),
    opponent_played=tuple(self._opponent_played),
    ...
)
```
**CLAUDE.md invariant:** "Frozen dataclasses for all game state — never mutate, construct new instances".

### Subscriber callback contract (Phase 2 D-02)
**Source:** `stonereader/services/_tracker.py:90-103, 171-179`
**Apply to:** `LiveGamePresenter._on_game_event`
```python
SubscriberCallback = Callable[[GameEvent, Optional[GameState]], None]

# Subscribers are called SYNCHRONOUSLY on the GUI thread.
# One subscriber raising will not prevent others from receiving the event.
def subscribe(self, callback: SubscriberCallback) -> None:
    if callback not in self._subscribers:
        self._subscribers.append(callback)

def unsubscribe(self, callback: SubscriberCallback) -> None:
    if callback in self._subscribers:
        self._subscribers.remove(callback)
```
**Implication for Live Game presenter:** subscribe in `__init__`, unsubscribe in `cleanup()`. Don't block in `_on_game_event` (no slow IO, no `wx.MessageBox`). RESEARCH.md §"Anti-Patterns to Avoid" lines 657-659.

### Speech-only-from-presenter rule
**Source:** `CLAUDE.md` ("Views never call SpeechService directly — only presenters call `self._speech`") and `stonereader/presenters/base.py:21-25`
**Apply to:** Both `LiveGamePresenter` and `LiveGamePanel`
```python
# stonereader/presenters/base.py
class BasePresenter:
    def __init__(self, speech: SpeechService) -> None:
        self._speech = speech

    def announce(self, text: str) -> None:
        self._speech.speak(text)
```
**Implication:** `LiveGamePanel` must not import `SpeechService` or call `speak`. All speech (zone entry, hotkey-triggered) routes through presenter methods.

### Silent-during-arrow-read rule (D-07)
**Source:** RESEARCH.md §"Pattern 3" lines 393-394, §"Anti-Patterns to Avoid" line 657
**Apply to:** `LiveGamePresenter._on_game_event` (only)
```python
# CORRECT: never speak from event handler
def _on_game_event(self, event: GameEvent, state: Optional[GameState]) -> None:
    self._current_state = state
    self._notify_view()    # silent re-render

# WRONG: violates D-07
def _on_game_event(self, event, state):
    self._speech.speak("Card drawn!")    # NEVER do this
```
**Test lock:** RESEARCH.md §"Validation Architecture" line 944 — `test_silent_during_event` asserts `speech.spoken == []` after firing a non-lifecycle event.

### Per-packet exception isolation in engine
**Source:** `stonereader/services/_engine.py:106-129`
**Apply to:** All new engine handlers (lineage, friendly-player resolution)
```python
def apply(self, packet: Packet) -> List[GameEvent]:
    events: List[GameEvent] = []
    try:
        ...
    except Exception:
        # D-04 / Pitfall 3: never let one packet kill the engine
        logger.exception("engine apply failed for %s", type(packet).__name__)
    return events
```
**Implication:** New lineage / friendly-player code paths inside `_record_entity`, `_on_create_game`, `_on_show_entity` already benefit from this top-level catch. Don't add nested try/except inside individual handlers unless a specific failure must be ignored more granularly.

### MockSpeechService test fixture
**Source:** `tests/conftest.py:8-22`
**Apply to:** `tests/test_live_game_presenter.py`
```python
class MockSpeechService(SpeechService):
    """SpeechService that captures speech output for testing."""

    def __init__(self) -> None:
        self._use_stdout = True
        self._output = None
        self.spoken: list[tuple[str, bool]] = []

    def speak(self, text: str, interrupt: bool = True) -> None:
        self.spoken.append((text, interrupt))

    @property
    def last_speech(self) -> str:
        return self.spoken[-1][0] if self.spoken else ""
```
**Implication:** `from tests.conftest import MockSpeechService` — already exported. No new mock needed for speech. **New mock to add (per RESEARCH.md §"Wave 0 Gaps" line 957):** a `MockGameTracker` exposing `subscribe`/`unsubscribe`/`current_state` — add to `tests/conftest.py` or a phase-local conftest.

### `pytest.importorskip("wx")` for wx-bound tests
**Source:** `tests/test_services/test_tracker.py:83`
**Apply to:** `tests/test_global_hotkey.py` and any `app.py` integration test
```python
def test_start_stop_clean():
    wx = pytest.importorskip("wx")
    ...
```
**Implication:** Pure-presenter tests don't need `wx`. Only tests that construct a `wx.Frame` (e.g. `GlobalHotkeyService(frame)`) need the `importorskip`.

### Captured-fixture skip pattern
**Source:** `tests/test_services/conftest.py:47-61`
**Apply to:** `tests/test_services/test_engine_friendly_player.py::test_captured_fixtures_resolve` and `tests/test_services/test_engine_lineage.py::test_reconnect_drops_lineage`
```python
@pytest.fixture
def power_log_fixture():
    def _load(name: str) -> Path:
        path = FIXTURE_DIR / name
        if not path.exists():
            pytest.skip(f"fixture not yet captured: {name} (Wave 5 task)")
        return path
    return _load
```
**Implication:** Fixture-dependent tests automatically skip on dev machines without captures. The 4 fixtures (`match_start.log`, `mid_game.log`, `game_end.log`, `reconnect.log`) are present per RESEARCH.md line 1007.

### Module + service naming convention
**Source:** `.planning/codebase/CONVENTIONS.md` (`_*` prefix for private services modules)
**Apply to:** `stonereader/services/_global_hotkey.py`
**Implication:** Underscore prefix mirrors `_engine.py`, `_watcher.py`, `_tracker.py`, `_parser.py`. The public surface re-exports through `services/__init__.py:21-37` only if other modules need to import the service by class name; otherwise it stays private (Phase 3 only `app.py` instantiates it, so re-export is optional).

---

## No Analog Found

None. Every Phase 3 file maps cleanly onto an existing analog in the codebase or onto itself for additive changes. This is the expected outcome for a phase that explicitly rests on Phase 1 (zone navigation, panel-swap, MENU_ITEMS) and Phase 2 (engine, tracker, packets, fixtures) infrastructure.

## Metadata

**Analog search scope:** `stonereader/`, `tests/`, `tests/test_services/` (read-only).
**Files scanned:** 18 (engine, tracker, watcher, packets, services init, app, presenters/{base, home, card_browser, deck_manager}, views/{base, card_browser, deck_manager}, models/game_state, tests/{conftest, test_card_browser, test_deck_manager}, tests/test_services/{conftest, test_engine, test_parser, test_tracker}).
**Pattern extraction date:** 2026-04-26
