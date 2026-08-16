# Live Game: full replay dialect, current-state only

## Status

Accepted (design contract, 2026-08-16). Builds on ADR-0003 (keymap policy),
ADR-0004 (contract), ADR-0007 (announcements), ADR-0008 (audio channel), and
ADR-0010 (seams). Amends ADR-0004's PageUp/PageDown clause and its four-zone
Live Game list. Retires the **Live game timeline** from CONTEXT.md.
Implementation lands via PRDs opened against the final UI spec (wayfinder
map #17); nothing here ships code by itself. Decided in ticket #34.

## Context

ADR-0004 gave Live Game four zones (`D`, `Shift+C`, `Shift+P`, `N`) while
asserting "inspecting a game is one dialect, live or replayed" — and the
Replay Viewer has sixteen zones plus five speak-only queries. Separately,
CONTEXT.md defined a **Live game timeline** — the navigable history of a game
in progress — that ADR-0004 bound PageUp/PageDown to, but no ADR ever
designed, and the shipped app cannot produce: the pipeline deliberately holds
one current `GameState`, overwritten per tracker callback (ADR-0002 made
events a pure downstream diff).

Three facts decided this ticket. First, a live `GameState` is already a full
both-sides snapshot: fifteen of the sixteen replay zones and all five queries
read fields the engine populates live today; only the events zone needs a
state *sequence*. Second, the replay dialect's letters are HSA's own in-game
keys (b/g boards, c hand, v/f heroes, w/s weapons/secrets, a/d/r queries) —
an HSA-fluent player already presses exactly these during a live game. Third,
no shipped tracker offers mid-game history: HSDT and Firestone confine review
to post-game replays because the real client renders its own play-history
strip, and HSA's in-game `y` ("Open the play history log") is precisely the
accessible version of that client feature.

## Decision

### Full zone inventory, current-state only

Live Game speaks the Replay Viewer's full dialect: the same **fifteen
navigable zones** and **five speak-only queries**, identical letters and help
phrases, reading the current `GameState` and nothing else. Zone labels are
shared with the Replay Viewer, with two changes on the live side: `D` is
labeled **Remaining Deck** (its live meaning — `Zone.DECK` minus draws,
grouped by card, per ADR-0007's worked example), and the former "Cards Drawn"
label becomes **Your drawn**, forced by `Shift+N` (Opponent drawn) joining
the surface. Live-specific title lines are kept where they carry live-only
facts (Opponent hand's positional identity-where-known rows and drawn-turn
lines). (The ui-spec later retired the live Opponent hand zone by this ADR's
own client-redundancy principle — live, `Shift+C` is an announced no-op like
`Y`, and the inventory is fourteen zones. The ui-spec is current.)

### No live history — the client is in the room

The **Live game timeline is retired from the domain model.** Mid-game state
stepping exists in no tracker because sighted players get "what happened"
from the client itself; the blind player's equivalent is HSA's `y` in the
client. StoneReader duplicating it is the same mistake as doubling the
client's audio, so the ruling extends ADR-0008's principle — *the real
client is in the room* — from audio to history. Consequently on Live Game,
**Y** and **PageUp/PageDown** are constant announced no-ops ("No events in a
live game"; "No turns to step in a live game"), joining L's "No game audio
during a live game". Live Game holds **zero buffered state**; reviewing a
finished game is the Replay Viewer's job, reached because every completed
live game already persists as a Replay via the recorder.

### Tracker-style intel: draw chance now, secrets helper later

What live players actually use trackers for is targeted hidden-info intel,
and the zones are that intel. One computed line joins them: **Remaining Deck
gains a draw-chance detail line** — `"{p} percent to draw"`, nearest whole
percent, copies remaining over cards remaining — HSDT's headline overlay
number, pure arithmetic on counts the state already holds. A secrets helper
(which secrets are still possible) is the strongest remaining overlay idea
but needs per-format secret-pool data, so it goes to map #17's fog as a
future research candidate rather than a spec ruling. No other counters.

### Bare context labels

Live zone landings keep the plain `"{Zone label}, {title}, {position} of
{count}"` utterance — no turn prefix. The Replay Viewer's "Turn {t}, {yours |
opponent's}" label exists because turn stepping changes what every zone
means; live, the turn is ambient (the client announces it; Lane 2 originally
doubled it, until the ui-spec retired turn narration as client-redundant).
One dialect means the same keys mean the same things, not that every
utterance carries the same prefix.

## Alternatives considered and rejected

- **Four-zone hidden-info tracker.** Rejected: leaves ADR-0004's one-dialect
  claim false, deadens letters an HSA player's fingers already know, and
  saves nothing — the data is already flowing.
- **The full Live game timeline.** Rejected: unprecedented in any tracker,
  weak mid-game (the User is on a turn timer), and fully served post-game by
  the Replay Viewer the moment the game persists.
- **A live events zone showing the current turn.** Rejected: even this
  smallest history duplicates HSA's in-client `y`, and Lane-2 narration
  already speaks events as they happen.
- **Turn-prefixed live labels for dialect symmetry.** Rejected as repetition
  ADR-0007 fought elsewhere.
- **The full helper suite (secrets, counters) now.** Rejected as scope; the
  secrets helper is fog, not forgotten.

## Consequences

**Positive.** "One dialect, live or replayed" becomes literal architecture —
one zone vocabulary, one set of help phrases, current state or snapshot as
the only difference. Zero new data plumbing: every added zone and query
reads existing `GameState` fields. ADR-0002's state-only stance is
vindicated end-to-end; no component anywhere retains history during a live
game.

**Negative.** A CONTEXT.md term dies, and its persistence bullet is reworded
(the recorder, not a timeline, was always the persistence path). "Cards
Drawn" is renamed, retraining the one existing user. The events zone is the
dialect's one asymmetry — navigable replayed, a constant no-op live — and
the draw-chance line is the spec's first computed (non-projection) detail
line, a precedent future intel ideas will cite.
