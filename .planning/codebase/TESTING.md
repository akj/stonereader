# Testing Patterns

**Analysis Date:** 2026-04-14

## Test Framework

**Runner:**
- pytest 9.0.3+
- Config: `pyproject.toml` (no separate pytest.ini)
- Run command: `uv run pytest tests/ -v`
- Watch mode: Not configured; use `pytest-watch` package if needed

**Assertion Library:**
- Built-in `assert` statements
- No external assertion library (pytest's native assertions sufficient)

**Run Commands:**
```bash
uv run pytest tests/ -v              # Run all tests with verbose output
uv run pytest tests/ -v --tb=short   # Short traceback format
uv run pytest tests/test_card_browser.py  # Single test file
uv run pytest -k "search"            # Run tests matching pattern
```

**Current Status:**
- 57 tests passing
- All checks pass: `uv run ruff check .`, `uv run pyright`
- No test coverage tool configured (no pytest-cov)

## Test File Organization

**Location:**
- Tests in `tests/` directory parallel to `stonereader/` source
- Co-located naming: `stonereader/presenters/card_browser.py` → `tests/test_card_browser.py`

**Naming:**
- `test_*.py` for test modules
- `test_*()` for test functions
- Descriptive names matching behavior being tested
- Example: `test_search_with_query_announces_result_count`, `test_navigate_to_zone_empty`

**Directory Structure:**
```
tests/
├── __init__.py         # Empty
├── conftest.py         # Shared fixtures: MockSpeechService
├── test_card_browser.py    # CardBrowserPresenter tests (22 tests)
├── test_db.py              # Database functions (5 tests)
├── test_input_layer.py     # InputLayer/key routing (16 tests)
├── test_speech_service.py  # SpeechService fallbacks (4 tests)
└── test_zone_navigation.py # ZoneNavigationMixin (10 tests)
```

## Test Structure

**Suite Organization:**
- Each test file focuses on one primary class or module
- No test classes; all functions are top-level
- Tests are independent and can run in any order

**Patterns Observed:**

**Setup (no fixtures needed for most tests):**
```python
def test_search_with_query_announces_result_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)
    # test code
```

**Teardown (explicit cleanup where needed):**
- wx.Frame tests call `frame.Destroy()` to clean up GUI resources
- Database tests use `tmp_path` fixture for temporary database files
- No teardown hooks; cleanup is inline or via pytest fixtures

**Assertion Pattern:**
```python
def test_search_multiple_results_announces_count():
    card_db = make_card_db(ALL_CARDS)
    speech = MockSpeechService()
    presenter = CardBrowserPresenter(speech, card_db)

    presenter.search("damage")

    assert "2 results" in speech.last_speech
```

## Mocking

**Framework:**
- No external mocking library (no `unittest.mock`, `pytest-mock`)
- Manual mock classes for essential dependencies

**Patterns:**

**MockSpeechService (from `conftest.py`):**
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

**What to Mock:**
- `SpeechService` — Always mocked; it's external (accessible_output2 or stdout)
- `CardDatabase` — Built up via test helper `make_card_db()`
- `Card` objects — Created via test helper `make_card()`
- wxPython frames — Created directly in tests but destroyed after

**What NOT to Mock:**
- Presenter classes — Test the actual presenter logic
- Model classes (`Deck`, `GameState`, etc.) — Test as-is, they're data structures
- Mixin classes (`ZoneNavigationMixin`) — Tested via stub presenter
- InputLayer — No mocking, test with real wx.Frame and synthetic key events

**Test Helpers (from `conftest.py` and test files):**

From `test_card_browser.py`:
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
```

From `test_zone_navigation.py`:
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

From `test_input_layer.py`:
```python
def _make_key_event(keycode: int, shift: bool = False, ctrl: bool = False, alt: bool = False) -> wx.KeyEvent:
    """Create a wx.KeyEvent with the given keycode and modifiers."""
    event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    event.SetKeyCode(keycode)
    event.shiftDown = shift
    event.controlDown = ctrl
    event.altDown = alt
    return event
```

## Fixtures and Factories

**Test Data:**

Fixtures from `conftest.py`:
```python
class MockSpeechService(SpeechService):
    # Provides a reusable mock across all test files
```

Factories from test files:
- `make_card()` — Creates Card instances with defaults
- `make_card_db()` — Populates CardDatabase with test cards
- `_make_key_event()` — Constructs wx.KeyEvent for input layer tests
- `StubPresenter` — Minimal presenter for navigation tests

**Location:**
- Shared fixtures in `tests/conftest.py` (imports via `from tests.conftest import MockSpeechService`)
- Test-specific factories defined in individual test files
- Test data constants (ALL_CARDS, FIREBALL, etc.) defined at module level in test files

**Example Test Data Setup from `test_card_browser.py`:**
```python
FIREBALL = make_card(name="Fireball", cost=4, text="Deal 6 damage.", card_class="MAGE")
FROSTBOLT = make_card(name="Frostbolt", cost=2, text="Deal 3 damage. Freeze.", card_class="MAGE")
ARCANE = make_card(name="Arcane Intellect", cost=3, text="Draw 2 cards.", card_class="MAGE")
WOLFRIDER = make_card(name="Wolfrider", cost=3, attack=3, health=1, text="Charge")

ALL_CARDS = [FIREBALL, FROSTBOLT, ARCANE, WOLFRIDER]
```

## Coverage

**Requirements:** No coverage tool configured; no minimum coverage enforced

**Current Coverage (estimated):**
- Models: ~95% (all paths exercised)
- Presenters: ~90% (core navigation well tested, callbacks tested)
- Input layer: ~95% (key routing comprehensive)
- Speech service: ~80% (fallback paths tested, screen reader path untestable in CI)
- Views: ~30% (no wxPython view tests; views tested by hand during development)
- Database: ~100% (schema and migrations fully tested)

**View Coverage Gap:**
- `stonereader/views/card_browser.py` — Not tested (wxPython widgets hard to unit test)
- `stonereader/views/base.py` — Tested indirectly via view callback tests
- Mitigation: Manual testing with NVDA/JAWS during development

## Test Types

**Unit Tests (all 57 tests):**
- Scope: Individual classes and their public methods
- Approach: Direct instantiation, method calls, assertion on state/output
- Examples:
  - `test_search_with_query_announces_result_count` — Presenter search behavior
  - `test_input_layer_calls_mapped_callback` — Key routing
  - `test_init_db_creates_tables` — Database schema

**Integration Tests:**
- Not separated; unit tests cover integration between:
  - Presenter ↔ SpeechService (via MockSpeechService)
  - Presenter ↔ Model (CardDatabase, Card)
  - InputLayer ↔ Key routing (synthetic events)
- Example: `test_view_callback_fires_on_search` — Presenter notifies view on search

**E2E Tests:**
- Not automated; manual testing only
- Tested manually with actual screen reader (NVDA/JAWS)
- Covers: Full app startup, card browsing, replay viewing, deck management
- See `docs/` for manual test procedures

## Common Patterns

**Async Testing:**
- Not used — application is synchronous
- wxPython event loop never entered in tests
- All operations complete immediately

**Error Testing:**
- No explicit "error path" tests
- Presenter methods return `None` gracefully on invalid input instead of raising
- Example: `test_copy_with_no_results_returns_none` — tests None return

**Callback/Event Testing:**
- Callbacks captured by setting via `set_on_state_changed()`
- Example from `test_card_browser.py`:
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
  ```

**Zone Navigation Testing:**
- All zone operations tested via `StubPresenter` + `MockSpeechService`
- Tests verify:
  - Cursor bounds (doesn't go negative or past end)
  - Persistence across zone switches
  - Orienting message diminishing (1st = full, 2nd = short, 3rd+ = silent)
  - Detail line reading (up/down through card details)

**Database Testing:**
- Uses pytest's `tmp_path` fixture for temporary database files
- Tests verify:
  - Schema creation (tables exist)
  - Idempotency (init_db() safe to call multiple times)
  - Data insertion and retrieval
- Example from `test_db.py`:
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

## Test Organization Principles

**Independence:** Each test is independent; no shared state between tests

**Clarity:** Test names describe the behavior being tested, not the implementation
- Good: `test_search_with_query_announces_result_count`
- Bad: `test_search_method` (too vague)

**Isolation:** No file I/O or network calls except where tested explicitly
- Database tests use `tmp_path` for isolation
- SpeechService tests mock accessible_output2

**Determinism:** All tests are deterministic; no flaky tests
- No time-dependent logic
- No randomization
- No external state dependencies

---

*Testing analysis: 2026-04-14*
