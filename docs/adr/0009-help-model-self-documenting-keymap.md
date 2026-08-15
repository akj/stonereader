# Help model: F1 and the self-documenting keymap

## Status

Accepted (design contract, 2026-08-15). Fills in the help shell ADR-0004
established (F1 universal, pushes a help surface, first line states the
widget type). Implementation lands via PRDs opened against the final UI spec
(wayfinder map #17); nothing here ships code by itself. Decided in ticket #23.

## Context

ADR-0004 fixed F1's shell and deferred its content. HSA ships F1 contextual
help on every screen and prompt, so the muscle memory exists. The risk this
ADR guards against is drift: hand-written help describes the keymap the
author remembered, not the one that ships. The app also carries a shipped
discoverability idiom to rule on — DL-008's "diminishing orienting
messages," where an inapplicable zone key speaks full help, then short, then
nothing.

## Decision

### Generated, never written

The Help menu renders the command registry (ticket #24's seam) for the
current surface. **A binding cannot be registered without its spoken help
phrase** — help is a view of the registry, so it cannot drift from the
bindings. The widget-type line is generated from the surface's declared
type. No per-surface help text exists anywhere else.

### The Help menu's shape

F1 pushes the **Help menu** — a vertical menu on the ordinary stack,
Backspace/Escape to return, window title "{Surface} help". Its options, in
order:

1. **The widget-type sentence** — "Card Browser is a horizontal list: Left
   and Right move between cards, Up and Down read details." Spoken on entry
   as the current option per ADR-0007's vertical-menu utterance.
2. **Screen-specific bindings**, one option per binding, key-first:
   `"{Key}: {action phrase}"` — "D: jump to Remaining Deck". Title-line
   rules apply (written for the ear).
3. **"Universal keys"** — a drill-down listing the app-wide layer (Escape,
   Home/End, PageUp/Down, Tab, Ctrl+F, F1, …). Structure carries the
   universal/screen-specific distinction; options are never individually
   labeled with it.
4. **"All commands"** — a drill-down of per-surface sections (Home order),
   each a nested vertical menu of that surface's bindings: the in-app
   command reference, generated from the same registry. Options here are
   read-only ("Only available on {surface}" on Enter).

Ctrl+F searches help like any searchable surface.

### Enter executes

Enter on a binding option **pops help and performs that binding on the
underlying surface** — help doubles as a discoverability command palette:
find "Shift+C: opponent hand," press Enter, land there. Options that cannot
sensibly execute (Enter itself, text-mode keys, All-commands entries) are
announced no-ops per ADR-0004's rule. Destructive safety is unchanged —
delete executed from help still only arms and asks for its second press.

### Edge cases

- **F1 inside help**: announced no-op ("Already in help") — help never
  stacks on help.
- **F1 in text mode**: works (F-keys aren't characters) and speaks the
  rescue without leaving the field: "Typing in {field}. Enter commits,
  Escape cancels." The Import Deck trap becomes structurally impossible to
  be lost in.

### DL-008 is retired

Bound-but-inapplicable keys speak one constant short announced no-op ("No
{zone} on this screen") every time. No press counting, no diminishing
verbosity, and never silence — a press going silent is exactly the "did my
keypress land?" ambiguity ADR-0007 outlawed at boundaries.

## Alternatives considered and rejected

- **Read-only help.** Rejected: options are registry entries, so execution
  is nearly free, and pick-to-perform teaches by doing — the difference
  between a manual and a teacher.
- **Flat list with universal keys appended** (or labeled per option).
  Rejected: re-listing the identical universal layer on every F1 buries the
  screen-specific keys the user opened help for; one drill-down puts it one
  Enter away instead.
- **Symmetric categories ("This screen" / "Everywhere" both as
  drill-downs).** Rejected: adds a hop to the 90% case for symmetry's sake.
- **A full-reference surface on the Home menu.** Rejected: Home's five
  lettered options are locked (ADR-0006), and the All-commands drill-down
  delivers the same reference from anywhere.
- **Keeping DL-008's diminishing verbosity.** Rejected: predictable beats
  adaptive for a screen-reader interface, and the counting/reset state
  machine buys nothing once announced no-ops are constant.

## Consequences

**Positive.** Help can never lie: every binding carries its phrase or fails
registration, and the same registry renders F1, the universal list, and the
command reference. Discoverability compounds — F1 anywhere, search inside
it, Enter to act on what you found, and a one-line rescue from text mode.
Per-surface specs need no help section at all.

**Negative.** The command-registry design (ticket #24) must carry a spoken
phrase per binding and a help-invokes-command path back to the parent
surface. DL-008's shipped counting code and behavior are deleted. The
input layer's F-key gap (noted in ADR-0004) becomes load-bearing.
