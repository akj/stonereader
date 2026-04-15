# Coding Conventions

**Analysis Date:** 2026-04-14

## Naming Patterns

**Files:**
- `snake_case.py` — All Python modules use snake_case
- Test files use `test_*.py` pattern — e.g., `test_card_browser.py`, `test_input_layer.py`
- Module organization by domain: `models/`, `presenters/`, `views/`, `tests/`

**Functions:**
- `snake_case()` for all functions and methods
- Callbacks and lambdas use `_on_event_name()` pattern for event handlers
- Private methods prefixed with single underscore: `_private_method()`
- Speech output methods use present imperative: `announce()`, `speak()`, `navigate_to_zone()`

**Variables:**
- `snake_case` for all variables and instance attributes
- Private attributes prefixed with underscore: `self._speech`, `self._current_zone`
- Type-annotated parameters and return values throughout (Python 3.12+)

**Types:**
- PascalCase for classes: `Card`, `CardDatabase`, `GameEntity`, `GameState`
- Dataclasses use frozen pattern with `@dataclass(frozen=True)` for immutable models
- Type hints use `Optional[Type]`, `List[Type]`, `Dict[K, V]`, `Tuple[T, ...]` (compatible with Python 3.12)

## Code Style

**Formatting:**
- Tool: Ruff (via `uv run ruff format .`)
- Line length: default (88 characters via ruff)
- Indentation: 4 spaces
- All checks pass via `uv run ruff check .` — no violations in codebase

**Linting:**
- Tool: Ruff (via `uv run ruff check .`)
- Configuration: Default ruff rules, no custom rule file in project
- Type checking: pyright (via `uv run pyright`)
- Import sorting: Ruff handles automatically
- No E501 (line-length) violations — lines naturally fit within ruff's limits

**Docstring Style:**
- Module-level docstrings present on all files
- Class docstrings: One-line summary followed by blank line and detailed explanation
- Method docstrings: Present for public methods, especially on base classes
- Format: Google-style docstrings with parameter and return type documentation
- Example from `card.py`:
  ```python
  def detail_lines(self) -> list[str]:
      """Return ordered detail lines for Up/Down inspection.

      Order matches HearthstoneAccess convention:
      name, cost, runes (DK), stats, text, spell school, type,
      rarity, set, flavor, artist.
      """
  ```

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first when needed)
2. Standard library: `import re`, `import sqlite3`, `import wx`
3. Third-party: `from hearthstone import deckstrings`
4. Local: `from stonereader.models.card import Card`

**Path Aliases:**
- No aliases configured — imports use full paths from package root
- Absolute imports always used: `from stonereader.models.card import Card`
- Never use relative imports (no `from . import` or `from .. import`)

**Example from `card.py`:**
```python
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from hearthstone.cardxml import load
```

## Error Handling

**Patterns:**
- Try/except blocks catch specific exceptions at integration boundaries
- Silent fallback common in `SpeechService` — exceptions logged to stdout instead of crashing
- Database operations wrapped with exception handling (see `db.py`)
- Presenter methods validate inputs and return `None` for invalid states rather than raising
- Example from `speech_service.py`:
  ```python
  try:
      from accessible_output2.outputs.auto import Auto
      candidate = Auto()
      if candidate.get_first_available_output() is None:
          self._use_stdout = True
      else:
          self._output = candidate
  except Exception:
      self._use_stdout = True
      self._output = None
  ```

## Logging

**Framework:** No explicit logging library — output uses `print()` for development/testing

**Pattern from `speech_service.py`:**
- On screen reader failure or missing accessible_output2, fallback to `print(text)`
- Captured by `capsys` fixture in pytest for verification
- Example test in `test_speech_service.py`:
  ```python
  def test_speak_does_not_raise(capsys):
      svc = SpeechService()
      svc.speak("hello")
      captured = capsys.readouterr()
      assert "hello" in captured.out
  ```

## Comments

**When to Comment:**
- Explain *why* not *what* — the code shows what it does
- Document non-obvious design decisions and algorithms
- Justify workarounds or WCAG accessibility requirements
- Reference accessibility standards (e.g., `DL-004`, `DL-007`, `DL-008` in comments)

**Pattern from `input_layer.py`:**
```python
"""Hotkey registration lifecycle management via wx.EVT_CHAR_HOOK.

EVT_CHAR_HOOK fires at the frame level before native control handlers run.
This is critical because NVDA/JAWS install WH_KEYBOARD_LL hooks that
intercept WM_KEYDOWN before it reaches the app, causing EVT_KEY_DOWN
and EVT_CHAR to silently fail on list/tree controls.
"""
```

## Function Design

