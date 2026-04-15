# Card Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Card Library feature — browse and search the Hearthstone card database with speech-driven navigation, detail inspection, and context menu copy.

**Architecture:** CardBrowserPresenter owns search state and a single "results" zone, inheriting ZoneNavigationMixin for cursor-per-zone navigation. CardBrowserPanel provides a search TextCtrl and a visual-only virtual ListCtrl companion. The presenter drives all speech output; the view is passive.

**Tech Stack:** Python 3.12+, wxPython (wx.ListCtrl virtual mode), hearthstone-data (CardDatabase), accessible_output2 (via SpeechService)

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `tests/test_card_browser.py` | Unit tests for CardBrowserPresenter — search, navigation, detail inspection, copy |
| **Create:** `stonereader/presenters/card_browser.py` | CardBrowserPresenter — search state, "results" zone, key map, view callbacks |
| **Create:** `stonereader/views/card_browser.py` | CardBrowserPanel — search TextCtrl, virtual ListCtrl companion, context menu |
| **Modify:** `stonereader/app.py` | Register Card Library tab in MainWindow |

---

### Task 1: CardBrowserPresenter — search

**Files:**
- Create: `tests/test_card_browser.py`
- Create: `stonereader/presenters/card_browser.py`

- [ ] **Step 1: Write the failing tests**

Create the test file with helpers and three search tests:

```python
# tests/test_card_browser.py
"""Tests for CardBrowserPresenter."""

from __future__ import annotations

from tests.conftest import MockSpeechService
from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.card_browser import CardBrowserPresenter


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
    return Card(
        id=f"TEST_{name.upper().replace(' ', '_')}",
        dbf_id=0,
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


def make_card_db(cards: list[Card]) -> CardDatabase:
    db = CardDatabase()
    for card in cards:
        db.cards_by_id[card.id] = card
        db.cards_by_dbf_id[card.dbf_id] = card
        db.cards_by_name[card.name.lower()] = card
        db.cards_by_class.setdefault(card.card_class, []).append(card)
        db.cards_by_type.setdefault(card.card_type, []).append(card)
        db.cards_by_set.setdefault(card.card_set, []).append(card)
        db.cards_by_cost.setdefault(card.cost, []).append(card)
        if card.collectible:
            db.collectible_cards.append(card)
    return db


FIREBALL = make_card(name="Fireball", cost=4, text="Deal 6 damage.", card_class="MAGE")
FROSTBOLT = make_card(name="Frostbolt", cost=2, text="Deal 3 damage. Freeze.", card_class="MAGE")
ARCANE = make_card(name="Arcane Intellect", cost=3, text="Draw 2 cards.", card_class="MAGE")
WOLFRIDER = make_card(name="Wolfrider", cost=3, attack=3, health=1, text="Charge")

ALL_CARDS = [FIREBALL, FROSTBOLT, ARCANE, WOLFRIDER]


def test_search_with_query_announces_result_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("fire")

    assert "1 result" in speech.last_speech


def test_search_multiple_results_announces_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("damage")

    assert "2 results" in speech.last_speech


def test_search_no_results_announces_no_results():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("xyz_no_match")

    assert "No results" in speech.last_speech


def test_search_resets_cursor_to_first():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("damage")
    presenter.move_in_zone(1)  # move to second result
    presenter.search("damage")  # search again

    # Cursor should be back at 0
    assert presenter._zone_cursors["results"] == 0


def test_initial_results_are_all_collectible_cards():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    items = presenter.get_zone_items("results")

    assert len(items) == 4
    # Sorted by name
    assert items[0].name == "Arcane Intellect"
    assert items[1].name == "Fireball"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_card_browser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stonereader.presenters.card_browser'`

- [ ] **Step 3: Write CardBrowserPresenter with search**

```python
# stonereader/presenters/card_browser.py
"""Card Library presenter — search and browse the card database."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from stonereader.models.card import Card, CardDatabase
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.speech_service import SpeechService


class CardBrowserPresenter(ZoneNavigationMixin, BasePresenter):
    """Manages search state and navigation for the Card Library tab."""

    def __init__(self, speech: SpeechService, card_db: CardDatabase) -> None:
        super().__init__(speech)
        self._card_db = card_db
        self._results: list[Card] = sorted(
            card_db.collectible_cards, key=lambda c: c.name
        )
        self._init_navigation(["results"])
        self._on_state_changed: Callable[[list[Card], int], None] | None = None

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == "results":
            return self._results
        return []

    def search(self, query: str) -> None:
        """Run a search and announce the result count."""
        self._results = self._card_db.search_cards(query)
        self._zone_cursors["results"] = 0
        self._detail_cursor = -1
        count = len(self._results)
        if count == 0:
            self._speech.speak("No results")
        elif count == 1:
            self._speech.speak("1 result")
        else:
            self._speech.speak(f"{count} results")
        self._notify_view()

    def set_on_state_changed(
        self, callback: Callable[[list[Card], int], None]
    ) -> None:
        self._on_state_changed = callback

    def _notify_view(self) -> None:
        if self._on_state_changed is not None:
            cursor = self._zone_cursors.get("results", 0)
            self._on_state_changed(self._results, cursor)

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        return {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_card_browser.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_card_browser.py stonereader/presenters/card_browser.py
git commit -m "$(cat <<'EOF'
feat: add CardBrowserPresenter with search

Introduces the Card Library presenter with search and result count
speech announcements. Initial state loads all collectible cards.
EOF
)"
```

