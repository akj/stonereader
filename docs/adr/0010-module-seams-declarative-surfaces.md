# Module seams: declarative surfaces, one registry, one announcer

## Status

Accepted (design contract, 2026-08-15). The architecture that makes the
contract ADRs (0004, 0006, 0007, 0008, 0009) structurally enforceable
rather than re-implemented per screen. Implementation lands via PRDs opened
against the final UI spec (wayfinder map #17); nothing here ships code by
itself. Decided in ticket #24.

## Context

The contract ADRs state invariants — no universal key dies silently, the
same place sounds the same on every route, help cannot drift from the
bindings — but the shipped code has no structure to hold them. A code
inventory (ticket #24) found: the presenter/view contract is entirely
duck-typed, with no Protocol or ABC anywhere; `set_on_state_changed` exists
in five incompatible signatures plus two narrower one-off callbacks, and
one screen names the method differently; a presenter missing `get_key_map`
silently receives an empty keymap from the controller (Import Deck ships
exactly that); nine presenters hand-build their own key dicts;
`ZoneNavigationMixin` has no change notification, so six presenters
hand-wire their own `_notify_view` and re-override the same movement
methods; views take focus three different ways; `NavigationController`
never speaks (back is silent), appends to the stack unconditionally, and
`replace_panel` rebuilds presenters from scratch, losing cursors; all nine
presenters call speech directly, plus three call sites in the composition
root; and both Ctrl+F dispatch and the global-hotkey service carry silent
no-op branches. Every invariant would otherwise be N screens' good
behavior. This ADR moves each one into a single component that either
enforces it or makes violating it a registration error.

## Decision

### Surfaces are declarations; two engines interpret them

A surface is data: label, widget type, bindings, data sources, title-line
formatter, drill-downs, slot fills. Exactly two **widget-type engines** —
vertical menu and horizontal list — interpret surface declarations and own
cursor movement, key dispatch, boundary behavior, and announcement
triggers. A surface cannot exist without a label and widget type; a
binding cannot register without its spoken help phrase (ADR-0009's
generated help falls out of this). The per-screen code that survives is
the surface definition plus its handlers — action callbacks and data
providers. It handles no keys, speaks no strings, syncs no cursors. The
word "presenter" is retired with the role; per-screen modules are surface
definitions.

### Zones live in the horizontal-list engine

A horizontal-list surface declares its zones — label, item source,
title-line formatter, optional jump letter. The engine owns the per-zone
cursors, their persistence across switches (ADR-0007), zone-switch
context-entry utterances, and the constant "No {zone} on this screen"
announced no-ops (ADR-0009). `ZoneNavigationMixin` is deleted, not ported.
Vertical menus have no zone concept.

### The command registry: commands, layers, slots

The registry's unit is the **command**: id, handler, spoken help phrase,
and the layer it belongs to. Three layers — universal, widget-type,
surface — and a lower layer structurally cannot shadow an upper one:
binding Escape or F1 on a surface is a registration error. Universal keys
with per-surface behavior (Enter, Tab, Ctrl+F, PageUp/Down, L) are
**slots**: a surface fills the slot by command id, or the slot's default
fires an announced no-op. Bindings map normalized chords to command ids;
the Help menu renders the registry, and its Enter-executes path dispatches
the chosen command id on the underlying surface (ADR-0009). System-wide
hotkeys are commands too: the global-hotkey service translates a hotkey to
a command dispatch through the same path, so no input route can die
silently.

### One input sink

`input_layer.py` grows into the single keyboard entry point: a frame-level
`EVT_CHAR_HOOK` normalizes every keystroke into a chord (closing the F-key
and Shift+Delete gaps ADR-0004 flagged), routes it to the active surface's
registry, and owns **text mode** as an input-layer state — entered only
explicitly, Enter commits, Escape always exits, F1 speaks the rescue
without leaving the field (ADR-0009). The bare-Ctrl game-audio stop
(ADR-0008) listens here, below the registry — a lone modifier is never a
chord. No child widget takes keyboard focus; views are render-only
subscribers of engine state. The three shipped focus variants die
structurally, and the five state-callback signatures dissolve with them.

### The Announcer owns every string; the Narrator feeds Lane 2

The **Announcer** owns every speech template — context-entry, bare-title
movement, boundary repeat, confirmations, drive-by queries — and both
speech lanes with their collision rules (ADR-0007). It is the only module
that imports the TTS output. Engines and the navigation controller call
it with typed data; a surface has no way to speak except by returning
data, so route invariance is topological, not tested. The surface's one
text hook is its title-line formatter, used verbatim by the displayed
row, movement speech, and detail line 0. The **Narrator** is the one
non-user-initiated speech producer: a service, owned by no surface, that
consumes Game events, phrases them, and speaks on Lane 2 — narration no
longer lives inside the Live Game screen, and Settings (ticket #25)
configures its verbosity against this seam.

### The navigation controller: stack, title, utterance, audio stop

The controller owns ADR-0006's stack semantics — a screen jump resets to
[Home, target], a drill-down pushes one, back pops (announced no-op at
Home) — and on every landing, by any route, fires the window-title
update, the context-entry utterance via the Announcer, and the game-audio
stop. `replace_panel` is deleted as subsumed by jump-reset. Surfaces are
lazy singletons: created on first visit, alive for the app's lifetime,
held by reference on the stack — ADR-0007's persistence rules are free,
and transient exceptions are per-surface declarations, not lifecycle
differences.

### Game audio: two services, three touchpoints

An **extraction/index service** (install discovery, runtime Unity-version
detection, per-patch clip index, the "no install → channel absent" state)
and an **async player** (one clip at a time, new replaces old, app-level
volume) live in the service layer, per ADR-0008's bright lines. The UI
touches them at exactly three points: the controller's transitions-stop
hook, the input layer's bare-Ctrl stop, and surfaces requesting clips by
card id and event. The Sounds menu is an ordinary vertical-menu surface
built from the index.

## Alternatives considered and rejected

- **A disciplined presenter base class** (Protocol/ABC, one signature
  set). Rejected: five signatures and zero formal contracts show
  discipline is what already failed; enforcement would stay review-level,
  and every invariant would still be N implementations.
- **Per-widget focus retained.** Rejected: three variants exist because
  each screen re-decides; with all keys dispatched centrally, no child
  needs focus at all.
- **Surfaces calling speech directly** (status quo). Rejected: route
  invariance and lane rules become untestable conventions; one Announcer
  makes them properties of the call graph.
- **Surface-rebindable universal keys.** Rejected: ADR-0004 calls them
  invariants; slots give surfaces the per-surface behavior they need
  without the power to break the layer above.
- **Porting `ZoneNavigationMixin`.** Rejected: its no-notification design
  is the root of the six duplicated view-sync sites.
- **Fresh surface instances per entry.** Rejected: ADR-0007's persistence
  would become hand-saved state; singletons make it free.
- **Splitting this into several ADRs** (registry, speech, navigation).
  Rejected: the seams only make sense together — the registry feeds help,
  the engines and controller feed the Announcer, the input layer feeds
  the registry and the audio stop.
- **Keeping the word "presenter."** Rejected: it would name a thing that
  no longer presents; stale names invite re-inventing the old shape.

## Consequences

**Positive.** The contract ADRs' invariants become structure: a surface
without a label or a binding without a phrase cannot be constructed;
shadowing a universal key cannot be registered; a silent back, a
route-dependent utterance, or drifted help have no code path. Invariant
checks become registry queries ("every surface fills Enter") instead of
code audits. New surfaces — the stats surface, Battlegrounds tools, pack
tracking — cost a declaration plus handlers.

**Negative.** This is a rewrite of the UI layer, not a refactor: nine
presenters, `ZoneNavigationMixin`, `replace_panel`, and the per-view
callback wiring are deleted, and PRD sequencing must stage that safely.
The two engines and the Announcer become load-bearing single points —
bugs there are app-wide by construction. The input layer's chord
normalization (F-keys, Shift+Delete, bare-Ctrl) must land before anything
else can. Production-unused presenter methods found by the inventory are
deleted unmourned.
