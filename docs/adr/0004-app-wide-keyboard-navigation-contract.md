# App-wide keyboard-navigation contract

## Status

Accepted (design contract, 2026-08-13). Extends ADR-0003 from the game-state
surfaces to the whole app. Implementation lands via PRDs opened against the
final UI spec (wayfinder map #17); nothing here ships code by itself.
Decided in ticket #18.

## Context

StoneReader's screens accreted one at a time, each choosing its own keys. A
survey of the shipped app found the same key meaning different things across
screens (Up/Down moves items on three screens, reads detail lines on four,
and is unbound on two), the same intent expressed two ways (delete confirms
via modal dialog on Deck Manager, via press-twice on Replays), three screens
that announce nothing on entry, and a text-field trap where Escape is dead
(Import Deck). Meanwhile HSA's non-game screens already follow a coherent
two-widget grammar StoneReader's audience has internalised.

## Decision

Every StoneReader surface obeys one contract, adopted from HSA's non-game
grammar and extended where HSA is silent.

### Two widget types, no third

Every surface presents exactly one **widget type** at a time:

**Vertical menu** — a cursor over options.

| Key | Action |
|---|---|
| Up / Down | Previous / next option |
| Enter | Act on current option |
| Home / End | First / last option |
| Shift+Up | Reread current option |
| Left / Right | Unbound — silence here is the signal "you're in a menu" |
| Letters | May be bound as jump-and-activate shortcuts (HSA main-menu precedent); each surface's spec assigns them |

**Horizontal list** — a cursor over items, each with detail lines.

| Key | Action |
|---|---|
| Left / Right | Previous / next item |
| Up / Down | Previous / next detail line of current item |
| Shift+Down | Read from current detail line to the last |
| Shift+Up | Repeat current detail line |
| Home / End | First / last item |

**Forms are vertical menus.** A form is a vertical menu whose options are
fields and actions ("Deck code, edit text", "Import"). Enter on a field
enters text mode; Enter on an action acts. This dissolves the app's one
free-form screen (Import Deck) into widget type #1 — there is no third type.

### Universal keys

| Key | Invariant |
|---|---|
| Enter | Acts on the current item. Never a silent no-op: each surface's spec assigns its action or an announced no-op. |
| Escape / Backspace | Synonyms for **back**, injected centrally by the navigation controller, never bound per-surface. At the stack root, back is an announced no-op ("Home — already at the top"), not a quit. Quit stays on Ctrl+Q / Alt+F4. |
| Home / End | First / last (option, item — whatever the widget type's cursor covers). |
| PageUp / PageDown | Page the surface's **coarse axis**: pages in collection surfaces, turns in the Replay Viewer. (This clause originally also named a "Live Game timeline"; ADR-0013 retired that concept — on Live Game, PageUp/PageDown is a constant announced no-op.) Related-card content (HSA's in-game PageUp/Down meaning) lives in the detail-line stream instead; a surface spec may add a dedicated key if that proves insufficient. |
| Tab / Shift+Tab | Group jump where the surface has groups (class filter in Card Browser — HSA collection precedent); announced no-op where it has none. Never focus traversal. |
| Ctrl+F | Search. Opens a typed search field on surfaces that support it (HSA collection precedent); announces "No search on this screen" on surfaces that don't. |
| F1 | Help, everywhere (see below). |

**No universal key ever dies silently.** If a universal key has no effect on
a surface, the surface says so. Unbound non-universal keys stay silent.

### Text mode

Text mode is entered only by an explicit act (Enter on a field, Ctrl+F).
While it is active, keystrokes go to the field — Backspace erases, arrows
move the caret. **Enter commits** the field and returns to the surface;
**Escape exits without committing**. Escape is therefore never dead: the
user can always leave a text field with one keypress. A surface never lands
the user in text mode on entry.

### One delete idiom

Delete arms: the surface speaks "Press Delete again to delete {item}".
Delete again on the same item deletes; any cursor movement disarms. No modal
confirmation dialogs — this is HSA's confirm-by-repeat pattern (tavern
upgrade/refresh/freeze), and it keeps the user in the surface they can
already navigate. Shift+Delete deletes without confirmation, per HSA's
Shift-skips-confirmation meaning. Deck Manager migrates off its modal
dialog; Replays already complies.

