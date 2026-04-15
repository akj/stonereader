# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services

**Hearthstone Game Data:**
- hearthstone 9.17.0 library - Card definitions, card XML parsing, game enums
  - SDK/Client: `hearthstone` package (PyPI)
  - Usage: `stonereader/models/card.py` (Card.from_cardxml), `stonereader/models/deck.py` (deckstring decoding)
  - No authentication required (offline library)

**Screen Reader Integration:**
- accessible-output2 0.17 - Cross-platform screen reader abstraction
  - SDK/Client: `accessible-output2` package (PyPI)
  - Supported readers: NVDA (Windows), JAWS (Windows), Windows Narrator, VoiceOver (macOS), others
  - Usage: `stonereader/speech_service.py` - SpeechService wraps accessible_output2.Auto for fallback to stdout if no reader available
  - No credentials required

## Data Storage

**Databases:**
- SQLite3 (stdlib) - Persistent deck and game history storage
  - Connection: `stonereader/db.py` - get_connection() defaults to `~/.stonereader/stonereader.db`
  - Client: Python's built-in sqlite3 module
  - Schema: Two tables (decks, games) defined in _SCHEMA_V1 with schema_version tracking
  - No external database server required (file-based)

**File Storage:**
- Local filesystem only
  - User data directory: `~/.stonereader/` (created at runtime)
  - Database file: `~/.stonereader/stonereader.db`
  - No cloud storage integration

**Caching:**
- None - Card data loaded from hearthstone-data package at startup

## Authentication & Identity

**Auth Provider:**
- None - Application requires no user authentication
- No login system implemented
- Single-user desktop application

## Monitoring & Observability

**Error Tracking:**
- None configured

**Logs:**
- stdout only (via SpeechService fallback)
- Screen reader speech output for accessibility alerts
- No persistent log files

## CI/CD & Deployment

**Hosting:**
- Local desktop application only
- No server-side deployment

**CI Pipeline:**
- None detected (no GitHub Actions, pre-commit hooks, or CI config files)

## Environment Configuration

**Required env vars:**
- None required for basic operation

**Secrets location:**
- None - Application uses no API keys, tokens, or secrets

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None (no external API calls initiated by the application)

## Network Access

**Outbound:**
- None by default
- The hearthstone library may periodically check for card database updates via requests library, but this is optional and not required for offline operation

## Data Formats

**Card Data Source:**
- Hearthstone card XML files (bundled with hearthstone-data package)
- Format: Hearthstone cardxml.zip structure

**Deck Format:**
- Hearthstone deckstrings - Standard base64-encoded deck format
- Parsed by: `hearthstone.deckstrings` module in `stonereader/models/deck.py`

**Replay Format:**
- Hearthstone replay files (planned feature, not yet implemented)
- Specification: Hearthstone Power.log replay format

---

*Integration audit: 2026-04-14*
