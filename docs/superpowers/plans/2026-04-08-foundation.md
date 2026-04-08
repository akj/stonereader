# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared infrastructure (speech service, input layer, app shell, database, base presenter/view patterns) that every feature slice depends on.

**Architecture:** MVP pattern. Models are frozen dataclasses (already exist). Presenters own navigation state, key maps, and speech. Views are passive wxPython widgets. Speech-driven navigation with visual companion ListCtrl widgets. EVT_CHAR_HOOK for all keyboard handling.

**Tech Stack:** Python 3.12, wxPython 4.2.3+, accessible_output2, SQLite (stdlib sqlite3), pytest, hearthstone library

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `stonereader/models/__init__.py` | Re-export all model classes from submodules |
| Create | `stonereader/models/card.py` | Card, CardDatabase (moved from models.py) |
| Create | `stonereader/models/deck.py` | Deck (moved from models.py) |
| Create | `stonereader/models/game_state.py` | Hero, GameEntity, GameState (moved from models.py) |
| Create | `stonereader/models/replay.py` | ReplayState |
| Create | `stonereader/speech_service.py` | SpeechService: accessible_output2 wrapper with stdout fallback |
| Create | `stonereader/input_layer.py` | InputLayer: EVT_CHAR_HOOK key routing, text mode |
| Create | `stonereader/app.py` | MainWindow, wx.Notebook shell, AcceleratorTable, StatusBar |
| Create | `stonereader/__main__.py` | App entry point |
| Create | `stonereader/db.py` | SQLite connection, schema creation, migrations |
| Create | `stonereader/presenters/__init__.py` | Empty init |
| Create | `stonereader/presenters/base.py` | BasePresenter, ZoneNavigationMixin |
| Create | `stonereader/views/__init__.py` | Empty init |
| Create | `stonereader/views/base.py` | Text mode helpers, panel factory |
| Create | `tests/__init__.py` | Empty init |
| Create | `tests/test_speech_service.py` | SpeechService unit tests |
| Create | `tests/test_input_layer.py` | InputLayer unit tests |
| Create | `tests/test_zone_navigation.py` | ZoneNavigationMixin unit tests |
| Create | `tests/test_db.py` | Database schema and migration tests |
| Create | `tests/conftest.py` | Shared fixtures (SpeechService mock, wx.App) |
| Delete | `stonereader/models.py` | Replaced by models/ package |
| Delete | `stonereader/presenters.py` | Replaced by presenters/ package |
| Delete | `stonereader/views.py` | Replaced by views/ package |
| Modify | `pyproject.toml` | Add pytest, accessible_output2 dependencies |

---

### Task 1: Add test and runtime dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pytest to dev dependencies and accessible_output2 to runtime dependencies**

```toml
[project]
name = "stonereader"
version = "0.1.0"
description = "An accessible interface to view Hearthstone cards, decks, and replays."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "accessible-output2>=0.17",
    "hearthstone>=9.15.8",
    "hearthstone-data>=221175.1",
    "pip",
    "setuptools>=80.9.0",
    "wxpython>=4.2.3",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pyright>=1.1.402",
    "ruff>=0.11.10",
]
```

- [ ] **Step 2: Sync dependencies**

Run: `uv sync`
Expected: resolves and installs pytest and accessible_output2

- [ ] **Step 3: Verify imports work**

Run: `uv run python -c "import pytest; import accessible_output2; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add pytest and accessible_output2 to dependencies"
```

---

### Task 2: Split models.py into models/ package

**Files:**
- Create: `stonereader/models/__init__.py`
- Create: `stonereader/models/card.py`
- Create: `stonereader/models/deck.py`
- Create: `stonereader/models/game_state.py`
- Create: `stonereader/models/replay.py`
- Delete: `stonereader/models.py`

- [ ] **Step 1: Create `stonereader/models/card.py`**

Move `Card` and `CardDatabase` from `stonereader/models.py` into this file. Keep all imports they need:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from hearthstone.cardxml import load


