# Screen topology and information architecture

## Status

Accepted (design contract, 2026-08-13). Builds on ADR-0004's navigation
contract; implementation lands via PRDs opened against the final UI spec
(wayfinder map #17); nothing here ships code by itself. Decided in ticket #19.

## Context

StoneReader's screens accreted without an information architecture. Home is a
five-item ListBox with no entry announcement; Card Library is a hardcoded
category chooser that exists only to construct the Card Browser; the
navigation stack appends unconditionally, so repeated global-hotkey presses
cost one Escape each to unwind; the window title never changes; a status bar
shows stale Card Browser text on every other screen; and a clipboard
deckstring teleports the User into the Import Deck form without a keypress.

The original framing asked "tabs, and where? Menus?" — but HSA, the
audience's daily driver, answers topology differently: no tabs anywhere,
a main menu of single-letter jump-and-activate shortcuts (R/A/M/B/T/C/O/J/S),
and Backspace walking back the way you came. Meanwhile StoneReader's global
hotkeys are system-wide (`RegisterHotKey`), designed to fire while
Hearthstone itself has focus — a scope HSA's menu letters never had to serve.

## Decision

### Home is an HSA-style vertical menu with letter jumps

Home is the stack root: a vertical menu (per ADR-0004) whose options carry
single-letter jump-and-activate shortcuts, HSA-main-menu style. The menu, in
order:

| Order | Option | Letter | Rationale |
|---|---|---|---|
| 1 | Live Game | `L` | free in HSA's main menu |
| 2 | Decks | `D` | free in HSA's main menu |
| 3 | Cards | `C` | matches HSA `C` = My Collection |
| 4 | Replays | `R` | mnemonic; HSA's R (Play Ranked) can't misfire here |
| 5 | Settings | `S` | HSA S = Shop; no shop exists here |

`B` and `O` are **reserved**: HSA binds B = Battlegrounds and O = Open
Packs, and both are known fog on map #17 (Battlegrounds tools,
collection/pack tracking). Burning them now would manufacture a future
collision with the audience's strongest reflexes.

Letters are **Home-scoped**. On other surfaces bare letters belong to that
surface's own keymap (zone letters, per ADR-0003/0004).

### Screen jumps reset the stack; drill-downs push

Two ways to reach a surface, with different stack semantics:

- A **screen jump** (Home letter, Home menu Enter, or system-wide hotkey)
  resets the stack to `[Home, target]`. Back from any jumped-to surface goes
  Home. Duplicate stack entries become structurally impossible.
- A **drill-down** (Replays → Replay Viewer, Decks → deck contents, Decks →
  Import Deck, F1 → help) pushes one level. Back pops exactly one.

Back's meaning is statable in one line: *back pops one drill-down; from a
top-level surface it goes Home; at Home it is an announced no-op*
(ADR-0004 — the shipped silent no-op at the root is an implementation gap).
Re-entry on back re-announces per ADR-0004's standard entry announcement
with the surface's cursor preserved; wording is ticket #21's scope.

### System-wide hotkeys: Ctrl+Shift, aligned with Home letters where free

Global hotkeys keep the shipped `Ctrl+Shift` modifier — they must fire over
Hearthstone, clear of HSA's own keymap. Assignments:

| Hotkey | Effect |
|---|---|
| `Ctrl+Shift+L` | Jump: Live Game, landing on remaining deck |
| `Ctrl+Shift+O` | Jump: Live Game, landing on opponent hand (shipped) |
| `Ctrl+Shift+C` | Jump: Cards |
| `Ctrl+Shift+R` | Jump: Replays |
| `Ctrl+Shift+D` | Speak-only query: deck counts (shipped; HSA `d` mnemonic) |
| `Ctrl+Shift+H` | Speak-only query: opponent hand count (shipped) |

