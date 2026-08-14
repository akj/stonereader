# Announcement grammar: one speech contract for every surface

## Status

Accepted (design contract, 2026-08-14). Extends ADR-0004's announcement
section into the full speech contract; supersedes its entry-announcement
example (see Decision). Implementation lands via PRDs opened against the
final UI spec (wayfinder map #17); nothing here ships code by itself.
Decided in ticket #21.

## Context

StoneReader's speech accreted per screen. A code inventory (ticket #21)
found: the same place sounds different by route — a global hotkey speaks
"Remaining deck zone, 2 cards. Glacial Shard, 1 copy, 1 of 2" where the
in-screen key speaks "Remaining Deck, Glacial Shard, 1 copy, 1 of 2";
internal ids leak into speech ("remaining_deck: empty") from one empty-state
code path while a second path correctly uses the label; four surfaces (Home,
Card Library, Deck Manager's normal path, Import Deck) announce nothing on
entry; back-navigation is entirely silent; spoken and displayed text for the
same row come from two independent formatters ("Fireball, 2 of 4" vs
"Fireball -- 4 mana -- MINION"); the detail-line cursor resets
inconsistently to -1 or 0; and confirmations and drive-by queries each have
ad-hoc phrasing ("Copied Fireball" vs "Deck code copied to clipboard";
"Opponent has 5 cards." vs "23 left, opponent 24."). All speech today is
interrupt-on-new; a queued-speech API exists with zero callers.

## Decision

### Route invariance: the context-entry utterance

There is exactly one **context-entry utterance**, and it fires identically
whenever the User lands in a context, regardless of route: screen jump,
drill-down, back-reveal, zone switch, in-place rebuild (filter or search
change), and orientation reread (Shift+Up). No route-specific phrasing
exists — no "back to…" prefix anywhere.

- Horizontal list / zone: `"{Context label}, {title}, {position} of {count}"`
- Vertical menu: `"{Context label}, {current option}"` — no position; menus
  are small and stable.
- Empty context: `"{Context label}: empty"` — universally, always the
  user-facing label, never an internal id, no per-surface nouns. This
  dissolves special cases like "No results".

This supersedes ADR-0004's richer example ("Deck Manager, Aggro Shaman,
Shaman, Standard, 1 of 4"): the item part of the utterance is the title
line, not a multi-fact summary.

### The title line: one formatter, spoken-first

Every item has exactly one **title line** — the shortest string that
identifies it among its neighbors in that list. One formatter produces it,
and it is used verbatim in three places: the displayed row, the movement
utterance, and detail line 0. Speech-only material (context label, position,
"empty", confirmations) is ephemeral wrapping added by the announcement
layer, never baked into item text.

Title contents are a per-surface spec decision under one grammar-level
test: **distinguishability** — a card's name suffices in Card Browser; a
Deck Contents duplicate needs its count ("Fireball x2"); a replay row needs
opponent/result/turn because bare names would all sound alike.

The canonical string is written for the ear ("3 attack, 2 health", never a
bare "3/2"); the visual display shows exactly that string. The eye reads
what the ear hears.

### Movement, detail lines, boundaries

- Moving the cursor speaks the bare title (or option, or detail line) —
  no position appended. Position is on demand via Shift+Up.
- Shift+Up is the orientation key: it re-fires the context-entry utterance
  for where you stand, with the current detail line in the item slot. On
  line 0 it reproduces the entry announcement exactly.
- Detail lines hold one fact per line; spoken text equals displayed text
  per line; the order of lines 1+ is per-surface spec territory.
- A boundary press (Up at first, Down at last, Left/Right at the ends)
  repeats the current bare title — "you pressed, nothing moved" with no
  new vocabulary. Sound cues (ticket #22) may layer an edge cue on top.

### Cursor rules

- The -1 "un-announced" detail state is outlawed: after any entry or
  movement the title has just been spoken, the detail cursor rests on
  line 0, and the first Down goes deeper to line 1.
- A non-empty context's item cursor always rests on a real item.
- Persistence: back-reveal keeps the revealed surface exactly as left;
  zone cursors persist across zone switches; a screen jump to a previously
  visited surface also finds it as left — jumps reset the stack (ADR-0006),
  not the target's innards. Surface specs may opt specific transients out
  (e.g. a search box). Fresh state is what app restart is for.

### Two speech lanes

- **Lane 1 — user-initiated** (movement, entry, drive-by queries,
  confirmations): always interrupts whatever is speaking, instantly.
- **Lane 2 — auto-narration** (live-game events): queues in order among
  itself, never interrupts Lane 1, and a Lane-1 keypress drops the pending
  Lane-2 queue (current utterance cut, queued events discarded — the
  information stays browsable in the timeline and zones).

Which events Lane 2 narrates, and at what verbosity, is the Settings
surface's scope (ticket #25); this grammar owns only the lanes and their
collision rules.

### Drive-by queries and mutations

- Drive-by (speak-only) queries: `"{Subject}, {value}"` — always
  subject-first, never a bare number. "Your mana, 4 of 10", "Opponent hand,
  5 cards", "Your deck, 23 cards".
- Confirmations: `"{Object} {verb-past}"` — "Fireball copied", "Aggro
  Shaman deleted", "Riffs of Rage imported".
- When an action changes what is under the cursor (delete, filter, search),
  the confirmation is followed by a re-fired context-entry utterance:
  "Aggro Shaman deleted. Deck Manager, Burn Mage, 2 of 3". Filter and
  search state ride in the context label: "Mage cards, 3 mana, Fireball,
  1 of 12"; "Search results for fire, Fireball, 1 of 4". Cursor-neutral
  actions (copy) get the confirmation alone.

## Alternatives considered and rejected

- **Summary-rich movement utterances** (name + stats + position on every
  arrow press). Rejected: chatter for a power-navigating screen-reader
  user, and unfaithful to HSA, which speaks the card name on Left/Right
  and keeps depth in the detail lines.
- **Route-distinguishable phrasing** ("back to Deck Manager…"). Rejected:
  the keypress already tells the User the route; only the destination needs
  saying, and one template makes the invariant testable.
- **Resuming the Lane-2 queue after user speech finishes.** Rejected as
  disorienting: a User navigating mid-turn has chosen to look rather than
  listen; stale narration arriving late is worse than silence.
- **The -1 before-the-list detail state.** Rejected: the entry utterance
  already speaks the title, so "reveal on first arrow" buys nothing and
  costs a state.
- **Per-surface empty nouns** ("no decks", "no replays"). Rejected: warmer,
  but N phrasings to keep consistent for zero information gain.
- **Silence or edge words ("top"/"bottom") at boundaries.** Rejected:
  silence is indistinguishable from a missed keypress; edge words are new
  vocabulary. Repeating the title is what HSA-conditioned ears expect.
- **Jump-means-fresh re-entry.** Rejected: it punishes the User for taking
  the fast route — jump-to-Cards and back-to-Cards should land in the
  same state.

## Consequences

**Positive.** The grammar is testable as invariants: same place sounds the
same on every route; no utterance ever contains an internal id; display,
movement speech, and detail line 0 are one string; no -1 state exists; no
Lane-2 utterance ever interrupts Lane 1. The single formatter forces the
module-seams design (ticket #24) to put speech in exactly one place. Entry
announcements, help (F1), and reread all reuse one template.

**Negative.** Every presenter's speech code is rewritten against the
contract. Display rows get thinner (title only — today's "Fireball -- 4
mana -- MINION" debug richness moves into detail lines). Shipped phrasings
users may know ("Deleted. 3 replays", "Copied Fireball") change shape.
ADR-0004's entry-announcement example no longer reflects the contract —
this ADR is its correction.