---

### Task 2: CardBrowserPresenter — navigation key map

**Files:**
- Modify: `tests/test_card_browser.py`
- Modify: `stonereader/presenters/card_browser.py`

- [ ] **Step 1: Write the failing navigation tests**

Append to `tests/test_card_browser.py`:

```python
def test_key_map_has_navigation_keys():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()

    assert "left" in key_map
    assert "right" in key_map
    assert "up" in key_map
    assert "down" in key_map
    assert "home" in key_map
    assert "end" in key_map


def test_right_arrow_announces_next_card():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["right"]()

    # Initial cursor is 0 (Arcane Intellect), right goes to 1 (Fireball)
    assert "Fireball" in speech.last_speech
    assert "2 of 4" in speech.last_speech


def test_left_arrow_at_start_stays_at_first():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["left"]()

    assert "Arcane Intellect" in speech.last_speech
    assert "1 of 4" in speech.last_speech


def test_down_arrow_reads_first_detail_line():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()

    # First detail line is the card name
    assert "Arcane Intellect" in speech.last_speech


def test_down_arrow_twice_reads_cost():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()
    key_map["down"]()

    assert "3 mana" in speech.last_speech


def test_up_arrow_moves_back_through_details():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["down"]()  # name
    key_map["down"]()  # cost
    key_map["up"]()    # back to name

    assert "Arcane Intellect" in speech.last_speech


def test_home_jumps_to_first():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["right"]()
    key_map["right"]()
    key_map["home"]()

    assert "Arcane Intellect" in speech.last_speech
    assert "1 of 4" in speech.last_speech


def test_end_jumps_to_last():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    key_map = presenter.get_key_map()
    key_map["end"]()

    assert "Wolfrider" in speech.last_speech
    assert "4 of 4" in speech.last_speech
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_card_browser.py::test_key_map_has_navigation_keys -v`
Expected: FAIL — `get_key_map()` returns empty dict

- [ ] **Step 3: Implement the key map**

Replace `get_key_map` in `stonereader/presenters/card_browser.py`:

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

    def _read_detail_down(self) -> None:
        item = self._current_item()
        if item is not None:
            self.read_detail_lines(item, direction=1)

    def _read_detail_up(self) -> None:
        item = self._current_item()
        if item is not None:
            self.read_detail_lines(item, direction=-1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_card_browser.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_card_browser.py stonereader/presenters/card_browser.py
git commit -m "$(cat <<'EOF'
feat: add Card Library navigation key map

Left/Right navigates cards, Up/Down reads detail lines,
Home/End jumps to first/last card.
EOF
)"
```

---

### Task 3: CardBrowserPresenter — view sync and copy

**Files:**
- Modify: `tests/test_card_browser.py`
- Modify: `stonereader/presenters/card_browser.py`

- [ ] **Step 1: Write the failing view-callback and copy tests**

Append to `tests/test_card_browser.py`:

```python
def test_view_callback_fires_on_search():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    received: list[tuple[int, int]] = []

    def on_state_changed(results: list[Card], cursor: int) -> None:
        received.append((len(results), cursor))

    presenter.set_on_state_changed(on_state_changed)
    presenter.search("fire")

    assert received == [(1, 0)]


def test_view_callback_fires_on_navigation():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    received: list[tuple[int, int]] = []

    def on_state_changed(results: list[Card], cursor: int) -> None:
        received.append((len(results), cursor))

    presenter.set_on_state_changed(on_state_changed)
    presenter.move_in_zone(1)  # right

    assert received == [(4, 1)]


def test_copy_current_card_name_returns_name():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    name = presenter.copy_current_card_name()

    assert name == "Arcane Intellect"
    assert "Copied Arcane Intellect" in speech.last_speech


def test_copy_with_no_results_returns_none():
    card_db = make_card_db([])
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    name = presenter.copy_current_card_name()

    assert name is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_card_browser.py::test_view_callback_fires_on_navigation -v`
Expected: FAIL — `_notify_view` not called from `move_in_zone`

Run: `uv run pytest tests/test_card_browser.py::test_copy_current_card_name_returns_name -v`
Expected: FAIL — `AttributeError: 'CardBrowserPresenter' object has no attribute 'copy_current_card_name'`

- [ ] **Step 3: Implement view sync on navigation and copy**

Add to `stonereader/presenters/card_browser.py`:

Override `move_in_zone` to add view sync:

```python
    def move_in_zone(self, delta: int) -> None:
        super().move_in_zone(delta)
        self._notify_view()
```

Add the copy method:

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_card_browser.py -v`
Expected: All 17 tests PASS

