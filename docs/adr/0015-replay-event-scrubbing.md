# Replay Viewer: the events zone scrubs the replay

## Status

Accepted (design contract, 2026-08-16). Builds on ADR-0002 (state-pair
events), ADR-0004 (contract), ADR-0007 (announcements), ADR-0008 (events-zone
auto-play), ADR-0010 (seams), and ADR-0013 (a Replay is the only navigable
history). Amends the ui-spec's Replay Viewer section and its cursor-persistence
clause as it applies to the events zone.

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

### The last event carries the turn's final state

A turn's last event shows the turn as it ended. A fresh turn landing
positions the events cursor on that last event, so plain turn stepping
sounds and reads exactly as it did before this ADR, and End always returns
the zones to the turn's final state.

### The events cursor is the replay position, not a browsing cursor

It persists across zone switches and back-reveal like any zone cursor
(ADR-0007), but a turn step repositions it to the new turn's last event —
that is the one amendment to the cursors-persist-across-turn-steps clause.
Every other zone's cursor keeps the unamended rule.

### Nothing new is spoken or played

Landing on an event speaks the event row and auto-plays its sound exactly as
shipped (ADR-0008); turn stepping stays speech-only and silent. Zone landings
speak the unchanged context-entry utterance — no "after {event}" prefix
anywhere. Where the replay stands within a turn is the events zone's position,
`"{n} of {count}"`, and nothing else's business.

## Alternatives considered and rejected

- **A dedicated fine-axis chord pair usable from any zone** (step events
  without leaving the board). Rejected for now: it costs new chords —
  surfaces cannot bind slot keys (ADR-0010) — and the events zone already
  owns full list navigation. Revisit only if round-tripping through `Y`
  proves clumsy in real use.
- **Splitting snapshots into more, finer "turns".** Rejected: it would make
  `"Turn {t}"` labels lie about the game's own turn structure.
- **"After {event}" prefixes on zone labels while scrubbed.** Rejected as the
  same repetition ADR-0013 rejected for live turn prefixes; route invariance
  of the context-entry utterance stays absolute (ADR-0007).
- **Keeping `TurnView` collapsed and re-diffing inside the viewer.** Rejected:
  snapshot retention belongs where turns are built; the viewer consumes, it
  does not reconstruct.