@dataclass(frozen=True)
class Card:
    """Represents a Hearthstone card with complete tag access."""

    id: str
    dbf_id: int
    name: str
    cost: int
    attack: Optional[int]
    health: Optional[int]
    text: str
    rarity: str
    card_class: str
    card_type: str
    card_set: str = ""
    collectible: bool = True
    durability: Optional[int] = None
    tags: Dict[str, Any] = field(default_factory=dict)

    def has_tag(self, tag_name: str) -> bool:
        if not self.tags:
            return False
        return bool(self.tags.get(tag_name, 0))

    def get_tag(self, tag_name: str, default: Any = None) -> Any:
        if not self.tags:
            return default
        return self.tags.get(tag_name, default)

    @classmethod
    def from_cardxml(cls, cardxml_card: Any) -> "Card":
        tags_dict: Dict[str, Any] = {}
        if hasattr(cardxml_card, "tags") and cardxml_card.tags:
            for tag_enum, value in cardxml_card.tags.items():
                tag_name = str(tag_enum).split(".")[-1]
                tags_dict[tag_name] = value

        return cls(
            id=cardxml_card.id,
            dbf_id=cardxml_card.dbf_id if hasattr(cardxml_card, "dbf_id") else 0,
            name=cardxml_card.name or "",
            cost=cardxml_card.cost or 0,
            attack=cardxml_card.atk if cardxml_card.atk else None,
            health=cardxml_card.health if cardxml_card.health else None,
            text=cardxml_card.description or "",
            rarity=str(cardxml_card.rarity) if cardxml_card.rarity else "COMMON",
            card_class=(
                str(cardxml_card.card_class) if cardxml_card.card_class else "NEUTRAL"
            ),
            card_type=str(cardxml_card.type) if cardxml_card.type else "MINION",
            card_set=str(cardxml_card.card_set) if cardxml_card.card_set else "",
            collectible=bool(cardxml_card.collectible),
            durability=cardxml_card.durability if cardxml_card.durability else None,
            tags=tags_dict,
        )

    def to_speech_text(self) -> str:
        """Return card name only for navigation announcements (DL-004)."""
        return self.name

    def detail_lines(self) -> list[str]:
        """Return ordered detail lines for Up/Down inspection.

        Order: name, cost, attack/health (if applicable), type, class,
        text, set, rarity, durability (if applicable).
        """
        lines = [
            self.name,
            f"{self.cost} mana",
        ]
        if self.attack is not None and self.health is not None:
            lines.append(f"{self.attack} attack, {self.health} health")
        elif self.attack is not None:
            lines.append(f"{self.attack} attack")
        elif self.health is not None:
            lines.append(f"{self.health} health")
        lines.append(self.card_type.lower())
        if self.card_class != "NEUTRAL":
            lines.append(f"{self.card_class.lower()} class")
        if self.text:
            lines.append(self.text)
        if self.card_set:
            lines.append(f"Set: {self.card_set}")
        lines.append(self.rarity.lower())
        if self.durability is not None:
            lines.append(f"{self.durability} durability")
        return lines


@dataclass
class CardDatabase:
    """Card database with indexed lookups and search."""

    cards_by_id: Dict[str, Card] = field(default_factory=dict)
    cards_by_dbf_id: Dict[int, Card] = field(default_factory=dict)
    cards_by_name: Dict[str, Card] = field(default_factory=dict)
    cards_by_class: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_type: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_set: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_cost: Dict[int, List[Card]] = field(default_factory=dict)
    collectible_cards: List[Card] = field(default_factory=list)

    @classmethod
    def load(cls) -> "CardDatabase":
        db, _ = load()
        card_db = cls()
        for card_data in db.values():
            card = Card.from_cardxml(card_data)
            card_db.cards_by_id[card.id] = card
            card_db.cards_by_dbf_id[card.dbf_id] = card
            card_db.cards_by_name[card.name.lower()] = card
            card_db.cards_by_class.setdefault(card.card_class, []).append(card)
            card_db.cards_by_type.setdefault(card.card_type, []).append(card)
            card_db.cards_by_set.setdefault(card.card_set, []).append(card)
            card_db.cards_by_cost.setdefault(card.cost, []).append(card)
            if card.collectible:
                card_db.collectible_cards.append(card)
        return card_db

    def get_card_by_id(self, card_id: str) -> Optional[Card]:
        return self.cards_by_id.get(card_id)

    def get_card_by_dbf_id(self, dbf_id: int) -> Optional[Card]:
        return self.cards_by_dbf_id.get(dbf_id)

    def get_card_by_name(self, name: str) -> Optional[Card]:
        return self.cards_by_name.get(name.lower())

    def search_cards(
        self, query: str = "", filters: Optional[Dict[str, Any]] = None
    ) -> List[Card]:
        if filters is None:
            filters = {}
        candidates = self.collectible_cards.copy()
        if "card_class" in filters:
            candidates = [c for c in candidates if c.card_class == filters["card_class"]]
        if "card_type" in filters:
            candidates = [c for c in candidates if c.card_type == filters["card_type"]]
        if "card_set" in filters:
            candidates = [c for c in candidates if c.card_set == filters["card_set"]]
        if "cost" in filters:
            candidates = [c for c in candidates if c.cost == filters["cost"]]
        if "min_cost" in filters:
            candidates = [c for c in candidates if c.cost >= filters["min_cost"]]
        if "max_cost" in filters:
            candidates = [c for c in candidates if c.cost <= filters["max_cost"]]
        if "rarity" in filters:
            candidates = [c for c in candidates if c.rarity == filters["rarity"]]
        if query:
            query_lower = query.lower()
            candidates = [
                c
                for c in candidates
                if query_lower in c.name.lower() or query_lower in c.text.lower()
            ]
        return sorted(candidates, key=lambda c: c.name)

    def get_cards_by_class(self, card_class: str) -> List[Card]:
        return self.cards_by_class.get(card_class, [])

    def get_cards_by_type(self, card_type: str) -> List[Card]:
        return self.cards_by_type.get(card_type, [])

    def get_cards_by_cost(self, cost: int) -> List[Card]:
        return self.cards_by_cost.get(cost, [])

    def get_cards_by_set(self, card_set: str) -> List[Card]:
        return self.cards_by_set.get(card_set, [])

    def total_cards(self) -> int:
        return len(self.cards_by_id)

    def total_collectible_cards(self) -> int:
        return len(self.collectible_cards)
