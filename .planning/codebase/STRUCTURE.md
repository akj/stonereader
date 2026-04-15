# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout

```
stonereader/
├── stonereader/              # Main package
│   ├── __main__.py           # Entry point (python -m stonereader)
│   ├── app.py                # MainWindow, StoneReaderApp
│   ├── input_layer.py        # EVT_CHAR_HOOK hotkey routing
│   ├── speech_service.py     # Screen reader output wrapper
│   ├── db.py                 # SQLite schema and migrations
│   ├── models/               # Domain models (frozen dataclasses)
│   │   ├── __init__.py       # Exports all models
│   │   ├── card.py           # Card, CardDatabase
│   │   ├── deck.py           # Deck
│   │   ├── game_state.py     # Hero, GameEntity, GameState
│   │   └── replay.py         # ReplayState
│   ├── presenters/           # State and keyboard routing
│   │   ├── __init__.py       # (empty)
│   │   ├── base.py           # BasePresenter, ZoneNavigationMixin
│   │   └── card_browser.py   # CardBrowserPresenter
│   └── views/                # wxPython widgets
│       ├── __init__.py       # (empty)
│       ├── base.py           # Helper functions (make_labeled_text_ctrl, bind_text_mode)
│       └── card_browser.py   # CardBrowserPanel, _CardListCtrl
├── tests/                    # Test suite
│   ├── conftest.py           # MockSpeechService fixture
│   ├── test_card_browser.py  # CardBrowserPresenter tests
│   ├── test_db.py            # Database tests
│   ├── test_input_layer.py   # InputLayer routing tests
│   ├── test_speech_service.py # SpeechService tests
│   ├── test_zone_navigation.py # ZoneNavigationMixin tests
│   └── __init__.py           # (empty)
├── docs/                     # Documentation
│   └── superpowers/          # Design research
│       ├── specs/
│       ├── research/
│       └── plans/
├── .planning/                # GSD planning documents (generated)
│   └── codebase/             # This analysis
├── pyproject.toml            # Project metadata and dependencies
├── uv.lock                   # Locked dependency versions
├── CLAUDE.md                 # Project guidelines (this file's content)
└── README.md                 # Purpose and features
```

## Directory Purposes

