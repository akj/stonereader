# Replay Viewer: the events zone scrubs the replay

## Status

Accepted (design contract, 2026-08-16; revised the same day: turns land on
their first event, and F5/F6 step events from any zone). Builds on ADR-0002
(state-pair events), ADR-0004 (contract), ADR-0007 (announcements), ADR-0008
(events-zone auto-play), ADR-0010 (seams), and ADR-0013 (a Replay is the only
navigable history). Amends the ui-spec's Replay Viewer section and its
cursor-persistence clause as it applies to the events zone.

## Context

Turn stepping is the Replay Viewer's coarse axis: PageUp/PageDown lands on a
turn and every zone shows that turn's **final** state. What happened *inside*
the turn is only a list — the `Y` events zone names each event, but selecting
one moves nothing. The User who wants to know how the board got this way must
run the diff in their head, event label by event label.

The data to do better already exists and was being thrown away. A
`ReplayState` holds one `GameState` snapshot per game packet — far finer than
turns — and every **Game event** is derived from a pair of adjacent snapshots
(ADR-0002), so each event has a natural "the game just after it" snapshot.
`turns()` discarded all but the last snapshot per turn.

## Decision

### The events zone is the fine axis

Selecting an event in the events zone renders **every other zone at the game
just after that event**: jump to a board, hand, or hero zone and it reads
as of that moment. The cursor moves with the keys the zone already has —
Left/Right, 1–9/0, Home/End — so the replay gains a second axis with zero new
chords: PageUp/PageDown steps turns, the events zone steps moments.

### A turn reads forward

A turn step lands the events cursor on the turn's **first** event, so every
zone shows the turn as it begins and the next keystroke moves the story
forward. The turn's last event still carries the turn's final state, so
stepping to it — or pressing End in the events zone — reads the turn as it
ended.

### F5 and F6 step events without leaving the zone

`F5`/`F6` (previous / next event) move the events cursor from **any** zone:
stay on the board and watch it change event by event. They are Replay Viewer
surface bindings only — registered neither in a universal layer nor as OS
global hotkeys. Each step speaks the event's title line, exactly what
stepping inside the events zone speaks, and fires the same auto-play. At the
turn's edges they clamp and repeat the current title — the boundary idiom
turn stepping already uses. Turn boundaries stay the coarse axis's job:
`F6` at the last event does not roll into the next turn; press PageDown and
read on.

### The events cursor is the replay position, not a browsing cursor

It persists across zone switches and back-reveal like any zone cursor
(ADR-0007), but a turn step repositions it to the new turn's first event —
that is the one amendment to the cursors-persist-across-turn-steps clause.
Every other zone's cursor keeps the unamended rule.

### Nothing new is spoken or played

Landing on an event — by any route, including F5/F6 — speaks the event row
and auto-plays its sound exactly as shipped (ADR-0008); turn stepping stays
speech-only and silent. Zone landings speak the unchanged context-entry
utterance — no "after {event}" prefix anywhere. Where the replay stands
within a turn is the events zone's position, `"{n} of {count}"`, and nothing
else's business. Live Game binds F5/F6 to the announced no-op "No events in
a live game" — the Y phrase, the same dialect asymmetry.

## Alternatives considered and rejected

- **Scrubbing only from inside the events zone** (the first draft of this
  ADR). Rejected the same day: round-tripping through `Y` to watch the board
  change is exactly the clumsiness the fine axis exists to remove; `F5`/`F6`
  step the moment from wherever the User stands.
- **F5/F6 rolling across turn boundaries.** Rejected: turn boundaries are
  the coarse axis's job, and the clamp keeps the two axes distinct.
- **Landing turns on their last event** (the first draft's rule, which kept
  turn stepping byte-identical to the pre-scrubber viewer). Rejected: a turn
  is a story read forward; landing at its end made every scrub start with
  Home.
- **Splitting snapshots into more, finer "turns".** Rejected: it would make
  `"Turn {t}"` labels lie about the game's own turn structure.
- **"After {event}" prefixes on zone labels while scrubbed.** Rejected as the
  same repetition ADR-0013 rejected for live turn prefixes; route invariance
  of the context-entry utterance stays absolute (ADR-0007).
- **Keeping `TurnView` collapsed and re-diffing inside the viewer.** Rejected:
  snapshot retention belongs where turns are built; the viewer consumes, it
  does not reconstruct.
