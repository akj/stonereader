# Cards sideways, records up and down; Enter follows the fact

## Status

Accepted (design contract, 2026-10-10). Amends ADR-0004 (which Surfaces are
horizontal lists), ADR-0006 (where Statistics and the import actions live),
ADR-0007 (empty zones, and what a zone switch repeats), ADR-0009 (help
ordering and key ranges), ADR-0012 (the Statistics surface), ADR-0013 (Live
Game with no game), and the ui-spec's "Enter in v1" ruling. ADR-0003's HSA
keymap is unchanged.

## Context

A recorded walk through the shipped app (every keypress and utterance,
driven through the real wiring) found that browsing felt confusing and
disjointed:

- The arrow axis rotated between neighbouring Surfaces — Home Up/Down, Decks
  Left/Right, Import Deck Up/Down, Cards Up/Down, Card Browser Left/Right —
  by a rule ("anything with detail lines is horizontal") the User cannot feel
  from where they stand. HSA itself uses horizontal lists only for cards and
  hero choices; Decks became horizontal because an ADR-0007 example
  utterance carried a position.
- Decks and Replays ended in action rows ("Import deck…", "Statistics…")
  posing as items in a list of records.
- Enter said "Nothing to do here" on Statistics, Card Browser, Deck detail,
  Live Game, and the Replay Viewer. Facts were shown but never followable:
  a deck's record lived in a separate list, its games in an unfiltered one.
- Absence dominated: "No Your board on this screen" for an empty board,
  "Remaining Deck: empty" for a Live Game with no game running.
- A Replay Viewer zone switch re-spoke the unchanged turn before the zone.

## Decision

### The axis rule

**Cards and game state move sideways; everything else moves up and down.**
Horizontal lists are Card Browser, Deck detail, Live Game, and the Replay
Viewer. Every other Surface — including Decks, Replays, and the new Deck and
Games Surfaces — is a vertical menu. Records lose Up/Down detail lines;
instead each row's Title line carries what tells it apart, most important
first, and omits the usual case.

### Decks

Vertical menu. Options in order:

1. **All decks**, `"All decks, {record}"` — opens the Deck Surface for the
   whole Stats corpus.
2. One option per saved deck: `"{name}[, {Class}][, Wild][, {n} cards],
   {record}"`. Class is omitted when the name already contains it; Wild is
   said only for Wild decks; the card count only when it is not 30.
3. **Other games**, `"Other games, {record}"` — only when the corpus holds
   games not counted under any saved deck (unattributed, deleted decks,
   non-constructed). All decks always equals the saved decks plus Other
   games.
4. `"Import deck…"`.

