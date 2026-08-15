# Deck and replay statistics surface

## Status

Accepted (design contract, 2026-08-15). Builds on ADR-0004 (contract),
ADR-0006 (topology slot), ADR-0007 (title lines and announcements), and
ADR-0010 (seams). Implementation lands via PRDs opened against the final UI
spec (wayfinder map #17); nothing here ships code by itself. Decided in
ticket #33.

## Context

The replay store (PR #16) records every finished live game: result
(WON/LOST/TIED), friendly and opponent class, turn count, game type
(ranked/casual/arena/Battlegrounds), format, timestamp, and a source column
distinguishing live-recorded games from manual imports. What it does not
record: which saved deck was played — the `deck_id`/`deck_name` columns
exist but have no writer, even though Live Game already auto-detects the
played deck (exact revealed-card match against exactly one saved
deckstring) and simply never hands the answer to the recorder. Two result
caveats: a missing playstate is silently recorded as `TIED` (never
`UNKNOWN`), and abandoned/disconnected games produce no row at all.
ADR-0006 fixed the surface's topology slot: a drill-down inside Decks.

## Decision

### The stats corpus is a membership, not a provenance rule

Statistics are computed over the **stats corpus**: the set of games the
User has said are theirs. Live-recorded games are members by default.
Imported replays are not — a watched replay isn't your result — but they
can join: the replay-import flow asks once per batch ("Count these N games
in your stats?"), and on the Replays surface **Space toggles the focused
game** in or out, with verb-past confirmations ("Included in stats" /
"Excluded from stats" — cursor-neutral, no re-entry utterance). Membership
shows as a detail line on the replay row ("Counted in stats" / "Not
counted"), never in its title. One caveat is documented rather than
solved: an imported replay is counted from its own recorded perspective,
so a replay recorded from the opponent's side attributes the wrong side's
result — the toggle is the remedy, not detection.

Deck statistics cover constructed games (ranked and casual, unfiltered —
locally the question is "does this deck win", not ladder purity). Arena
and Battlegrounds games are excluded: neither plays a saved deck.

### Attribution: deck identity, snapshotted, backfilled

Games are attributed by **`deck_id`, with the deck name snapshotted at
save time**. Editing a saved deck keeps its history; deleting one leaves
its games grouped under the snapshotted name. The recorder gains the
plumbing Live Game's detection already earned: detected deck id and name
are written at save. A **one-time backfill migration** re-derives
attribution for existing replays from their stored XML using the same
exact-unique-match rule; ambiguous or unmatched games stay unattributed
and appear under one **Other games** grouping, which still counts in the
overall record.

### The win-rate formula

Win rate is **wins ÷ (wins + losses)**. Ties are spoken only when nonzero
(vanishingly rare in constructed; the conditional omission matches
ADR-0007's empty-state economy). Going forward the recorder writes
`UNKNOWN` instead of a fabricated `TIED` when no playstate was observed;
unknowns are excluded from the rate. Abandoned games' absence from the
denominator is accepted — they are unobservable, and counting them as
losses would punish disconnects.

### The Statistics surface

One surface, reached by a **"Statistics…" option row in Decks** (beside
"Import deck…", per ADR-0006's drill-down idiom) — the only door in v1.
It is a **horizontal list, single zone**. Rows, in order: **All decks**
(the overall record) first; then every attributed identity and saved deck
ordered by most recently played (zero-game saved decks included — a deck
that vanished from Statistics would read as an attribution bug); **Other
games** last.

Title line (displayed row = movement speech = detail line 0, per
ADR-0007): `"{Name}, {W} wins, {L} losses"`, appending `", {T} ties"`
only when nonzero; zero-game decks say `"{Name}, no games yet"`. The
percent deliberately stays out of the title: at local sample sizes the
raw record is the honest headline ("2 wins, 0 losses" tells the truth
that "100 percent" hides).

Detail lines, one fact per line:

1. `"Win rate, {p} percent"`
2. `"Last 20 games, {w} wins, {l} losses"` — the fixed recency window;
   omitted when the total is 20 or fewer (it would repeat line 0)
3. One line per opponent class with at least one game, ordered by games
   played descending: `"Versus {class}, {w} wins, {l} losses"`

**Enter is an announced no-op** in v1. The natural fill — drilling into
the deck's games as a filtered Replays view — is real future value but
specs a filtered-list capability this surface doesn't own; the door stays
marked for whichever effort (mulligan helper, collection tracking) needs
filtered lists first.

### Seams

Per ADR-0010, a **stats service** over the replay store computes on
surface entry — no caching, no persisted aggregates; local scale makes
recomputation free. The Statistics surface is an ordinary declaration fed
by it. Data-layer work the PRDs inherit: recorder plumbs detected
deck id/name at save (columns exist); recorder writes `UNKNOWN` for
missing playstates; `in_stats` flag with live-recorded-in /
imported-out defaults; the one-time backfill migration on first
post-upgrade launch (logged); the dead v1 `games` table is dropped, not
revived.

## Alternatives considered and rejected

- **Provenance as the corpus rule** (count `live_auto`, exclude all
  imports). Rejected: users arrive with years of prior .hsreplay logs
  that are genuinely theirs; membership with defaults serves both truths.
- **Deckstring content identity as the attribution anchor.** Rejected: a
  one-card swap would shatter a deck's history; the deck as the User
  manages it — named, editable — is the thing they ask about.
- **New-games-only attribution (no backfill).** Rejected: the XML already
  holds the User's history; pretending stats started today is false
  poverty.
- **Percent in the title line.** Rejected for sample-size honesty; the
  rate lives one Down-press away.
- **Folding ties into losses.** Rejected: wrong on real ties, and the
  `UNKNOWN` fix addresses the pollution at the source.
- **Configurable recency windows / time filters.** Rejected: slicing
  dashboards over a store measured in dozens-to-hundreds of games mostly
  produces empty slices; one fixed window catches "this deck stopped
  working."
- **A letter mnemonic for the stats toggle.** Rejected: Space is the OS
  toggle idiom, unbound app-wide, and spends no letter HSA may claim
  later.
- **Enter drills into a filtered Replays view now.** Rejected as scope:
  a Replays capability deserving its own decision; noted as future work.

## Consequences

**Positive.** The surface is one declaration plus one service — the
ADR-0010 payoff realized on its first new surface. Every settled
invariant holds: title-line distinguishability, spoken-equals-displayed,
no silent Enter, verb-past confirmations. Closing this ticket unblocks
the final spec assembly (ticket #28).

**Negative.** The recorder changes shape (deck plumbing, `UNKNOWN`), and
a migration runs against every existing install's store. Space gets its
first app-wide binding — a precedent future surfaces will cite. The
imported-perspective caveat is documented, not solved. The 20-game
window is fixed by fiat; if it's wrong, changing it is cheap but
retrains the ear.
