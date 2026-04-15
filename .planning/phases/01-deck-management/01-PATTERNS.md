# Phase 1: Deck Management - Pattern Map

**Mapped:** 2026-04-15
**Files analyzed:** 19 (new/modified)
**Analogs found:** 17 / 19

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `stonereader/presenters/deck_manager.py` | presenter | CRUD | `stonereader/presenters/card_browser.py` | exact |
| `stonereader/presenters/deck_contents.py` | presenter | request-response | `stonereader/presenters/card_browser.py` | exact |
| `stonereader/presenters/import_deck.py` | presenter | request-response | `stonereader/presenters/card_browser.py` | role-match |
| `stonereader/presenters/home.py` | presenter | request-response | `stonereader/presenters/card_browser.py` | role-match |
| `stonereader/views/deck_manager.py` | view | request-response | `stonereader/views/card_browser.py` | exact |
| `stonereader/views/deck_contents.py` | view | request-response | `stonereader/views/card_browser.py` | exact |
| `stonereader/views/import_deck.py` | view | request-response | `stonereader/views/card_browser.py` | role-match |
| `stonereader/views/home.py` | view | request-response | `stonereader/views/card_browser.py` | role-match |
| `stonereader/models/deck.py` (modify) | model | transform | `stonereader/models/deck.py` | self |
| `stonereader/app.py` (modify) | infrastructure | request-response | `stonereader/app.py` | self |
| `stonereader/db.py` (modify) | service | CRUD | `stonereader/db.py` | self |
| `stonereader/input_layer.py` (modify) | infrastructure | event-driven | `stonereader/input_layer.py` | self |
| `stonereader/models/__init__.py` (modify) | config | N/A | `stonereader/models/__init__.py` | self |
| `tests/test_deck_manager.py` | test | N/A | `tests/test_card_browser.py` | exact |
| `tests/test_deck_contents.py` | test | N/A | `tests/test_card_browser.py` | exact |
| `tests/test_import_deck.py` | test | N/A | `tests/test_card_browser.py` | role-match |
| `tests/test_home.py` | test | N/A | `tests/test_zone_navigation.py` | role-match |
| `tests/test_navigation.py` | test | N/A | `tests/test_input_layer.py` | role-match |
| `tests/test_db.py` (extend) | test | N/A | `tests/test_db.py` | self |

## Pattern Assignments

### `stonereader/presenters/deck_manager.py` (presenter, CRUD)

**Analog:** `stonereader/presenters/card_browser.py`

**Imports pattern** (lines 1-9):
```python
"""Card Library presenter — search and browse the card database."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService
```

**Adapt to:**
```python
"""Deck Manager presenter — browse, delete, and export saved decks."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Sequence

from stonereader.models.deck import DeckSummary
from stonereader.models.card import CardDatabase
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService
from stonereader.db import get_all_decks, delete_deck
```

**Class declaration pattern** (lines 15-26):
```python
class CardBrowserPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages search state and navigation for the Card Library tab."""

    def __init__(self, speech: SpeechService, card_db: CardDatabase) -> None:
        super().__init__(speech)
        self._card_db = card_db
        self._results: list[Card] = sorted(
            card_db.collectible_cards, key=lambda c: c.name
        )
        self._init_navigation([_RESULTS_ZONE])
        self._on_state_changed: Callable[[list[Card], int], None] | None = None
        self._on_status_changed: Callable[[str], None] | None = None
```

**Zone items pattern** (lines 28-31):
```python
    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _RESULTS_ZONE:
            return self._results
        return []
```

**Speech format override** — use `_format_item_speech` from `stonereader/presenters/base.py` (lines 52-61):
```python
    def _format_item_speech(self, item: Any, position: int, total: int) -> str:
        suffix = f", {position} of {total}"
        if item is None:
            return "Unknown card" + suffix
        if isinstance(item, tuple) and len(item) == 2:
            card, count = item
            name = getattr(card, "name", str(card))
            return f"{name} x{count}" + suffix
        name = getattr(item, "name", str(item))
        return name + suffix
```