```

- [ ] **Step 2: Create `stonereader/models/deck.py`**

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

    def total_cards(self) -> int:
        return sum(count for _, count in self.cards)

    def average_cost(self) -> float:
        if not self.cards:
            return 0.0
        total_cost = sum(card.cost * count for card, count in self.cards)
        total_cards = self.total_cards()
        return total_cost / total_cards if total_cards > 0 else 0.0

    def cards_by_cost(self) -> Dict[int, List[Tuple[Card, int]]]:
        cost_groups: Dict[int, List[Tuple[Card, int]]] = {}
        for card, count in self.cards:
            cost_groups.setdefault(card.cost, []).append((card, count))
        return cost_groups

    @property
    def total_dust_cost(self) -> int:
        dust_costs = {
            "COMMON": 40,
            "RARE": 100,
            "EPIC": 400,
            "LEGENDARY": 1600,
        }
        return sum(
            dust_costs.get(card.rarity, 0) * count for card, count in self.cards
        )

    @classmethod
    def from_deckstring(
        cls, deckstring: str, card_db: CardDatabase, name: str = "Imported Deck"
    ) -> "Deck":
        cards_data, heroes_data, format_data, _ = deckstrings.parse_deckstring(
            deckstring
        )
        cards = []
        missing_cards = []
        for dbf_id, count in cards_data:
            card = card_db.get_card_by_dbf_id(dbf_id)
            if card:
                cards.append((card, count))
            else:
                missing_cards.append(dbf_id)
        if missing_cards:
            raise ValueError(f"Missing cards with DBF IDs: {missing_cards}")
        hero_class = "NEUTRAL"
        if heroes_data:
            hero_card = card_db.get_card_by_dbf_id(heroes_data[0])
            if hero_card:
                hero_class = hero_card.card_class
        format_name = "Unknown"
        if format_data:
            format_name = "Standard" if format_data == 2 else "Wild"
        return cls(
            name=name,
            format=format_name,
            cards=tuple(cards),
            hero_class=hero_class,
            deckstring=deckstring,
        )
```

- [ ] **Step 3: Create `stonereader/models/game_state.py`**

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from stonereader.models.card import Card


@dataclass(frozen=True)
class Hero:
    """Represents a Hearthstone hero."""

    id: str
    name: str
    health: int
    armor: int
    hero_power: str


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


@dataclass(frozen=True)
class GameState:
    """Represents a moment in game time."""

    turn: int
    active_player_id: int
    player_board: Tuple[GameEntity, ...]
    opponent_board: Tuple[GameEntity, ...]
    player_hand: Tuple[GameEntity, ...]
    opponent_hand: Tuple[Optional[GameEntity], ...]
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
```

- [ ] **Step 4: Create `stonereader/models/replay.py`**

```python
from dataclasses import dataclass
from typing import Tuple

from stonereader.models.game_state import GameState


@dataclass(frozen=True)
class ReplayState:
    """Complete game timeline as ordered sequence of GameState snapshots."""

    states: Tuple[GameState, ...]
    friendly_player_id: int
```

- [ ] **Step 5: Create `stonereader/models/__init__.py`**

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

- [ ] **Step 6: Delete `stonereader/models.py`**

```bash
rm stonereader/models.py
```

- [ ] **Step 7: Update `stonereader/presenters.py` imports temporarily**

The old `presenters.py` imports `from models import ...`. Update it to `from stonereader.models import ...` so it doesn't break before we replace it:

```python
from stonereader.models import Card, CardDatabase, Deck, GameState
```

- [ ] **Step 8: Verify the refactor works**

Run: `uv run python -c "from stonereader.models import Card, CardDatabase, Deck, Hero, GameEntity, GameState, ReplayState; print('OK')"`
Expected: `OK`

Run: `uv run pyright stonereader/models/`
Expected: 0 errors (warnings are acceptable)

- [ ] **Step 9: Commit**

```bash
git add stonereader/models/ stonereader/presenters.py
git rm stonereader/models.py
git commit -m "Split models.py into models/ package"
```

---

### Task 3: Create SpeechService

**Files:**
- Create: `stonereader/speech_service.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_speech_service.py`

- [ ] **Step 1: Write the tests**

Create `tests/conftest.py`:

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

    @property
    def last_speech(self) -> str:
        return self.spoken[-1][0] if self.spoken else ""
```

Create `tests/__init__.py` (empty file).

Create `tests/test_speech_service.py`:

```python
from stonereader.speech_service import SpeechService


def test_speech_service_creates_without_error():
    svc = SpeechService()
    assert svc is not None


def test_speak_does_not_raise(capsys):
    svc = SpeechService()
    svc.speak("hello")
    # On CI/dev without a screen reader, falls back to stdout
    captured = capsys.readouterr()
    assert "hello" in captured.out


def test_speak_queued_does_not_interrupt(capsys):
    svc = SpeechService()
    svc.speak_queued("queued text")
    captured = capsys.readouterr()
    assert "queued text" in captured.out


def test_speak_interrupt_default_is_true(capsys):
    svc = SpeechService()
    svc.speak("first")
    svc.speak("second")
    captured = capsys.readouterr()
    assert "first" in captured.out
    assert "second" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_speech_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stonereader.speech_service'`

- [ ] **Step 3: Create `stonereader/speech_service.py`**

