# stonereader/

## Overview

Accessible Hearthstone card, deck, and replay viewer using the MVP pattern.
Models hold frozen game data. Presenters own all navigation state, speech logic,
and key-handling. Views are passive wx widgets that route focus events to
InputLayer.

## Architecture

```
CardDatabase / GameState / ReplayState  (models/)
        |
        v
ZoneNavigationMixin
  CardBrowserPresenter
  DeckManagerPresenter       (presenters/)  -- own state, key maps, speech
  ReplayViewerPresenter
        |
        v
InputLayer                                 (input_layer.py)
        |
        v
MainWindow / Notebook / Panels             (app.py, views/)
        |
        v
SpeechService  (speech_service.py)         -- called only from presenters
```

Flow: user keystroke -> EVT_CHAR_HOOK -> InputLayer -> presenter callback -> SpeechService.
Views never call SpeechService directly (enforced by convention, not type system).

MainWindow creates SpeechService and InputLayer as infrastructure. This is object
wiring, not business logic -- consistent with the MVP pattern.

## Design Decisions

**Zone-per-presenter with ZoneNavigationMixin (DL-001)**
Each presenter declares only the zones it supports. A monolithic base class would
force all presenters to carry zone infrastructure for zones they do not have
(CardBrowserPresenter would need board/hero/weapon zone stubs). ZoneNavigationMixin
provides cursor management and navigation helpers without imposing unused zone sets.

Rejected: modal zone navigation. Always-global zone keys match the Hearthstone
Accessibility convention that zone keys are instant jumps with no enter/exit
required. Modal navigation adds cognitive load for screen reader users.

**Hero power in hero zone, not separate keys (DL-002)**
V (player hero) and F (opponent hero) announce name, health, armor, and hero power
name in one call. No R/Shift+R keys. Hero power is always associated with the hero;
separate keys add key count without benefit.

**EVT_CHAR_HOOK for all keyboard handling (DL-003)**
InputLayer binds `wx.EVT_CHAR_HOOK` at the frame level. EVT_CHAR_HOOK fires before
native control handlers, which is critical because NVDA/JAWS install
WH_KEYBOARD_LL hooks that intercept WM_KEYDOWN before it reaches the app, causing
EVT_KEY_DOWN and EVT_CHAR to silently fail on list/tree controls.

Ctrl and Alt combinations always pass through (`event.Skip()`) so native menu
accelerators and screen reader shortcuts remain functional.

**Navigate-then-inspect speech model (DL-004)**
`Card.to_speech_text()` returns only the name -- used for navigation announcements
(zone jumps, Left/Right). `Card.detail_lines()` returns an ordered list of stat
strings that the presenter reads one at a time as the user presses Down. This keeps
navigation fast and non-overwhelming; users inspect deliberately.

Rejected: brief/normal/detailed verbosity modes. Consistent announcements are more
predictable than mode switching.

**Text mode via flag guard on EVT_CHAR_HOOK (DL-005)**
`InputLayer.enter_text_mode()` sets a flag that causes `_on_char_hook` to call
`event.Skip()` for all keys, allowing keystrokes to reach TextCtrl widgets
normally. Ctrl and Alt combinations are always passed through regardless of text
mode.

`activate_view()` automatically exits text mode when switching views, preventing
stale text mode state.

EVT_ACTIVATE guard: `_on_activate` calls `exit_text_mode()` when the window
regains focus and the focused widget is not a TextCtrl. wx does not reliably fire
`EVT_KILL_FOCUS` on alt-tab; without this guard, text mode can become permanently
stuck after the user switches away and back.

Speech-driven panels should set `wx.WANTS_CHARS` style to ensure all keystrokes
reach EVT_CHAR_HOOK rather than being consumed by the native widget.

**Frozen dataclasses (DL-006)**
GameEntity, GameState, ReplayState, and Hero are `@dataclass(frozen=True)`,
consistent with the existing frozen Card and Deck models. Prevents accidental
mutation when multiple presenters hold references to the same game state snapshot.
Any state update requires constructing a new instance.

**SpeechService stdout fallback (DL-007)**
`SpeechService.__init__` wraps the `accessible_output2` import in try/except.
Stdout fallback means the application runs in development and CI environments
without a screen reader installed. `accessible_output2.Auto()` handles detection
across NVDA, JAWS, Windows Narrator, and others at runtime.

**Diminishing orienting messages (DL-008)**
When a zone key is pressed that has no meaning in the current view (e.g., B in
card browser), `handle_inapplicable_zone` tracks press counts:
- First press: full help string ("Card browser: Tab for search, arrows to browse")
- Second press: short form ("Card browser mode")
- Third+ press: silent

Counts reset on zone change. Prevents annoyance while maintaining discoverability.

**Replay pipeline out of scope (DL-009)**
Models define the data shapes (GameEntity, GameState, ReplayState). The hslog
BaseExporter subclass that produces ReplayState from a `.hsreplay` file is
deferred to a separate implementation. Presenters accept pre-built ReplayState
objects, enabling testing with hand-constructed snapshots.

## Invariants

- Views never call SpeechService directly. Only presenters call `self._speech`.
- Zone keys are always global. No zone requires an enter/exit action.
- Each zone cursor is independent and persists across zone switches.
- InputLayer holds exactly one active key map at a time. `activate_view()` fully
  replaces the previous map.
- Ctrl and Alt combinations are never intercepted by InputLayer.
- All game state models are frozen. Never mutate a GameState or ReplayState;
  construct new instances instead.
- `Card.to_speech_text()` returns only the name. Do not add a verbosity parameter.
- `opponent_hand` entries are `Optional[GameEntity]`: None represents a hidden
  card whose identity is not exposed in Power.log.
- Enchantment fidelity in replays depends on `GameTag.ATTACHED` linkage. Aura
  effects (e.g. Stormwind Champion +1/+1) may not generate explicit TAG_CHANGE
  packets -- buffed stats are correct in entity tags but the aura source may not
  be discoverable via ATTACHED. This is a Power.log format limitation.
- `cards_by_name` in CardDatabase uses lowercased keys. All name lookups must go
  through `get_card_by_name()`.

## Tradeoffs

- Navigate-then-inspect trades immediate detail for navigation speed. Users must
  press Down to hear stats, but zone switching and browsing stay fast and
  non-overwhelming.
- Frozen dataclasses prevent in-place mutation, requiring new object creation for
  state updates. Acceptable because game states are snapshots, not live-edited
  objects.
- Multi-index CardDatabase maintains 7 parallel dictionaries (by id, dbf_id, name,
  class, type, set, cost) plus a collectible list. Trades ~7x memory for O(1)
  lookups on all common query patterns. Card search and deckstring parsing are
  latency-sensitive in an interactive UI.