A record reads `"{W} wins, {L} losses"`, appending `", {T} ties"` only when
nonzero, with counts in agreement ("1 win, 1 loss"); zero games reads
`"no games yet"`. Enter opens the option. C copies the focused deck's code;
Delete/Shift+Delete delete the focused deck (ADR-0004's idiom); on a
non-deck option those keys announce their existing no-ops.

### Deck (the deck page)

Vertical menu, a Drill-down from Decks or from Replays' D. Window title and
context label are the subject's name ("Odd Hunter", "All decks", "Other
games"). Options:

- `"Cards, {n}"` — saved decks only; opens Deck detail.
- `"Games, {record}, {p} percent"` (percent only when any game was decided;
  `"Games, none yet"` with no games) — opens the Games Surface for exactly
  the games that record counts. With no games, Enter announces `"No games
  yet"` and does not push.
- `"Last 20 games, {record}"` — only when there are more than 20 games.
- One `"Versus {Class}, {record}"` per opponent class, most games first —
  each opens the Games Surface for those games.
- `"Copy deck code"` and `"Delete deck"` — saved decks only. Delete deck
  arms on Enter ("Press Enter again to delete {name}") and deletes on the
  second Enter, then pops to Decks with `"{name} deleted"` followed by the
  Decks landing. Delete/Shift+Delete and C also work anywhere on the page.

**Every record row opens the games behind it** — the follow-the-fact rule.
The Statistics Surface is retired; its facts live on Deck pages.

### Games

Vertical menu, a Drill-down from a Deck page record row. Context label names
the selection: `"{name} games"`, `"{name} versus {Class}"`,
`"{name}, last 20 games"`, with `"All games"` / `"Other games"` standing in
for the name on those subjects. Rows are Replays rows, without the deck name
when the list is one saved deck's. Enter opens the replay; Delete and
Shift+Delete delete it. No stats toggle (a toggle here would remove the row
from under the cursor) and no import row.

### Replays

Vertical menu, newest first, then `"Import replays…"`. Row Title line:
`"{Outcome} {Class} in {n} turns, {when}[, {deck}][, {game type}][, {format}][, imported][, not counted]"`
— outcome is "Won against", "Lost to", "Tied with", or "Result unknown
against"; `when` is "today 3:36 PM", "yesterday 9:10 PM", a weekday within
the last week, otherwise "August 16" (with the year when not this year);
game type is said only when it is not Ranked, format only when not Standard,
and unknown values are omitted rather than spoken as "Unknown". Enter opens
the replay; Space toggles stats membership; Delete/Shift+Delete delete;
**D opens the Deck page of the deck the game was played with**, or announces
`"No saved deck for this game"`.

### Enter follows the fact in the Replay Viewer

In the played and drawn zones, Enter moves the replay position to the event
where that card was played or drawn and lands in the Events zone on it.
Elsewhere in the Replay Viewer, and on Card Browser, Deck detail, and Live
Game, Enter stays an announced no-op.

### Opening a replay starts at the beginning

Every open of a replay (from Replays or Games) lands on the Events zone at
the game's first event, with every other zone cursor reset. Back-reveal
(from help or the Sounds menu) still finds the Replay Viewer as left.

### Empty zones are places

A zone letter for an empty zone switches to it and speaks
`"{Zone label}: empty"`; arrows, Home/End, and digits in an empty zone repeat
that. The "No {zone} on this screen" template is retired.

### What changed comes first

A Surface may declare a surface-wide context prefix (the Replay Viewer's
turn: `"Your turn {t}"` / `"Opponent's turn {t}"`). The prefix is spoken on
landing, orientation reread, and in-place rebuilds that change it (turn
step, event jump); a zone switch and empty-zone repeats omit it. Full form:
`"Opponent's turn 3, Events, Threads of Despair revealed, 2 of 20"`; zone
switch: `"Your board, Bloodmage Thalnos, 1 of 3"`.

### Live Game says its state

With no game in progress, landing on Live Game speaks
`"Live Game, waiting for a game"`, and every zone letter, query, and
navigation key there speaks `"Waiting for a game"`. Home's option reads
`"Live Game, waiting for a game"` or `"Live Game, turn {t} versus {Class}"`
during a game. During a game, entry is unchanged (zone utterance, no turn
prefix — ADR-0013).

### Help

F1 always opens a Help menu on its widget-type sentence. Bindings that share
one help phrase (digits) are one option. Enter's phrase comes first, then the
Surface's keys in the order its spec lists them, then Universal keys and All
commands.

### Copy and data hygiene

Counts agree with their nouns everywhere. Class keys are spoken through one
formatter ("Death Knight", never "Deathknight"). Card text carries no
markup ("[x]", "@", "$", "#", tags), set names are spoken names (never
"HERO_SKINS"), and Card Browser lists cards that can go in a deck — hero
skins and other cosmetics are excluded.

### Signature sound

Reaching a replay's game-over event plays the victory or defeat jingle under
the Replay auto-play setting — the one place StoneReader marks a moment with
sound beyond the event clips themselves.

### The window

The window shows where the User is: a heading with the stack path
("Decks › Odd Hunter › Cards"), the list, and the current item's detail
lines beside the list rather than below it.

## Alternatives considered and rejected

- **Keep records horizontal and announce the widget type on entry.**
  Rejected: it explains the rotation instead of removing it, and ADR-0004
  already rejected announcing the type.
- **A separate record page between Deck and Games.** Rejected: one more hop
  for every fact; the Deck page holds the record rows directly.
- **D on the Games Surface.** Rejected: the Deck page is already on the stack
  beneath it, and ADR-0006's stack forbids a Surface appearing twice.
- **Hero greeting on replay open as the signature sound.** Rejected: clip
  names cannot identify emote lines (audio research, finding 13); the
  victory and defeat jingles are name-identifiable.

## Consequences

**Positive.** The axis is predictable from what is under the cursor. Every
record fact is followable to its games, and every game to its deck.
Navigation speaks presence and change, not absence and repetition.

**Negative.** Record rows are longer than bare names (the User interrupts
with the next arrow). Statistics' muscle memory is lost. The Decks and
Replays help phrases and keymaps change shape. The ui-spec sections for
Decks, Replays, Statistics, Live Game, Replay Viewer, Home, and Help are
rewritten against this ADR.