**Size:** Functions are compact, typically 5-30 lines

**Parameters:**
- Explicit parameters always used — no *args or **kwargs in method signatures
- Type hints required: `def search(self, query: str) -> None:`
- Optional parameters with defaults: `def speak(self, text: str, interrupt: bool = True) -> None:`

**Return Values:**
- Explicit return statements
- Return `None` for void operations: `def navigate_to_zone(self, zone_name: str, zone_label: str) -> None:`
- Return tuples for multiple values: `Tuple[Tuple[Card, int], ...]` in `Deck.cards`
- Return empty list rather than `None` for empty results: see `CardBrowserPresenter.get_zone_items()`

**Example from `presenters/base.py`:**
```python
def move_in_zone(self, delta: int) -> None:
    zone = self._current_zone
    items = self.get_zone_items(zone)
    if not items:
        self._speech.speak(f"{zone}: empty")
        return
    cursor = self._zone_cursors.get(zone, 0) + delta
    cursor = max(0, min(cursor, len(items) - 1))
    self._zone_cursors[zone] = cursor
    self._detail_cursor = 0
    self._speech.speak(
        self._format_item_speech(items[cursor], cursor + 1, len(items))
    )
```

## Module Design

**Exports:**
- `__all__` list present in package `__init__.py` files
- Example from `models/__init__.py`:
  ```python
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

**Barrel Files:**
- Package init files (`__init__.py`) act as barrels, re-exporting public classes
- Consumer imports: `from stonereader.models import Card, Deck`
- Implementation imports use specific submodule: `from stonereader.models.card import Card` (within module)

## Data Structures

**Frozen Dataclasses:**
- All game state models use `@dataclass(frozen=True)` — immutable by design
- Never mutate instances; construct new ones instead
- Example `Card`, `GameState`, `GameEntity`, `Deck`, `Hero` — all frozen

**Patterns from models:**
```python
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
    spell_school: str = ""
    flavor_text: str = ""
    artist: str = ""
    rune_blood: int = 0
    rune_frost: int = 0
    rune_unholy: int = 0
    tags: Dict[str, Any] = field(default_factory=dict)
```

## Presenter Patterns

**BasePresenter:**
- All presenters inherit from `BasePresenter` in `stonereader/presenters/base.py`
- `__init__` stores `SpeechService` as `self._speech`
- Implement `get_key_map()` returning `Dict[str, Callable[[], None]]`
- Call `self._speech.speak()` for announcements, never print directly

**ZoneNavigationMixin:**
- Presenters managing multiple zones inherit `ZoneNavigationMixin`
- Call `self._init_navigation(["zone1", "zone2"])` in `__init__`
- Implement `get_zone_items(zone_name: str) -> Sequence[Any]`
- Use `navigate_to_zone()`, `move_in_zone()`, `jump_to_first()` for navigation
- Each zone maintains independent cursor via `self._zone_cursors`
- Detail inspection uses `read_detail_lines(item, direction=1)`

**Example from `card_browser.py`:**
```python
class CardBrowserPresenter(ZoneNavigationMixin, BasePresenter):
    def __init__(self, speech: SpeechService, card_db: CardDatabase) -> None:
        super().__init__(speech)
        self._card_db = card_db
        self._results: list[Card] = sorted(
            card_db.collectible_cards, key=lambda c: c.name
        )
        self._init_navigation([_RESULTS_ZONE])
        self._on_state_changed: Callable[[list[Card], int], None] | None = None
        self._on_status_changed: Callable[[str], None] | None = None

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        if zone_name == _RESULTS_ZONE:
            return self._results
        return []

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

## View Patterns

**Text Mode Binding:**
- TextCtrl widgets bind `EVT_SET_FOCUS`/`EVT_KILL_FOCUS` to toggle text mode on InputLayer
- Use helper `bind_text_mode(ctrl, input_layer)` from `views/base.py`
- Text mode disables hotkey processing so keystrokes reach TextCtrl
- Example from `views/base.py`:
  ```python
  def bind_text_mode(ctrl: wx.TextCtrl, input_layer: InputLayer) -> None:
      ctrl.Bind(wx.EVT_SET_FOCUS, lambda evt: (_enter_text(input_layer), evt.Skip()))
      ctrl.Bind(wx.EVT_KILL_FOCUS, lambda evt: (_exit_text(input_layer), evt.Skip()))
  ```

**Label Association:**
- Use `make_labeled_text_ctrl()` to create labeled controls
- Places `wx.StaticText` label *before* TextCtrl in sizer so NVDA/JAWS read label via sibling order
- Ensures screen reader association without extra ARIA (semantic HTML equivalent for wx)

---

*Convention analysis: 2026-04-14*