Override for D-08 speech format: `"Name, Class, Format, N of M"`.

**View callback pattern** (lines 50-61):
```python
    def set_on_state_changed(
        self, callback: Callable[[list[Card], int], None]
    ) -> None:
        self._on_state_changed = callback

    def set_on_status_changed(self, callback: Callable[[str], None]) -> None:
        self._on_status_changed = callback

    def _notify_view(self) -> None:
        if self._on_state_changed is not None:
            cursor = self._zone_cursors.get(_RESULTS_ZONE, 0)
            self._on_state_changed(self._results, cursor)
```

**Key map pattern** (lines 86-94):
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

DeckManagerPresenter will add `"enter"`, `"delete"`, and an export key (e.g., `"c"`) to this map.

**Copy/export pattern** (lines 75-84):
```python
    def copy_current_card_name(self) -> str | None:
        """Return current card name and announce copy. View handles clipboard."""
        item = self._current_item()
        if item is None:
            return None
        card = self._extract_card(item)
        if card is None:
            return None
        self.announce(f"Copied {card.name}")
        return card.name
```

Follow same pattern for export: presenter returns deckstring, view handles `wx.TheClipboard`.

---

### `stonereader/presenters/deck_contents.py` (presenter, request-response)

**Analog:** `stonereader/presenters/card_browser.py`

Same structure as `CardBrowserPresenter` but simpler -- single zone containing `(Card, count)` tuples from a `Deck`. No search capability needed.

**Zone items with (Card, count) tuples** -- already handled by base `_format_item_speech` in `stonereader/presenters/base.py` (lines 56-59):
```python
        if isinstance(item, tuple) and len(item) == 2:
            card, count = item
            name = getattr(card, "name", str(card))
            return f"{name} x{count}" + suffix
```

**Detail lines via read_detail_lines** in `stonereader/presenters/base.py` (lines 143-153):
```python
    def read_detail_lines(self, item: Any, direction: int = 1) -> None:
        card = self._extract_card(item)
        if card is None:
            return
        lines = card.detail_lines()
        if not lines:
            return
        self._detail_cursor = max(
            0, min(self._detail_cursor + direction, len(lines) - 1)
        )
        self._speech.speak(lines[self._detail_cursor])
```

`_extract_card` already handles `(Card, count)` tuples (lines 130-141).

---

### `stonereader/presenters/import_deck.py` (presenter, request-response)

**Analog:** `stonereader/presenters/card_browser.py` (role-match only -- import is not zone-based)

This presenter does NOT use `ZoneNavigationMixin`. It inherits only `BasePresenter`.

**BasePresenter inheritance** from `stonereader/presenters/base.py` (lines 18-29):
```python
class BasePresenter:
    """Base class for all presenters."""

    def __init__(self, speech: SpeechService) -> None:
        self._speech = speech

    def announce(self, text: str) -> None:
        self._speech.speak(text)

    def get_key_map(self) -> Dict[str, Callable[[], None]]:
        """Return the key map for this presenter. Subclasses must override."""
        return {}
```

ImportDeckPresenter needs `get_key_map()` to return an empty dict (all input goes through TextCtrls and buttons, not hotkeys). It holds `db_conn`, `card_db`, and a callback for success navigation.

**Deckstring parsing pattern** from `stonereader/models/deck.py` (lines 47-78):
```python
    @classmethod
    def from_deckstring(
        cls, deckstring: str, card_db: CardDatabase, name: str = "Imported Deck"
    ) -> "Deck":
        cards_data, heroes_data, format_data, _ = deckstrings.parse_deckstring(
            deckstring
        )
        # ... resolves cards, detects hero class and format ...
        if missing_cards:
            raise ValueError(f"Missing cards with DBF IDs: {missing_cards}")
```

Catch `(ValueError, TypeError, Exception)` per RESEARCH.md Pitfall 2.

---

### `stonereader/presenters/home.py` (presenter, request-response)