```python
"""Screen reader output via accessible_output2 with stdout fallback.

accessible_output2.Auto() handles detection across NVDA, JAWS, Windows
Narrator, and others. If import fails (package absent or incompatible),
all output goes to stdout (ref: DL-007).
"""

from __future__ import annotations


class SpeechService:
    """Screen reader output.

    Wraps accessible_output2.Auto for cross-reader output. Falls back to
    stdout when no screen reader is available.
    """

    def __init__(self) -> None:
        self._use_stdout = False
        try:
            from accessible_output2.outputs.auto import Auto

            self._output = Auto()
        except Exception:
            self._use_stdout = True
            self._output = None

    def speak(self, text: str, interrupt: bool = True) -> None:
        """Send text to the screen reader."""
        if self._use_stdout or self._output is None:
            print(text)
            return
        try:
            self._output.speak(text, interrupt=interrupt)
        except Exception:
            print(text)

    def speak_queued(self, text: str) -> None:
        """Queue text after current speech without interrupting."""
        self.speak(text, interrupt=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_speech_service.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add stonereader/speech_service.py tests/
git commit -m "Add SpeechService with accessible_output2 and stdout fallback"
```

---

### Task 4: Create InputLayer

**Files:**
- Create: `stonereader/input_layer.py`
- Create: `tests/test_input_layer.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_input_layer.py`:

```python
import wx

from stonereader.input_layer import InputLayer, _key_spec_from_event

# wx.App must exist before creating any wx objects
_app = wx.App(False)


def _make_key_event(keycode: int, shift: bool = False, ctrl: bool = False, alt: bool = False) -> wx.KeyEvent:
    """Create a wx.KeyEvent with the given keycode and modifiers."""
    event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    event.SetId(keycode)
    # Use UnicodeKey for character keys, KeyCode for all
    event.m_keyCode = keycode
    event.m_shiftDown = shift
    event.m_controlDown = ctrl
    event.m_altDown = alt
    return event


def test_key_spec_arrow_keys():
    assert _key_spec_from_event(_make_key_event(wx.WXK_LEFT)) == "left"
    assert _key_spec_from_event(_make_key_event(wx.WXK_RIGHT)) == "right"
    assert _key_spec_from_event(_make_key_event(wx.WXK_UP)) == "up"
    assert _key_spec_from_event(_make_key_event(wx.WXK_DOWN)) == "down"


def test_key_spec_letter_keys():
    assert _key_spec_from_event(_make_key_event(ord("B"))) == "b"
    assert _key_spec_from_event(_make_key_event(ord("H"))) == "h"


def test_key_spec_shift_letter():
    assert _key_spec_from_event(_make_key_event(ord("T"), shift=True)) == "shift+t"


def test_key_spec_shift_arrow_not_prefixed():
    assert _key_spec_from_event(_make_key_event(wx.WXK_UP, shift=True)) == "up"


def test_key_spec_enter():
    assert _key_spec_from_event(_make_key_event(wx.WXK_RETURN)) == "enter"
    assert _key_spec_from_event(_make_key_event(wx.WXK_NUMPAD_ENTER)) == "enter"


def test_key_spec_escape():
    assert _key_spec_from_event(_make_key_event(wx.WXK_ESCAPE)) == "escape"


def test_key_spec_unmapped_returns_empty():
    assert _key_spec_from_event(_make_key_event(wx.WXK_F1)) == ""


def test_input_layer_calls_mapped_callback():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"b": lambda: called.append("b")})
    event = _make_key_event(ord("B"))
    layer._on_char_hook(event)
    assert called == ["b"]
    frame.Destroy()


def test_input_layer_text_mode_skips_callbacks():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"b": lambda: called.append("b")})
    layer.enter_text_mode()
    event = _make_key_event(ord("B"))
    layer._on_char_hook(event)
    assert called == []
    frame.Destroy()


def test_input_layer_ctrl_always_passes_through():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"c": lambda: called.append("c")})
    event = _make_key_event(ord("C"), ctrl=True)
    layer._on_char_hook(event)
    assert called == []
    frame.Destroy()


def test_input_layer_alt_always_passes_through():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"f": lambda: called.append("f")})
    event = _make_key_event(ord("F"), alt=True)
    layer._on_char_hook(event)
    assert called == []
    frame.Destroy()


def test_activate_view_replaces_key_map():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("v1", {"b": lambda: called.append("v1")})
    layer.activate_view("v2", {"b": lambda: called.append("v2")})
    event = _make_key_event(ord("B"))
    layer._on_char_hook(event)
    assert called == ["v2"]
    frame.Destroy()


def test_activate_view_exits_text_mode():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    layer.enter_text_mode()
    assert layer._text_mode is True
    layer.activate_view("v1", {})
    assert layer._text_mode is False
    frame.Destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_input_layer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stonereader.input_layer'`

- [ ] **Step 3: Create `stonereader/input_layer.py`**

