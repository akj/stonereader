# Technology Stack

**Analysis Date:** 2026-04-14

## Languages

**Primary:**
- Python 3.12+ - All application code, models, presenters, views, database schema, testing

## Runtime

**Environment:**
- Python 3.12.3

**Package Manager:**
- uv (modern Python package manager)
- Lockfile: `uv.lock` (present, 44.9 KB, pinned versions)

## Frameworks

**Core:**
- wxPython 4.2.5 - Cross-platform GUI framework for desktop application (`stonereader/app.py`, `stonereader/views/`, `stonereader/input_layer.py`)

**Game Data:**
- hearthstone 9.17.0 - Hearthstone card definitions, enum parsing, deckstring decoding (`stonereader/models/card.py`, `stonereader/models/deck.py`)
- hearthstone-data 223542.1 - Card XML database for hearthstone library

**Accessibility:**
- accessible-output2 0.17 - Screen reader abstraction layer (NVDA, JAWS, Narrator support) (`stonereader/speech_service.py`)

**Testing:**
- pytest 9.0.3 - Test runner and framework (`tests/conftest.py`, test files)
- pyright 1.1.402 - Static type checker
- ruff 0.12.2 - Linter and code formatter

## Key Dependencies

**Critical:**
- wxPython 4.2.5 - GUI framework; essential for the desktop application
- hearthstone 9.17.0 - Card library and game mechanics; required for card data access
- accessible-output2 0.17 - Screen reader integration; required for WCAG AA compliance

**Supporting:**
- requests 2.32.4 - HTTP client library (transitive, used by hearthstone for updates)
- urllib3 2.5.0 - URL handling (transitive)
- certifi 2025.6.15 - SSL certificate validation (transitive)
- charset-normalizer 3.4.2 - Character encoding detection (transitive)

**Platform-Specific:**
- pywin32 311 - Windows-only; provides native Windows APIs for accessible-output2 on Windows
- appscript 1.4.0 - macOS-only; provides native macOS APIs for accessible-output2 on macOS
- libloader 1.4.3 - Dependency of accessible-output2 for loading native libraries
- platform-utils 1.6.2 - Platform detection and utilities
- lxml 6.0.2 - XML parsing library (used by appscript on non-Windows)

## Configuration

**Environment:**
- No `.env` file required or used
- No environment variables required for basic operation
- Database path: `~/.stonereader/stonereader.db` (created at runtime)

**Build:**
- `pyproject.toml` - Package metadata, dependencies, Python version requirement (>=3.12)

## Platform Requirements

**Development:**
- Python 3.12 or higher
- uv package manager
- Working wxPython installation (requires native GUI libraries per OS)

**Production:**
- Python 3.12 or higher
- Windows, macOS, or Linux with GUI support
- For accessibility: Screen reader installed (NVDA on Windows, VoiceOver on macOS, etc.)
- wxPython native dependencies (GTK on Linux, Cocoa on macOS, native Windows APIs)

## Build & Development Commands

Located in `CLAUDE.md`:

```bash
uv sync                    # Install dependencies
uv run pytest tests/ -v    # Run tests
uv run pyright             # Type check
uv run ruff check .        # Lint
uv run ruff format .       # Format
```

---

*Stack analysis: 2026-04-14*