**Analog:** `stonereader/presenters/card_browser.py` (role-match -- simpler, no search)

Uses `ZoneNavigationMixin` with a single zone containing menu item strings (e.g., `["Card Library", "Deck Manager", "Import Deck"]`).

**Key map** will include `"enter"` to select current menu item, `"left"/"right"` for navigation, `"home"/"end"` for jump.

No `_format_item_speech` override needed -- base class handles strings via `getattr(item, "name", str(item))` which falls through to `str(item)`.

---

### `stonereader/views/deck_manager.py` (view, request-response)

**Analog:** `stonereader/views/card_browser.py`

**Imports pattern** (lines 1-14):
```python
"""Card Library view — search TextCtrl and visual-only ListCtrl companion."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

from stonereader.views.base import make_labeled_text_ctrl

if TYPE_CHECKING:
    from stonereader.input_layer import InputLayer
    from stonereader.models.card import Card
    from stonereader.presenters.card_browser import CardBrowserPresenter
```

**Panel class pattern** (lines 47-73):
```python
class CardBrowserPanel(wx.Panel):
    """Card Library tab panel."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: CardBrowserPresenter,
        input_layer: InputLayer,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Search TextCtrl — label placed immediately before for MSAA
        self._search_ctrl = make_labeled_text_ctrl(
            self, sizer, "Search cards:", input_layer, style=wx.TE_PROCESS_ENTER
        )
        self._search_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_search)

        # Visual companion ListCtrl — label for MSAA, never focused by user
        results_label = wx.StaticText(self, label="Card results:")
        sizer.Add(results_label, 0, wx.ALL, 4)
        self._list_ctrl = _CardListCtrl(self)
        sizer.Add(self._list_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)
```

DeckManagerPanel follows same structure but without search TextCtrl. ListCtrl displays deck summaries.

**Virtual ListCtrl pattern** (lines 17-44):
```python
class _CardListCtrl(wx.ListCtrl):
    """Virtual ListCtrl displaying card results."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self.AppendColumn("Card", width=400)
        self._cards: list[Card] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 — wx override
        return False

    def set_cards(self, cards: list[Card]) -> None:
        self._cards = cards
        self.SetItemCount(len(cards))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:
        if item >= len(self._cards):
            return ""
        card = self._cards[item]
        return f"{card.name} — {card.cost} mana — {card.card_type}"
```

**Clipboard write pattern** (lines 112-116):
```python
    def _on_copy_card_name(self, event: wx.CommandEvent) -> None:
        name = self._presenter.copy_current_card_name()
        if name is not None and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(name))
            wx.TheClipboard.Close()
```

Reuse this exact pattern for deck export (deckstring to clipboard).

**View callback wiring** (lines 76-77):
```python
        # Wire presenter callbacks
        presenter.set_on_state_changed(self._on_state_changed)
        presenter.set_on_status_changed(self._on_status_changed)
```

---

### `stonereader/views/deck_contents.py` (view, request-response)

**Analog:** `stonereader/views/card_browser.py`

Same structure as `CardBrowserPanel` but without search. Displays `(Card, count)` tuples in a ListCtrl. `OnGetItemText` would format as `"CardName x2 -- 3 mana -- MINION"`.

---

### `stonereader/views/import_deck.py` (view, request-response)

**Analog:** `stonereader/views/card_browser.py` (for panel structure) + `stonereader/views/base.py` (for labeled text inputs)

**Labeled text input pattern** from `stonereader/views/base.py` (lines 29-46):
```python
def make_labeled_text_ctrl(
    parent: wx.Window,
    sizer: wx.Sizer,
    label: str,
    input_layer: InputLayer,
    style: int = 0,
) -> wx.TextCtrl:
    """Create a labeled TextCtrl and add both to the sizer.

    Places a wx.StaticText immediately before the TextCtrl in the sizer
    so NVDA/JAWS read the label via MSAA sibling order.
    """
    static = wx.StaticText(parent, label=label)
    ctrl = wx.TextCtrl(parent, style=style)
    sizer.Add(static, 0, wx.ALL, 4)
    sizer.Add(ctrl, 0, wx.EXPAND | wx.ALL, 4)
    bind_text_mode(ctrl, input_layer)
    return ctrl
```