### Numbers

Restating ADR-0003 as an app-wide invariant: **numbers never switch
zones.** On game-state surfaces digits 1–9 jump to positions 1–9 and 0 to
position 10. On collection surfaces digits filter by mana cost, **0–9**:
0–8 exact, 9 means 9+. This deliberately extends HSA's 0–7 filter — 8 and 9
are unbound in HSA's collection, so the extension is purely additive; the
one visible divergence is that if HSA's 7 means "7+", StoneReader's 7 means
exactly 7.

Consequently **Live Game drops digits 1–4 as zone switches** (a pre-ADR-0003
holdover) and adopts the Replay Viewer's letter set for the same zones:
`d` remaining deck, `Shift+C` opponent hand, `Shift+P` opponent played,
`n` cards drawn. Inspecting a game is one dialect, live or replayed.
(ADR-0013 later completed the dialect: Live Game carries the Replay Viewer's
full zone inventory and speak-only queries, current-state only.)

### Announcements

Every surface announces itself on entry: `"{Surface name}, {current item
announcement}"` — e.g. "Deck Manager, Aggro Shaman, Shaman, Standard, 1 of
4" — degrading to `"{Surface name}: empty"` (or a count) when there is
nothing under the cursor. Same shape as zone-entry announcements within a
surface. The widget type is not announced explicitly; behavior plus F1 carry
it. Full speech grammar (movement wording, empty states, interrupt policy)
is ticket #21's scope.

### F1 help

F1 pushes a **help surface** — itself a vertical menu on the ordinary
navigation stack — one option per binding, browsable at the user's pace,
Backspace to return. Its first line states the surface's widget type ("Card
Browser is a horizontal list: Left and Right move between cards…"). Help
content generation and the full command reference are ticket #23's scope.

## Alternatives considered and rejected

- **A third widget type for forms.** Rejected: the vertical-menu-of-fields
  model covers it, and the free-form screen was where the Escape-dead bug
  lived — the trap was structural (focus lands in a text field on entry),
  not a missing binding.
- **Modal dialogs as the delete confirmation.** Rejected for the
  press-twice idiom: HSA precedent, no focus excursion into a foreign
  dialog, and the armed state disarms on any movement.
- **Left/Right aliased to Up/Down in vertical menus** (shipped behavior on
  Home and Card Library). Rejected: if Left/Right work in menus, the two
  widget types are indistinguishable by probe, and the type is the user's
  mental anchor.
- **Strict HSA PageUp/PageDown (related-card lines) on game-state
  surfaces.** Rejected where a surface has a paging axis: turn stepping is
  the Replay Viewer's spine and already in users' hands; the rare
  colossal/questline card reads fine from the detail lines.
- **Escape-as-quit at the root.** Rejected: Escape-to-quit is how a session
  is lost to a reflex.

## Consequences

**Positive.** The contract is small enough to test as invariants (no silent
universal keys, Escape always exits text mode, numbers never switch zones,
every surface announces entry). HSA muscle memory transfers everywhere, not
just on game-state surfaces. Per-surface specs shrink to: widget type,
Enter's action, groups (if any), search (if any), letters (if any).

**Negative.** Shipped behavior changes: Import Deck is respecced as a
vertical menu, Deck Manager loses its delete dialog, Live Game loses digit
zone-switching (retraining the one existing user's muscle memory), Home and
Card Library lose the Left/Right alias. The input layer must learn F-keys
(currently unrepresentable) and Shift+Delete. Numbers-mean-0–9 diverges
from HSA by design; ADR-0003's correction pass (ticket #29) must not
"fix" it back to 0–7.