```python
"""Hotkey registration lifecycle management via wx.EVT_CHAR_HOOK.

EVT_CHAR_HOOK fires at the frame level before native control handlers run.
This is critical because NVDA/JAWS install WH_KEYBOARD_LL hooks that
intercept WM_KEYDOWN before it reaches the app, causing EVT_KEY_DOWN
and EVT_CHAR to silently fail on list/tree controls.

Key routing priority:
1. Text mode (TextCtrl focused) -> event.Skip()
2. Ctrl or Alt held -> event.Skip()
3. Key in active map -> call callback, consume key
4. Everything else -> event.Skip()
"""

from __future__ import annotations

from typing import Callable, Dict

import wx

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


def _key_spec_from_event(event: wx.KeyEvent) -> str:
    """Build a key spec string matching the format used in presenter key maps."""
    keycode = event.GetKeyCode()
    name = _KEY_NAMES.get(keycode)
    if name is None and 32 < keycode < 127:
        name = chr(keycode).lower()
    if name is None:
        return ""
    # Shift prefix for letter keys only — not arrows, enter, etc.
    if event.ShiftDown() and name not in _KEY_NAMES.values():
        name = f"shift+{name}"
    return name


class InputLayer:
    """Per-view hotkey set manager.

    Maintains one active key map at a time. Swapping views replaces the
    key map. Text mode disables all hotkey processing so keystrokes reach
    TextCtrl widgets.
    """

    def __init__(self, main_window: wx.Frame) -> None:
        self._current_key_map: Dict[str, Callable[[], None]] = {}
        self._text_mode = False
        main_window.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        main_window.Bind(wx.EVT_ACTIVATE, self._on_activate)

    def activate_view(self, name: str, key_map: Dict[str, Callable[[], None]]) -> None:
        """Replace the active key map."""
        self._current_key_map = key_map
        self._text_mode = False

    def enter_text_mode(self) -> None:
        """Disable hotkey processing so keystrokes reach TextCtrl."""
        self._text_mode = True

    def exit_text_mode(self) -> None:
        """Re-enable hotkey processing."""
        self._text_mode = False

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        # Rule 1: text mode passes everything through
        if self._text_mode:
            event.Skip()
            return
        # Rule 2: never intercept Ctrl or Alt combos
        if event.ControlDown() or event.AltDown():
            event.Skip()
            return
        # Rule 3: check active key map
        spec = _key_spec_from_event(event)
        callback = self._current_key_map.get(spec)
        if callback is not None:
            callback()
        else:
            # Rule 4: unmatched keys pass through
            event.Skip()

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        """Unstick text mode when window activates without TextCtrl focused."""
        event.Skip()
        if not self._text_mode:
            return
        window = wx.Window.FindFocus()
        if not isinstance(window, wx.TextCtrl):
            self.exit_text_mode()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_input_layer.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add stonereader/input_layer.py tests/test_input_layer.py
git commit -m "Add InputLayer with EVT_CHAR_HOOK key routing and text mode"
```

---

### Task 5: Create ZoneNavigationMixin and BasePresenter

**Files:**
- Create: `stonereader/presenters/__init__.py`
- Create: `stonereader/presenters/base.py`
- Create: `tests/test_zone_navigation.py`
- Delete: `stonereader/presenters.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_zone_navigation.py`:

```python
from typing import Any, Sequence

from tests.conftest import MockSpeechService
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin


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


def test_initial_zone_is_first():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    assert p._current_zone == "zone_a"


def test_navigate_to_zone_announces_zone_and_item():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_b", "Zone B")
    assert "Zone B" in speech.last_speech
    assert "Delta" in speech.last_speech


def test_navigate_to_zone_empty():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p._items["zone_b"] = []
    p.navigate_to_zone("zone_b", "Zone B")
    assert "empty" in speech.last_speech


def test_move_right_advances_cursor():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(1)
    assert "Bravo" in speech.last_speech
    assert "2 of 3" in speech.last_speech


def test_move_left_does_not_go_below_zero():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(-1)
    assert "Alpha" in speech.last_speech
    assert "1 of 3" in speech.last_speech


def test_move_right_does_not_go_past_end():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(1)
    p.move_in_zone(1)
    p.move_in_zone(1)  # past end
    assert "Charlie" in speech.last_speech
    assert "3 of 3" in speech.last_speech


def test_zone_cursor_persists_across_switches():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.move_in_zone(1)  # cursor on Bravo (index 1)
    p.navigate_to_zone("zone_b", "Zone B")
    p.navigate_to_zone("zone_a", "Zone A")
    assert "Bravo" in speech.last_speech


def test_detail_lines_navigates_card_details():
    from stonereader.models import Card

    speech = MockSpeechService()
    p = StubPresenter(speech)
    card = Card(
        id="TEST_001",
        dbf_id=1,
        name="Fireball",
        cost=4,
        attack=None,
        health=None,
        text="Deal 6 damage.",
        rarity="COMMON",
        card_class="CardClass.MAGE",
        card_type="SpellType.SPELL",
    )
    p._items["zone_a"] = [card]
    p._init_navigation(["zone_a"])
    p.navigate_to_zone("zone_a", "Zone A")
    # First Down reads first detail line (name)
    p.read_detail_lines(card, direction=1)
    assert "Fireball" in speech.last_speech
    # Second Down reads next line (cost)
    p.read_detail_lines(card, direction=1)
    assert "4 mana" in speech.last_speech


def test_diminishing_orienting_messages():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.handle_inapplicable_zone("b", "Full help message", "Short help")
    assert speech.last_speech == "Full help message"
    p.handle_inapplicable_zone("b", "Full help message", "Short help")
    assert speech.last_speech == "Short help"
    p.handle_inapplicable_zone("b", "Full help message", "Short help")
    # Third press: silent (no new speech)
    assert speech.last_speech == "Short help"


def test_orienting_counts_reset_on_zone_change():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.handle_inapplicable_zone("b", "Full help", "Short")
    p.handle_inapplicable_zone("b", "Full help", "Short")
    # Switch zones resets counts
    p.navigate_to_zone("zone_b", "Zone B")
    p.handle_inapplicable_zone("b", "Full help", "Short")
    assert speech.last_speech == "Full help"


def test_jump_to_position():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.jump_to_position(3)
    assert "Charlie" in speech.last_speech
    assert "3 of 3" in speech.last_speech


def test_jump_to_first_and_last():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_to_zone("zone_a", "Zone A")
    p.jump_to_last()
    assert "Charlie" in speech.last_speech
    p.jump_to_first()
    assert "Alpha" in speech.last_speech


def test_navigate_singleton_zone():
    speech = MockSpeechService()
    p = StubPresenter(speech)
    p.navigate_singleton_zone("stats", "Statistics", "Win rate: 55%")
    assert "Statistics: Win rate: 55%" in speech.last_speech
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_zone_navigation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stonereader.presenters.base'`