Import screen needs two `make_labeled_text_ctrl` calls (deckstring, name) plus buttons. `bind_text_mode` is called automatically by `make_labeled_text_ctrl`.

**Text mode binding pattern** from `stonereader/views/base.py` (lines 15-18):
```python
def bind_text_mode(ctrl: wx.TextCtrl, input_layer: InputLayer) -> None:
    """Bind focus events on a TextCtrl to enter/exit text mode."""
    ctrl.Bind(wx.EVT_SET_FOCUS, lambda evt: (_enter_text(input_layer), evt.Skip()))
    ctrl.Bind(wx.EVT_KILL_FOCUS, lambda evt: (_exit_text(input_layer), evt.Skip()))
```

---

### `stonereader/views/home.py` (view, request-response)

**Analog:** `stonereader/views/card_browser.py` (role-match -- simpler)

Home panel uses `wx.ListBox` (per RESEARCH.md Open Question 1) instead of `wx.ListCtrl`. ListBox is simpler and standard for menu-like selection. NVDA/JAWS handle it natively.

Panel structure follows the same `wx.Panel` with `wx.BoxSizer(wx.VERTICAL)` pattern.

---

### `stonereader/models/deck.py` (modify -- add DeckSummary)

**Analog:** self (existing `Deck` frozen dataclass pattern)

**Frozen dataclass pattern** (lines 1-17):
```python
from dataclasses import dataclass
from typing import Dict, List, Tuple

from hearthstone import deckstrings

from stonereader.models.card import Card, CardDatabase


@dataclass(frozen=True)
class Deck:
    """Represents a Hearthstone deck."""

    name: str
    format: str
    cards: Tuple[Tuple[Card, int], ...]
    hero_class: str
    deckstring: str = ""
```

Add `DeckSummary` following same pattern:
```python
@dataclass(frozen=True)
class DeckSummary:
    """Lightweight deck info for list display."""

    deck_id: int
    name: str
    hero_class: str
    format: str
    deckstring: str
    created_at: str
```

---

### `stonereader/app.py` (modify -- NavigationController replaces wx.Notebook)

**Analog:** self

**Current tab registration pattern** (lines 63-78):
```python
    def add_tab(
        self,
        panel: wx.Panel,
        name: str,
        presenter: object,
        focus_target: wx.Window,
    ) -> None:
        """Register a feature tab."""
        self._notebook.AddPage(panel, name)
        self._tab_presenters.append(presenter)
        self._tab_focus_targets.append(focus_target)
        self._tab_names.append(name)
        if len(self._tab_presenters) == 1:
            get_map = getattr(presenter, "get_key_map", None)
            key_map = get_map() if get_map is not None else {}
            self._input_layer.activate_view(name, key_map)
```

Replace with `NavigationController.register_panel()` and `show_panel()` following the pattern in RESEARCH.md Pattern 1. The key_map swap and focus management logic from `_on_page_changed` (lines 80-89) transfers directly to `NavigationController.show_panel()`:

```python
    def _on_page_changed(self, event: wx.BookCtrlEvent) -> None:
        page = event.GetSelection()
        if 0 <= page < len(self._tab_presenters):
            presenter = self._tab_presenters[page]
            get_map = getattr(presenter, "get_key_map", None)
            key_map = get_map() if get_map is not None else {}
            self._input_layer.activate_view(self._tab_names[page], key_map)
            target = self._tab_focus_targets[page]
            wx.CallAfter(target.SetFocus)
        event.Skip()
```

