# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StoneReader is an accessible Hearthstone replay viewer built with Python and wxPython. It provides an accessible GUI interface for viewing cards, decks, and replays with enhanced screen reader support.

## Dependencies and Environment

- Python 3.12+ required
- Uses `uv` for package management
- Key dependencies: wxPython, hearthstone, hearthstone-data
- pyright for type checking

## Common Commands

### Development
- `uv sync` - Install dependencies
- `uv run python main.py` - Run the main application
- `uv run ruff check .` - Run linter
- `uv run ruff format .` - Format code

### Testing
- No test framework currently configured

## Architecture

The project follows a Model-View-Presenter (MVP) pattern with accessibility as a core focus:

### Core Components

**Models (`stonereader/models.py`):**
- `Card` - Hearthstone card with accessibility metadata and `to_speech_text()` method
- `Deck` - Collection of cards with format and class information
- `Hero` - Player hero with health, armor, and hero power
- `GameState` - Snapshot of game state at a specific turn

**Presenters (`stonereader/presenters.py`):**
- `CardBrowserPresenter` - Handles card search and browsing logic
- `DeckManagerPresenter` - Manages deck import/export and validation
- `ReplayViewerPresenter` - Controls replay navigation and state management

**Views (`stonereader/views.py`):**
- `MainWindow` - Main application frame with menus and navigation
- `CardBrowserPanel` - Accessible card search interface
- `DeckViewPanel` - Deck viewing and editing
- `ReplayViewerPanel` - Game replay viewer with zone-based navigation
- `AccessibleListCtrl` - Enhanced list control for screen reader support

### Key Design Patterns

- **Accessibility First**: All UI components include enhanced screen reader support
- **Zone Navigation**: Replay viewer uses keyboard shortcuts (b: player board, g: opponent board)
- **Speech-Friendly Output**: Models include `to_speech_text()` methods for different verbosity levels
- **Separation of Concerns**: Business logic in presenters, UI in views, data in models

## File Structure

```
stonereader/
├── main.py           # Application entry point
├── models.py      # Data models with accessibility features
├── presenters.py  # Business logic and data processing
└── views.py       # wxPython GUI components
```

## Development Notes

- The project is in early development with skeleton implementations
- Focus on accessibility features when implementing UI components
- Use the hearthstone library for card data and deckstring parsing
- All text output should be optimized for screen readers