**stonereader/**
- Purpose: Main package containing application logic
- Key structure: Models → Presenters → Views, plus infrastructure (app, input_layer, speech, db)

**stonereader/models/**
- Purpose: Immutable domain models for Hearthstone concepts
- Contains: Card, CardDatabase, Deck, Hero, GameEntity, GameState, ReplayState
- Key files: `card.py` (4.5KB), `deck.py`, `game_state.py`, `replay.py`
- Pattern: All models frozen dataclasses to prevent mutation

**stonereader/presenters/**
- Purpose: State management, keyboard routing, speech announcements
- Contains: Base classes and presenter implementations per feature
- Key files: `base.py` (ZoneNavigationMixin, BasePresenter), `card_browser.py`
- Pattern: Each presenter inherits BasePresenter + ZoneNavigationMixin, implements get_key_map()

**stonereader/views/**
- Purpose: wxPython widget layer — passive rendering of state
- Contains: View panels and helper functions
- Key files: `base.py` (make_labeled_text_ctrl, bind_text_mode), `card_browser.py` (CardBrowserPanel)
- Pattern: Views bind presenter callbacks, never call SpeechService

**tests/**
- Purpose: pytest test suite with 100% coverage target
- Key files: `conftest.py` (MockSpeechService), one test file per major module
- Test doubles: MockSpeechService captures speak() calls for assertion

**docs/superpowers/**
- Purpose: Design research and feature specifications
- Contains: Accessibility research, replay parser specs, deck import plans
- Not part of runtime code

**.planning/codebase/**
- Purpose: Generated architecture and structure analysis (this analysis)
- Created by: /gsd-map-codebase with arch focus

## Key File Locations

**Entry Points:**
- `stonereader/__main__.py`: Imports StoneReaderApp, calls app.MainLoop()
- `stonereader/app.py:StoneReaderApp.OnInit()`: Initializes tabs and infrastructure

**Configuration:**
- `pyproject.toml`: Python version (3.12+), dependencies (wxPython 4.2.5+, hearthstone, accessible_output2)
- No .env files (local app, no secrets)

**Core Logic:**
- `stonereader/app.py`: MainWindow frame, Notebook tabs, database lifecycle
- `stonereader/input_layer.py`: EVT_CHAR_HOOK → key_map dispatch
- `stonereader/speech_service.py`: accessible_output2 wrapper
- `stonereader/models/card.py`: CardDatabase with indexed lookups, Card.detail_lines()
- `stonereader/presenters/card_browser.py`: Search state, zone navigation, callbacks
- `stonereader/views/card_browser.py`: CardBrowserPanel, ListCtrl display sync

**Testing:**
- `tests/conftest.py`: MockSpeechService for testing
- `tests/test_*.py`: One file per feature (card_browser, db, input_layer, zone_navigation, speech_service)

## Naming Conventions

**Files:**
- `*.py`: All module files use lowercase_snake_case
- `_*`: Private/internal helpers (e.g., `_CardListCtrl`, `_read_detail_down`)
- Pattern examples: `card_browser.py`, `input_layer.py`, `card.py`

**Directories:**
- `stonereader/models/`, `stonereader/presenters/`, `stonereader/views/`: Feature-oriented groups
- `tests/`: Parallel structure with test_*.py for each module

**Classes:**
- `PascalCase` for all classes (wx convention + Python convention)
- Pattern: `CardBrowserPresenter`, `CardBrowserPanel`, `_CardListCtrl`, `InputLayer`, `SpeechService`
- Presenters end with `Presenter`
- Panels/Views end with `Panel`
- Private classes start with `_`

**Functions:**
- `snake_case` for module-level and method functions
- Pattern: `make_labeled_text_ctrl()`, `bind_text_mode()`, `_enter_text()`, `_exit_text()`
- Callbacks have `on_` prefix: `_on_search()`, `_on_page_changed()`, `_on_char_hook()`
- Private methods start with `_`

**Variables:**
- `snake_case` for all variables
- Pattern: `search_ctrl`, `_current_zone`, `_zone_cursors`, `_detail_cursor`
- No type annotations in names (use type hints instead)

**Types:**
- Frozen dataclass models: `@dataclass(frozen=True)` enforces immutability
- Dict keys are strings: `Dict[str, Callable[[], None]]` for key maps
- Optional types explicit: `Optional[Card]`, `Card | None`

## Where to Add New Code

**New Feature (e.g., Deck Manager tab):**

1. **Model layer** — `stonereader/models/`:
   - Add model classes as frozen dataclasses (e.g., `deck_state.py`)
   - Ensure all attributes are immutable (no mutable defaults)

2. **Presenter layer** — `stonereader/presenters/`:
   - Create `deck_manager.py`
   - Class signature: `class DeckManagerPresenter(ZoneNavigationMixin, BasePresenter):`
   - Implement `get_zone_items()` method (required by mixin)
   - Implement `get_key_map()` returning Dict[str, Callable[[], None]]
   - Call `self.announce()` for speech output (not `self._speech.speak()` directly)
   - Use `_notify_view()` callback to sync visual state after state changes

3. **View layer** — `stonereader/views/`:
   - Create `deck_manager.py` with `DeckManagerPanel(wx.Panel):`
   - Bind presenter callbacks: `presenter.set_on_state_changed(self._on_state_changed)`
   - Pass `input_layer` to constructor and bind text mode: `bind_text_mode(ctrl, input_layer)`
   - Keep views passive — only render, never call SpeechService

4. **App registration** — `stonereader/app.py`:
   - In `StoneReaderApp.OnInit()`, instantiate presenter and panel
   - Call `self._frame.add_tab(panel, "Deck Manager", presenter, focus_target)`

5. **Tests** — `tests/test_deck_manager.py`:
   - Use `MockSpeechService` from conftest
   - Test presenter state logic independent of views
   - Mock card_db or game_state as needed

**New Component/Module (within existing presenter):**

1. If it's a helper function → add to `stonereader/views/base.py` or presenter module
2. If it's a domain model → add to `stonereader/models/`
3. If it's a shared presenter behavior → add method to `ZoneNavigationMixin` or `BasePresenter`
4. Example: Adding card filtering → add method to `CardBrowserPresenter.filter_by_cost()`

**Utilities:**

- Shared view helpers: `stonereader/views/base.py` (e.g., `make_labeled_text_ctrl()`, `bind_text_mode()`)
- Shared presenter methods: `stonereader/presenters/base.py` (BasePresenter or ZoneNavigationMixin)
- Model helpers: Methods on model classes (e.g., `Card.to_speech_text()`, `Card.detail_lines()`)

## Special Directories

**`.planning/codebase/`:**
- Purpose: Generated GSD analysis documents
- Generated by: `/gsd-map-codebase` command with focus area
- Files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md (as applicable)
- Committed: Yes (tracked in git, regenerated when codebase changes significantly)

**`docs/superpowers/`:**
- Purpose: Design research for future features (replays, deck manager, accessibility specs)
- Committed: Yes (reference material)
- Generated: No (written by team during feature planning)

**`tests/`:**
- Purpose: pytest test suite
- Committed: Yes
- Coverage: All modules have corresponding test files
- Running: `uv run pytest tests/ -v`

**`stonereader/`:**
- Purpose: Main package directory
- __init__.py pattern: Empty in presenters/ and views/, exports all models in models/__init__.py

---

*Structure analysis: 2026-04-14*