- [ ] **Step 3: Create `stonereader/presenters/__init__.py`**

Empty file:

```python
```

- [ ] **Step 4: Create `stonereader/presenters/base.py`**

```python
"""Base presenter and zone navigation mixin.

ZoneNavigationMixin provides cursor-per-zone navigation shared across all
presenters. Zone keys are always global (never modal). Each zone maintains
an independent cursor that persists across zone switches (DL-001).

BasePresenter holds the SpeechService reference and provides an announce()
convenience method.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from stonereader.speech_service import SpeechService


class BasePresenter:
    """Base class for all presenters."""

    def __init__(self, speech: SpeechService) -> None:
        self._speech = speech

    def announce(self, text: str) -> None:
        self._speech.speak(text)

    def get_key_map(self) -> Dict[str, Callable[[], None]]:
        """Return the key map for this presenter. Subclasses must override."""
        return {}


class ZoneNavigationMixin:
    """Cursor-per-zone navigation.

    Diminishing orienting messages (DL-008): handle_inapplicable_zone tracks
    per-key press counts. 1st = full help, 2nd = short, 3rd+ = silent.
    Counts reset on zone change.
    """

    _speech: SpeechService

    def _init_navigation(self, zones: List[str]) -> None:
        self._current_zone = zones[0] if zones else ""
        self._zone_cursors: Dict[str, int] = {z: 0 for z in zones}
        self._orienting_counts: Dict[str, int] = {}
        self._detail_cursor: int = -1

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        """Return item sequence for zone. Subclasses must override."""
        raise NotImplementedError

    def _format_item_speech(self, item: Any, position: int, total: int) -> str:
        prefix = f"{position} of {total}: "
        if item is None:
            return prefix + "Unknown card"
        if isinstance(item, tuple) and len(item) == 2:
            card, count = item
            name = getattr(card, "name", str(card))
            return prefix + f"{name} x{count}"
        name = getattr(item, "name", str(item))
        return prefix + name

    def navigate_to_zone(self, zone_name: str, zone_label: str) -> None:
        self._current_zone = zone_name
        self._detail_cursor = -1
        self._orienting_counts.clear()
        items = self.get_zone_items(zone_name)
        if not items:
            self._speech.speak(f"{zone_label}: empty")
            return
        cursor = self._zone_cursors.get(zone_name, 0)
        cursor = max(0, min(cursor, len(items) - 1))
        self._zone_cursors[zone_name] = cursor
        text = f"{zone_label}, {self._format_item_speech(items[cursor], cursor + 1, len(items))}"
        self._speech.speak(text)

    def navigate_singleton_zone(
        self, zone_name: str, zone_label: str, content: str
    ) -> None:
        self._current_zone = zone_name
        self._detail_cursor = -1
        self._orienting_counts.clear()
        self._speech.speak(f"{zone_label}: {content}")

    def move_in_zone(self, delta: int) -> None:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        if not items:
            self._speech.speak(f"{zone}: empty")
            return
        cursor = self._zone_cursors.get(zone, 0) + delta
        cursor = max(0, min(cursor, len(items) - 1))
        self._zone_cursors[zone] = cursor
        self._detail_cursor = -1
        self._speech.speak(
            self._format_item_speech(items[cursor], cursor + 1, len(items))
        )

    def jump_to_position(self, pos: int) -> None:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        if not items:
            self._speech.speak(f"{zone}: empty")
            return
        cursor = max(0, min(pos - 1, len(items) - 1))
        self._zone_cursors[zone] = cursor
        self._detail_cursor = -1
        self._speech.speak(
            self._format_item_speech(items[cursor], cursor + 1, len(items))
        )

    def jump_to_first(self) -> None:
        self.jump_to_position(1)

    def jump_to_last(self) -> None:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        self.jump_to_position(len(items))

    def _current_item(self) -> Optional[Any]:
        zone = self._current_zone
        items = self.get_zone_items(zone)
        if not items:
            return None
        cursor = self._zone_cursors.get(zone, 0)
        if cursor >= len(items):
            return None
        return items[cursor]

    def _extract_card(self, item: Any) -> Any:
        """Extract a Card from various item types."""
        from stonereader.models.card import Card
        from stonereader.models.game_state import GameEntity

        if isinstance(item, Card):
            return item
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], Card):
            return item[0]
        if isinstance(item, GameEntity) and item.base_card is not None:
            return item.base_card
        return None

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

    def handle_inapplicable_zone(
        self, key: str, full_message: str, short_message: str
    ) -> None:
        count = self._orienting_counts.get(key, 0) + 1
        self._orienting_counts[key] = count
        if count == 1:
            self._speech.speak(full_message)
        elif count == 2:
            self._speech.speak(short_message)
```