Speak-only queries are HSA's drive-by-query idiom made system-wide: they
speak and navigate nowhere. `Ctrl+Shift+D` stays a query rather than a
Decks jump — mid-game, "what's left in my deck" is the high-value ask, and
it inherits HSA's in-game `d`. Decks and Settings get no global jump: they
are not mid-game surfaces, and Home reaches them in two keys. The letter
alignment rule is therefore *aligned where free, HSA-in-game mnemonics win
conflicts*. (`Ctrl+Shift+R` changes meaning from the shipped build — it
jumped to Live Game's remaining deck, which `Ctrl+Shift+L` now covers.)

### No native menu bar

No `wx.MenuBar`. It would be a second copy of every command (drift risk)
in a second dialect (menu traversal vs the two widget types), for an
audience whose muscle memory is HSA — which has no menu bar. Discoverability
is already assigned: F1's per-surface help menu (ticket #23) and Home
itself. Reversible omission: a mirror menu bar could be added later without
disturbing the topology.

### Card Library is deleted; Cards is the Card Browser

The Library's one job — pick a class — is a job ADR-0004 already gave the
Browser (Tab/Shift+Tab group-jumps the class filter, HSA collection
precedent). Home → Cards opens the Browser directly on All Cards with the
standard entry announcement; class selection, search (Ctrl+F), and mana
filter (0–9) live inside the list. One surface, one keymap.

### Import Deck lives inside Decks

Import Deck is a drill-down from the Decks surface ("Import deck…" option),
not a Home entry. Importing is a deck-management act; finishing or backing
out lands the User in Decks, where the new deck is.

### Clipboard deckstring detection offers, never teleports

On window activation with a deckstring on the clipboard, StoneReader
announces an offer ("Deck code on clipboard — press Enter to import")
instead of pushing the Import form pre-filled. Accepting drills into Import
Deck with the code pre-filled. This preserves the invariant the rest of the
topology can now state: **the User always chose to be here** — no surface
change without a keypress.

### Window title tracks the surface; no status bar

The frame title is `{Surface name} — StoneReader`, updated on every stack
change, so Alt+Tab and screen-reader title reads lead with *where you are*.
The status bar is removed rather than given a job — for a screen-reader-only
audience it is dead weight, and its one shipped writer (Card Browser) leaks
stale text onto every other screen. Sighted debugging is the log's job.

## Alternatives considered and rejected

- **Tabs** (the original prompt's framing). Rejected: no HSA precedent; the
  audience's model is menus, letters, and Backspace.
- **A native menu-bar mirror.** Rejected as a second dialect and a second
  copy of every command; see above.
- **Home-only letters with no system-wide jumps.** Rejected: "check my
  cards mid-game" would mean leaving Hearthstone's focus and unwinding by
  hand. The system-wide tier is StoneReader's whole reason to exist beside
  HSA.
- **Uniform Home-letter alignment for all global hotkeys** (`Ctrl+Shift+D`
  as Decks jump). Rejected: it evicts the deck-counts query from its HSA
  `d` mnemonic to serve a surface nobody jumps to mid-game.
- **Push-with-dedup stack semantics** (jump pops back to an existing
  entry). Rejected: jump-resets-to-`[Home, target]` makes Backspace's
  behavior predictable from the current surface alone, with no stack
  history to reason about.
- **Keeping Card Library as the class chooser.** Rejected: it fronts the
  real surface with an extra hop every time, duplicates Home's keymap, and
  its job is already inside the Browser.
- **Clipboard auto-push into Import Deck** (shipped behavior). Rejected:
  the one place the app moved the User without a keypress.
- **A "last announcement" status-bar job.** Rejected: inventing a job to
  keep chrome no target user perceives.

## Consequences

**Positive.** The topology is statable in three sentences: Home is a menu
of five lettered options; jumps reset, drill-downs push, back pops one;
system-wide Ctrl+Shift keys jump or query over Hearthstone. All four fog
surfaces slot in without new grammar — Battlegrounds tools and pack
tracking land on reserved letters that agree with HSA's own B and O.
Per-surface specs need only name their drill-downs.

**Negative.** Shipped behavior changes: Card Library is deleted,
`Ctrl+Shift+R` changes meaning, Import Deck leaves Home, the clipboard
flow demands one extra keypress, and the stack model invalidates the
current `NavigationController` append/pop logic (`stonereader/app.py`) —
including `replace_panel`, which the jump-reset model subsumes. Known
implementation gaps recorded for the PRDs: silent root no-op
(contradicts ADR-0004), stale status-bar text, clipboard flow reaching
into `nav._panels` privately.