- [ ] **Step 5: Run linting and type checks**

Run: `uv run ruff check stonereader/presenters/card_browser.py tests/test_card_browser.py`
Expected: No issues

Run: `uv run pyright stonereader/presenters/card_browser.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add tests/test_card_browser.py stonereader/presenters/card_browser.py
git commit -m "$(cat <<'EOF'
feat: add Card Library view sync and copy card name

View callback fires on search and navigation for visual ListCtrl sync.
copy_current_card_name returns the name and announces the copy.
EOF
)"
```

---

### Task 4: CardBrowserPanel — view

**Files:**
- Create: `stonereader/views/card_browser.py`

- [ ] **Step 1: Create CardBrowserPanel**

```python
# stonereader/views/card_browser.py
"""Card Library view — search TextCtrl and visual-only ListCtrl companion."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

from stonereader.views.base import make_labeled_text_ctrl

if TYPE_CHECKING:
    from stonereader.input_layer import InputLayer
    from stonereader.models.card import Card
    from stonereader.presenters.card_browser import CardBrowserPresenter


class _CardListCtrl(wx.ListCtrl):
    """Virtual ListCtrl displaying card results as a visual companion.

    Never focused — NVDA will not announce selection changes.
    """

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self.AppendColumn("Card", width=400)
        self._cards: list[Card] = []

    def set_cards(self, cards: list[Card]) -> None:
        self._cards = cards
        self.SetItemCount(len(cards))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:
        if item >= len(self._cards):
            return ""
        card = self._cards[item]
        return f"{card.name} — {card.cost} mana — {card.card_type}"


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

        # Wire view callback
        presenter.set_on_state_changed(self._on_state_changed)

        # Context menu
        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

        # Initial visual state
        self._list_ctrl.set_cards(list(presenter.get_zone_items("results")))

    @property
    def search_ctrl(self) -> wx.TextCtrl:
        return self._search_ctrl

    def _on_search(self, event: wx.CommandEvent) -> None:
        query = self._search_ctrl.GetValue()
        self._presenter.search(query)
        self.SetFocus()
        frame = self.GetTopLevelParent()
        count = len(self._presenter.get_zone_items("results"))
        if count:
            frame.SetStatusText(f"{count} results")
        else:
            frame.SetStatusText("No results")

    def _on_state_changed(self, results: list[Card], cursor: int) -> None:
        self._list_ctrl.set_cards(results)
        if results:
            self._list_ctrl.Select(cursor)

    def _on_context_menu(self, event: wx.ContextMenuEvent) -> None:
        menu = wx.Menu()
        copy_id = wx.NewIdRef()
        menu.Append(copy_id, "Copy card name")
        self.Bind(wx.EVT_MENU, self._on_copy_card_name, id=copy_id)
        self.PopupMenu(menu)
        menu.Destroy()

    def _on_copy_card_name(self, event: wx.CommandEvent) -> None:
        name = self._presenter.copy_current_card_name()
        if name is not None and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(name))
            wx.TheClipboard.Close()
```

- [ ] **Step 2: Run linting**

Run: `uv run ruff check stonereader/views/card_browser.py`
Expected: No issues

- [ ] **Step 3: Commit**

```bash
git add stonereader/views/card_browser.py
git commit -m "$(cat <<'EOF'
feat: add CardBrowserPanel with search and visual companion

Speech-driven panel with labeled search TextCtrl, virtual ListCtrl
visual companion, and context menu for copying card names.
EOF
)"
```

---

### Task 5: Tab registration

**Files:**
- Modify: `stonereader/app.py:94-100` (StoneReaderApp.OnInit)

- [ ] **Step 1: Register Card Library tab in StoneReaderApp.OnInit**

In `stonereader/app.py`, update `StoneReaderApp.OnInit` to load the card database and register the tab:

```python
class StoneReaderApp(wx.App):
    """Application entry point."""

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

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Run linting and type checks**

Run: `uv run ruff check . && uv run pyright stonereader/`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add stonereader/app.py
git commit -m "$(cat <<'EOF'
feat: register Card Library tab in app shell

Loads card database on startup and wires up the Card Library as the
first Notebook tab with presenter and panel.
EOF
)"
```

---

## Summary

After all 5 tasks, the Card Library feature is complete:

- **Search**: type in the search box, press Enter. Speech announces result count. Focus returns to panel.
- **Browse**: Left/Right navigates cards with name and position ("2 of 47: Fireball"). All collectible cards loaded on startup.
- **Detail inspection**: Down/Up reads card detail lines one at a time (name, cost, attack/health, type, class, text, set, rarity).
- **Quick navigation**: Home/End jumps to first/last card.
- **Context menu**: Applications key or Shift+F10 opens menu with "Copy card name".
- **Visual companion**: Virtual ListCtrl syncs selection with speech cursor but is never focused.
- **Status bar**: Shows result count, readable via NVDA+End / JAWS Insert+B.
- **Accessibility**: All controls labeled via MSAA sibling order. All navigation keyboard-only. EVT_CHAR_HOOK routing.