- [ ] **Step 5: Delete old `stonereader/presenters.py`**

```bash
rm stonereader/presenters.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_zone_navigation.py -v`
Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add stonereader/presenters/ tests/test_zone_navigation.py
git rm stonereader/presenters.py
git commit -m "Add ZoneNavigationMixin and BasePresenter"
```

---

### Task 6: Create database layer

**Files:**
- Create: `stonereader/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_db.py`:

```python
import sqlite3

from stonereader.db import get_connection, init_db, get_schema_version


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


def test_schema_version_starts_at_one(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    assert get_schema_version(conn) == 1
    conn.close()


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    init_db(conn)  # second call should not raise or duplicate
    assert get_schema_version(conn) == 1
    conn.close()


def test_decks_table_schema(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    conn.execute(
        "INSERT INTO decks (name, hero_class, format, deckstring) VALUES (?, ?, ?, ?)",
        ("Test Deck", "MAGE", "Standard", "AAECAf0EAA=="),
    )
    row = conn.execute("SELECT * FROM decks").fetchone()
    assert row is not None
    conn.close()


def test_games_table_schema(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    init_db(conn)
    conn.execute(
        """INSERT INTO games
        (deck_name, hero_class, opponent_class, result, turns, duration_seconds, played_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        ("Test Deck", "MAGE", "WARRIOR", "WIN", 10, 300),
    )
    row = conn.execute("SELECT * FROM games").fetchone()
    assert row is not None
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stonereader.db'`

- [ ] **Step 3: Create `stonereader/db.py`**

```python
"""SQLite database for persisting decks and game history."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    hero_class TEXT NOT NULL,
    format TEXT NOT NULL,
    deckstring TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_name TEXT NOT NULL,
    hero_class TEXT NOT NULL,
    opponent_class TEXT NOT NULL,
    result TEXT NOT NULL,
    turns INTEGER NOT NULL,
    duration_seconds INTEGER,
    played_at TIMESTAMP NOT NULL
);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection. Defaults to ~/.stonereader/stonereader.db."""
    if db_path is None:
        data_dir = Path.home() / ".stonereader"
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / "stonereader.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if not initialized."""
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist. Idempotent."""
    version = get_schema_version(conn)
    if version >= 1:
        return
    conn.executescript(_SCHEMA_V1)
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add stonereader/db.py tests/test_db.py
git commit -m "Add SQLite database layer with schema migrations"
```

---

### Task 7: Create base view helpers and app shell

**Files:**
- Create: `stonereader/views/__init__.py`
- Create: `stonereader/views/base.py`
- Create: `stonereader/app.py`
- Create: `stonereader/__main__.py`
- Delete: `stonereader/views.py`

- [ ] **Step 1: Create `stonereader/views/__init__.py`**

Empty file:

```python
```

- [ ] **Step 2: Create `stonereader/views/base.py`**

```python
"""Shared view helpers and base widgets.

Text mode lifecycle: bind EVT_SET_FOCUS / EVT_KILL_FOCUS on TextCtrl widgets
to enter/exit text mode on the InputLayer. This ensures hotkeys are suppressed
while typing.
"""

from __future__ import annotations

import wx

from stonereader.input_layer import InputLayer


def bind_text_mode(ctrl: wx.TextCtrl, input_layer: InputLayer) -> None:
    """Bind focus events on a TextCtrl to enter/exit text mode."""
    ctrl.Bind(wx.EVT_SET_FOCUS, lambda evt: (_enter_text(input_layer), evt.Skip()))
    ctrl.Bind(wx.EVT_KILL_FOCUS, lambda evt: (_exit_text(input_layer), evt.Skip()))


def _enter_text(input_layer: InputLayer) -> None:
    input_layer.enter_text_mode()


def _exit_text(input_layer: InputLayer) -> None:
    input_layer.exit_text_mode()


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

- [ ] **Step 3: Create `stonereader/app.py`**

```python
"""Main application window and wx.App setup."""

from __future__ import annotations

import wx

from stonereader.db import get_connection, init_db
from stonereader.input_layer import InputLayer
from stonereader.speech_service import SpeechService


class MainWindow(wx.Frame):
    """Top-level window with Notebook tabs, status bar, and accelerator table."""

    def __init__(self) -> None:
        super().__init__(None, title="StoneReader", size=(800, 600))

        self._speech = SpeechService()
        self._input_layer = InputLayer(self)

        # Database
        self._db_conn = get_connection()
        init_db(self._db_conn)

        # Status bar — readable via NVDA+End / JAWS Insert+B
        self.CreateStatusBar()
        self.SetStatusText("StoneReader ready")

        # Notebook (tabs added by feature slices)
        self._notebook = wx.Notebook(self)
        self._notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)

        # Track presenters and focus targets per tab
        self._tab_presenters: list = []
        self._tab_focus_targets: list[wx.Window] = []
        self._tab_names: list[str] = []

        # Main sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

        # Accelerator table for standard shortcuts
        accel_entries = [
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("Q"), wx.ID_EXIT),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self._on_quit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    @property
    def speech(self) -> SpeechService:
        return self._speech

    @property
    def input_layer(self) -> InputLayer:
        return self._input_layer

    @property
    def notebook(self) -> wx.Notebook:
        return self._notebook

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

    def _on_page_changed(self, event: wx.BookCtrlEvent) -> None:
        page = event.GetSelection()
        if 0 <= page < len(self._tab_presenters):
            presenter = self._tab_presenters[page]
            key_map = presenter.get_key_map() if hasattr(presenter, "get_key_map") else {}
            self._input_layer.activate_view(self._tab_names[page], key_map)
            target = self._tab_focus_targets[page]
            wx.CallAfter(target.SetFocus)
        event.Skip()

    def _on_quit(self, event: wx.CommandEvent) -> None:
        self.Close()

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._db_conn.close()
        self.Destroy()


class StoneReaderApp(wx.App):
    """Application entry point."""

    def OnInit(self) -> bool:
        self._frame = MainWindow()
        self._frame.Show()
        return True
```

- [ ] **Step 4: Create `stonereader/__main__.py`**

```python
"""StoneReader entry point."""

from stonereader.app import StoneReaderApp


def main() -> None:
    app = StoneReaderApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Delete old `stonereader/views.py`**

```bash
rm stonereader/views.py
```

- [ ] **Step 6: Verify the app launches without errors**

Run: `uv run python -c "import stonereader.app; import stonereader.views.base; print('OK')"`
Expected: `OK`

Run: `uv run pyright stonereader/app.py stonereader/views/base.py stonereader/__main__.py`
Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add stonereader/app.py stonereader/__main__.py stonereader/views/
git rm stonereader/views.py
git commit -m "Add app shell, base view helpers, and entry point"
```

---

### Task 8: Update internal documentation

**Files:**
- Modify: `stonereader/README.md`
- Modify: `stonereader/CLAUDE.md`

- [ ] **Step 1: Update `stonereader/README.md`**

Replace the architecture diagram and design decisions to reflect the new structure:

- Remove references to `keyboard_handler` and `WXKeyboardHandler` (DL-003, DL-005)
- Update the architecture diagram to show the `models/`, `presenters/`, `views/` packages
- Update DL-004 to specify `to_speech_text()` returns name only (no verbosity parameter)
- Update DL-005 to describe `EVT_CHAR_HOOK` with Ctrl/Alt passthrough and text mode flag (not `_unregister_all()`)
- Add note about Ctrl/Alt passthrough rule
- Add note about `wx.WANTS_CHARS` for speech-driven panels

- [ ] **Step 2: Update `stonereader/CLAUDE.md`**

Update the file table to reflect the new package structure:

```markdown
# stonereader/

## Files

| File                | What                                                  | When to read                                     |
| ------------------- | ----------------------------------------------------- | ------------------------------------------------ |
| `README.md`         | Architecture, design decisions, invariants            | Understanding why the code is structured this way |
| `speech_service.py` | SpeechService: accessible_output2 wrapper             | Modifying speech output, debugging screen reader |
| `input_layer.py`    | InputLayer: EVT_CHAR_HOOK key routing, text mode      | Changing key routing, debugging text mode         |
| `app.py`            | MainWindow, StoneReaderApp, Notebook shell            | Adding tabs, modifying app structure              |
| `__main__.py`       | App entry point                                       | Changing startup behavior                         |
| `db.py`             | SQLite connection, schema, migrations                 | Adding tables, changing persistence               |

## Subdirectories

| Directory     | What                                             | When to read                          |
| ------------- | ------------------------------------------------ | ------------------------------------- |
| `models/`     | Domain models: Card, Deck, GameState, etc.       | Changing data structures              |
| `presenters/` | Presenters: ZoneNavigationMixin, BasePresenter   | Implementing feature presenters       |
| `views/`      | View helpers: text mode binding, labeled widgets | Building feature panels               |
```

- [ ] **Step 3: Commit**

```bash
git add stonereader/README.md stonereader/CLAUDE.md
git commit -m "Update docs for new package structure and design decisions"
```

---

### Task 9: Run full test suite and type check

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass (speech_service, input_layer, zone_navigation, db)

- [ ] **Step 2: Run type checker**

Run: `uv run pyright stonereader/`
Expected: 0 errors (warnings acceptable)

- [ ] **Step 3: Run linter and formatter**

Run: `uv run ruff check .`
Run: `uv run ruff format --check .`
Expected: No errors. If formatting issues, run `uv run ruff format .` and commit.

- [ ] **Step 4: Verify app can be imported end-to-end**

Run: `uv run python -c "from stonereader.models import Card, Deck, GameState, Hero, ReplayState; from stonereader.speech_service import SpeechService; from stonereader.input_layer import InputLayer; from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin; from stonereader.db import init_db, get_connection; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "Fix lint and type check issues"
```