**OnInit feature registration pattern** (lines 102-118):
```python
    def OnInit(self) -> bool:
        self._frame = MainWindow()

        # Card Library tab
        from stonereader.models.card import CardDatabase
        from stonereader.presenters.card_browser import CardBrowserPresenter
        from stonereader.views.card_browser import CardBrowserPanel

        card_db = CardDatabase.load()
        card_presenter = CardBrowserPresenter(self._frame.speech, card_db)
        card_panel = CardBrowserPanel(
            self._frame.notebook, card_presenter, self._frame.input_layer
        )
        self._frame.add_tab(card_panel, "Card Library", card_presenter, card_panel)

        self._frame.Show()
        return True
```

Refactor to register all panels with `NavigationController` and show home screen first.

---

### `stonereader/db.py` (modify -- add CRUD functions)

**Analog:** self

**Existing db pattern** (lines 35-62):
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

New CRUD functions follow same conventions: pure functions taking `sqlite3.Connection`, parameterized queries, `conn.commit()` after writes. See RESEARCH.md Pattern 3 for `save_deck`, `get_all_decks`, `delete_deck` examples.

Note: `conn.row_factory = sqlite3.Row` is set in `get_connection()` (line 42), so query results return `sqlite3.Row` objects, not plain tuples. CRUD functions should handle this.

---

### `stonereader/input_layer.py` (modify -- add WXK_DELETE)

**Analog:** self

**Key name mapping pattern** (lines 21-33):
```python
_KEY_NAMES: Dict[int, str] = {
    wx.WXK_LEFT: "left",
    wx.WXK_RIGHT: "right",
    wx.WXK_UP: "up",
    wx.WXK_DOWN: "down",
    wx.WXK_RETURN: "enter",
    wx.WXK_NUMPAD_ENTER: "enter",
    wx.WXK_ESCAPE: "escape",
    wx.WXK_BACK: "back",
    wx.WXK_HOME: "home",
    wx.WXK_END: "end",
    wx.WXK_SPACE: "space",
}
```

Add `wx.WXK_DELETE: "delete"` to this dictionary.

---

### `stonereader/models/__init__.py` (modify -- add DeckSummary export)

**Analog:** self

**Barrel export pattern** (lines 1-16):
```python
"""StoneReader domain models."""

from stonereader.models.card import Card, CardDatabase
from stonereader.models.deck import Deck
from stonereader.models.game_state import GameEntity, GameState, Hero
from stonereader.models.replay import ReplayState

__all__ = [
    "Card",
    "CardDatabase",
    "Deck",
    "GameEntity",
    "GameState",
    "Hero",
    "ReplayState",
]
```

Add `DeckSummary` to the import from `deck` and to `__all__`.

---

### `tests/test_deck_manager.py` (test)

**Analog:** `tests/test_card_browser.py`

**Test file structure** (lines 1-9):
```python
"""Tests for CardBrowserPresenter."""

from __future__ import annotations

from tests.conftest import MockSpeechService
from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.card_browser import CardBrowserPresenter
```

**MockSpeechService usage** from `tests/conftest.py` (lines 8-21):
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

**Test function pattern** (lines 65-72):
```python
def test_search_with_query_announces_result_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("fire")

    assert "1 result" in speech.last_speech
```

For DeckManagerPresenter tests: create in-memory SQLite database (from `test_db.py` pattern using `tmp_path`), insert test deck rows, then test presenter operations. Assert speech output matches D-08 format.

**In-memory DB test pattern** from `tests/test_db.py` (lines 4-7):
```python
def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
```

---

### `tests/test_deck_contents.py` (test)

**Analog:** `tests/test_card_browser.py`

Same structure. Create a `Deck` with known cards, pass to `DeckContentsPresenter`, test zone navigation and detail inspection on `(Card, count)` tuples.

**Card fixture pattern** from `tests/test_card_browser.py` (lines 11-54):
```python
def make_card(
    name: str = "Test Card",
    cost: int = 1,
    attack: int | None = None,
    health: int | None = None,
    text: str = "",
    card_type: str = "MINION",
    card_class: str = "NEUTRAL",
    rarity: str = "COMMON",
    card_set: str = "CORE",
) -> Card:
    global _next_dbf_id
    _next_dbf_id += 1
    return Card(
        id=f"TEST_{name.upper().replace(' ', '_')}",
        dbf_id=_next_dbf_id,
        name=name,
        cost=cost,
        attack=attack,
        health=health,
        text=text,
        rarity=rarity,
        card_class=card_class,
        card_type=card_type,
        card_set=card_set,
        collectible=True,
    )
```

---

### `tests/test_import_deck.py` (test)

**Analog:** `tests/test_card_browser.py` (role-match)

Tests for `ImportDeckPresenter`. Focus on validation logic: empty deckstring, empty name, invalid deckstring (ValueError), malformed base64 (TypeError). No wx needed -- test presenter logic only.

---

### `tests/test_home.py` (test)

**Analog:** `tests/test_zone_navigation.py`

**Stub presenter pattern** from `tests/test_zone_navigation.py` (lines 7-19):
```python
class StubPresenter(ZoneNavigationMixin, BasePresenter):
    """Minimal presenter for testing zone navigation."""

    def __init__(self, speech: MockSpeechService) -> None:
        super().__init__(speech)
        self._items: dict[str, list[Any]] = {
            "zone_a": ["Alpha", "Bravo", "Charlie"],
            "zone_b": ["Delta", "Echo"],
        }
        self._init_navigation(["zone_a", "zone_b"])

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        return self._items.get(zone_name, [])
```

HomePresenter can be tested the same way -- it IS the real presenter with string items like `["Card Library", "Deck Manager", "Import Deck"]`.

---

### `tests/test_navigation.py` (test)

**Analog:** `tests/test_input_layer.py`

**wx.App and Frame setup pattern** from `tests/test_input_layer.py` (lines 1-6, 52-59):
```python
import wx

from stonereader.input_layer import InputLayer, _key_spec_from_event

# wx.App must exist before creating any wx objects
_app = wx.App(False)
```

```python
def test_input_layer_calls_mapped_callback():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"b": lambda: called.append("b")})
    event = _make_key_event(ord("B"))
    layer._on_char_hook(event)
    assert called == ["b"]
    frame.Destroy()
```

NavigationController tests need `wx.App(False)`, a `wx.Frame`, and a `wx.BoxSizer`. Test `register_panel`, `show_panel`, `go_back` with mock panels. Verify focus and visibility state.

---

### `tests/test_db.py` (extend)

**Analog:** self

**DB test pattern** (lines 4-15):
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
    assert "games" in tables
    assert "schema_version" in tables
    conn.close()
```

Add CRUD tests: `test_save_deck_returns_id`, `test_get_all_decks_sorted_by_newest`, `test_delete_deck_removes_row`, `test_get_all_decks_empty`.

---

## Shared Patterns

### Speech Service (All Presenters)

**Source:** `stonereader/speech_service.py` (lines 33-36)
**Apply to:** All presenter files -- never call `print()`, always use `self._speech.speak()`.

```python
    def speak(self, text: str, interrupt: bool = True) -> None:
        """Send text to the screen reader."""
        if self._use_stdout or self._output is None:
            print(text)
            return
```

### BasePresenter Inheritance

**Source:** `stonereader/presenters/base.py` (lines 18-29)
**Apply to:** All new presenter files.

```python
class BasePresenter:
    """Base class for all presenters."""

    def __init__(self, speech: SpeechService) -> None:
        self._speech = speech

    def announce(self, text: str) -> None:
        self._speech.speak(text)

    def get_key_map(self) -> Dict[str, Callable[[], None]]:
        """Return the key map for this presenter. Subclasses must override."""
        return {}
```

### ZoneNavigationMixin

**Source:** `stonereader/presenters/base.py` (lines 32-163)
**Apply to:** `DeckManagerPresenter`, `DeckContentsPresenter`, `HomePresenter` -- all zone-based presenters.

Key methods: `_init_navigation(zones)`, `get_zone_items(zone_name)`, `navigate_to_zone()`, `move_in_zone()`, `jump_to_first()`, `jump_to_last()`, `_current_item()`, `read_detail_lines()`.

### View Panel Construction

**Source:** `stonereader/views/card_browser.py` (lines 47-73)
**Apply to:** All new view panel files.

```python
class CardBrowserPanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        presenter: CardBrowserPresenter,
        input_layer: InputLayer,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter
        sizer = wx.BoxSizer(wx.VERTICAL)
        # ... add widgets to sizer ...
        self.SetSizer(sizer)
        # Wire presenter callbacks
```

### Labeled Text Input (MSAA)

**Source:** `stonereader/views/base.py` (lines 29-46)
**Apply to:** `ImportDeckPanel` -- all TextCtrl widgets on the import screen.

```python
def make_labeled_text_ctrl(
    parent: wx.Window,
    sizer: wx.Sizer,
    label: str,
    input_layer: InputLayer,
    style: int = 0,
) -> wx.TextCtrl:
    static = wx.StaticText(parent, label=label)
    ctrl = wx.TextCtrl(parent, style=style)
    sizer.Add(static, 0, wx.ALL, 4)
    sizer.Add(ctrl, 0, wx.EXPAND | wx.ALL, 4)
    bind_text_mode(ctrl, input_layer)
    return ctrl
```

### Clipboard Write

**Source:** `stonereader/views/card_browser.py` (lines 112-116)
**Apply to:** `DeckManagerPanel` (export deckstring), `MainWindow` (clipboard auto-detection read).

```python
    def _on_copy_card_name(self, event: wx.CommandEvent) -> None:
        name = self._presenter.copy_current_card_name()
        if name is not None and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(name))
            wx.TheClipboard.Close()
```

### Key Map Swap on View Activation

**Source:** `stonereader/input_layer.py` (lines 64-67) + `stonereader/app.py` (lines 80-89)
**Apply to:** `NavigationController.show_panel()` and `go_back()`.

```python
    def activate_view(self, name: str, key_map: Dict[str, Callable[[], None]]) -> None:
        """Replace the active key map."""
        self._current_key_map = key_map
        self._text_mode = False
```

### Test Fixture: MockSpeechService

**Source:** `tests/conftest.py` (lines 8-21)
**Apply to:** All new test files.

```python
class MockSpeechService(SpeechService):
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

### Test Fixture: In-Memory SQLite

**Source:** `tests/test_db.py` (lines 4-7)
**Apply to:** `test_deck_manager.py`, `test_import_deck.py`, `test_db.py` (extended).

```python
def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
```

### Module Docstring Convention

**Apply to:** All new files.

Every module starts with a docstring. Format: `"""One-line summary — context phrase."""`

Examples from codebase:
- `"""Card Library presenter — search and browse the card database."""`
- `"""Card Library view — search TextCtrl and visual-only ListCtrl companion."""`
- `"""Shared view helpers and base widgets."""`
- `"""SQLite database for persisting decks and game history."""`

### Import Convention

**Apply to:** All new files.

Always use `from __future__ import annotations` first. Then stdlib, then project imports. Absolute imports only -- never relative.

```python
from __future__ import annotations

import sqlite3
from typing import Any, Callable, Sequence

from stonereader.models.deck import DeckSummary
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `stonereader/app.py` (NavigationController class) | infrastructure | request-response | New navigation paradigm -- no panel-swap stack exists yet. Use RESEARCH.md Pattern 1 as reference. Closest existing logic is `_on_page_changed` in `app.py` lines 80-89. |
| Clipboard auto-detection (`EVT_ACTIVATE` handler) | infrastructure | event-driven | No clipboard-read-on-activate pattern exists. `_on_activate` in `input_layer.py` handles text mode only. Use RESEARCH.md Pattern 4 as reference. |

## Metadata

**Analog search scope:** `stonereader/`, `tests/`
**Files scanned:** 15 source files, 5 test files
**Pattern extraction date:** 2026-04-15
