# StoneReader UI specification

## Purpose

This is the per-surface specification implementation PRDs open against. It folds
every decision locked in ADR-0003 through ADR-0017 into one document: the
cross-cutting contracts every **Surface** obeys, and then, for each Surface, its
**Widget type**, its stack behavior, its window title and **Context-entry
utterance**, its rows or **zones** and their detail lines, its complete key
bindings with the spoken help phrase each one carries, and its speech, **Game
audio**, and Settings behavior. Nothing here is argued — every normative
statement cites the ADR that decided it. A PRD written against a section of this
document should have nothing left to decide except code.

**Status:** Final, assembled 2026-08-15 against ADR-0003…0012, amended
2026-08-16 for ADR-0013 and ADR-0014 (wayfinder map
[#17](https://github.com/akj/stonereader/issues/17), tickets #28, #34, and
[#35](https://github.com/akj/stonereader/issues/35)), amended for ADR-0015 and
ADR-0016 as they landed, and amended 2026-10-10 for ADR-0017 (cards sideways,
records up and down; the Deck and Games Surfaces; the window heading and
detail pane). No open questions remain: every section is normative and
PRD-ready. Nothing here ships code by itself.

Where an ADR left a detail to the per-surface spec, or where two ADRs could be
read against each other, this document rules and says so inline ("this spec's
ruling"). A ruling is as binding as an ADR citation.

## ADR index

| ADR | Governs |
|---|---|
| [0003](adr/0003-navigation-mirrors-hearthstone-access.md) | HSA-mirroring keymap policy: zone letters, Shift's two meanings, numbers, speak-only queries |
| [0004](adr/0004-app-wide-keyboard-navigation-contract.md) | App-wide keyboard contract: two widget types, universal keys, **Text mode**, delete idiom, numbers |
| [0005](adr/0005-native-wxpython-over-web-ui.md) | Platform: native wxPython, direct screen-reader speech APIs, native global hotkeys |
| [0006](adr/0006-screen-topology-and-information-architecture.md) | Topology: Home menu and letters, **Screen jump** vs **Drill-down**, system-wide hotkeys, window title, no menu bar |
| [0007](adr/0007-announcement-grammar.md) | Announcement grammar: **Context-entry utterance**, **Title line**, detail lines, cursors, the two **Speech lanes**, queries and confirmations |
| [0008](adr/0008-hearthstone-audio-channel.md) | **Game audio**: runtime extraction, channel contract, per-surface audio, the listen key and the **Sounds menu** |
| [0009](adr/0009-help-model-self-documenting-keymap.md) | **Help menu**: generated from the command registry, key-first ordering, Enter-executes, DL-008 retirement |
| [0010](adr/0010-module-seams-declarative-surfaces.md) | Seams: declarative surfaces, two widget-type engines, command registry with layers and slots, one input sink, Announcer and Narrator, navigation controller |
| [0011](adr/0011-settings-surface.md) | Settings surface, **Narration preset**, **Picker** idiom, **Capture mode**, global-hotkey rebinding, persistence and defaults |
| [0012](adr/0012-deck-replay-statistics-surface.md) | **Stats corpus** membership, deck attribution, win-rate formula (its Statistics surface is retired by ADR-0017) |
| [0013](adr/0013-live-game-current-state-full-dialect.md) | Live Game: full replay dialect current-state only, no **Live game timeline**, draw-chance line, bare labels |
| [0014](adr/0014-how-stonereader-asks.md) | Asking: the closed idiom inventory, the **Offer** and Ctrl+Enter, OS-dialog delegation, replay import |
| [0015](adr/0015-replay-event-scrubbing.md) | Replay event scrubbing: the events zone as the fine axis, F5/F6 from any zone, turns read forward |
| [0016](adr/0016-distribution-and-auto-update.md) | Distribution: the per-user installer, GitHub Releases as the update feed, updates that prompt and never happen silently |
| [0017](adr/0017-cards-sideways-records-up-and-down.md) | The axis rule, **Records** and the Deck and Games Surfaces, Enter follows the fact, empty zones as places, the surface-wide context prefix, Live Game's waiting state, help order, data hygiene, the window heading and detail pane |

ADR-0001 (Power.log over memory reading) and ADR-0002 (state-only prev/curr
dispatch) govern the data pipeline below this spec and are not restated here.

---

# Cross-cutting contracts

These hold on every Surface. A per-surface section below may fill a slot or add
a surface-layer binding; it may never restate or override anything here
(ADR-0010: a lower registry layer structurally cannot shadow an upper one).

## Widget types

Every Surface presents exactly one **Widget type**; there is no third
(ADR-0004). Two widget-type engines interpret surface declarations and own
cursor movement, key dispatch, boundary behavior, and announcement triggers
(ADR-0010).

**The axis rule: cards and game state move sideways; everything else moves
up and down** (ADR-0017). The horizontal lists are exactly Card Browser, Deck
detail, Live Game, and the Replay Viewer. Every other Surface — Home, Decks,
Deck, Games, Replays, Cards, Settings, every form, Picker, help Surface, and
the Sounds menu — is a vertical menu. The User can tell the axis from what is
under the cursor. A **Record** row carries what tells it apart in its option
title, most important first, and omits the usual case; records have no detail
lines (ADR-0017).

**Vertical menu** — a cursor over options.

| Key | Action |
|---|---|
| Up / Down | Previous / next option |
| Enter | Act on current option |
| Home / End | First / last option |
| Shift+Up | Reread current option |
| Left / Right | Unbound and silent — the widget-type signal (ADR-0004, reaffirmed ADR-0011) |
| Letters | Bound as jump-and-activate shortcuts only where a surface section below assigns them |

**Horizontal list** — a cursor over items, each with detail lines.

| Key | Action |
|---|---|
| Left / Right | Previous / next item |
| Up / Down | Previous / next detail line of current item |
| Shift+Up | Repeat current detail line (orientation reread, ADR-0007) |
| Shift+Down | Read from current detail line to the last |
| Home / End | First / last item |

Forms are vertical menus whose options are fields and actions (ADR-0004). A
horizontal-list Surface may declare **zones**; the engine owns per-zone cursors,
their persistence across switches, and zone-switch context-entry utterances
(ADR-0010). **Empty zones are places** (ADR-0017): a zone letter for an empty
zone switches to it and speaks `"{Zone label}: empty"`, and arrows, Home/End,
Shift+Down, and digits there repeat that utterance. The "No {zone} on this
screen" template is retired (ADR-0017, retiring ADR-0009's phrase). A
horizontal list may also declare a surface-wide context prefix and a waiting
state (see [Announcement grammar](#announcement-grammar)). Vertical menus have
no zones, no prefix, and no waiting state (ADR-0010, ADR-0017).

## Universal keys

Universal keys are registered on the universal layer; a Surface fills a slot by
command id or gets the slot's announced-no-op default (ADR-0010). **No universal
key ever dies silently** (ADR-0004). Unbound non-universal keys stay silent
(ADR-0004).

| Key | Command | Invariant |
|---|---|---|
| Enter | Slot — surface-assigned | Acts on the current item; never a silent no-op (ADR-0004) |
| Escape / Backspace | Back | Injected centrally by the navigation controller, never bound per-surface; announced no-op at the stack root — "Home — already at the top" (ADR-0004, ADR-0006, ADR-0010) |
| Home / End | First / last | Whatever the widget type's cursor covers (ADR-0004) |
| PageUp / PageDown | Slot — coarse axis | Pages on collection Surfaces, turns in the Replay Viewer; announced no-op elsewhere. Related-card content (HSA's in-game PageUp/Down meaning) lives in the detail-line stream instead; a surface spec may add a dedicated key if that proves insufficient (ADR-0004) |
| Tab / Shift+Tab | Slot — group jump | Group jump where the Surface has groups; announced no-op where it has none. Never focus traversal (ADR-0004) |
| Ctrl+F | Slot — search | Opens a typed search field on Surfaces that support it; "No search on this screen" elsewhere (ADR-0004) |
| F1 | Help | Pushes the **Help menu** from every Surface (ADR-0004, ADR-0009) |
| L | Slot — listen | Drills into the **Sounds menu** for the card under the cursor; announced no-op where no card is focused (ADR-0008, ADR-0010) |
| Ctrl (bare tap) | Stop game audio | Listens in the input layer below the registry; a lone modifier is never a chord (ADR-0008, ADR-0010) |
| Ctrl+Q / Alt+F4 | Quit | The only quit; Escape is never quit (ADR-0004) |

The five slots are exactly Enter, Tab/Shift+Tab, Ctrl+F, PageUp/PageDown, and L
(ADR-0010); the enumeration is exhaustive.

**App-wide idioms are not universal keys.** Delete, Shift+Delete, and Space are
**surface-layer bindings** — ADR-0010's slot enumeration does not include them
and ADR-0004's universal-key table never listed them. Where a Surface binds
them, they obey the app-wide idiom: Delete arms ("Press Delete again to delete
{item}"), a second Delete on the same item acts, any cursor movement disarms,
and there are no modal confirmation dialogs (ADR-0004); Shift+Delete acts
without arming, per HSA's Shift-skips-confirmation meaning (ADR-0004); Space
toggles **Stats corpus** membership, the precedent ADR-0012 set on Replays.
Where a Surface does not bind them they are unbound non-universal keys and
therefore stay **silent** — not announced no-ops (ADR-0004).

Digits are surface-class-dependent and **never switch zones** (ADR-0003,
ADR-0004): on game-state Surfaces 1–9 jump to positions 1–9 and 0 to position
10; on collection Surfaces they filter by mana cost, 0–8 exact and 9 meaning 9+,
single-select with re-press to clear. The 8 and 9 buckets are a deliberate,
purely additive extension of HSA's 0–7 filter, and the one visible divergence is
recorded: where HSA's 7 means "7 or more", StoneReader's 7 means exactly 7
(ADR-0004).

**Shift carries exactly two meanings** — opponent-side (Shift+C/D/W/S/A) and
skip-confirmation (Shift+Delete, HSA's Shift+E) — kept distinct, never collapsed
into one rule (ADR-0003).

All keyboard input enters through one frame-level sink that normalizes every
keystroke — including F-keys, Shift+Delete, and bare modifiers — into a chord
and routes it to the active Surface's registry. No child widget takes keyboard
focus; views are render-only subscribers (ADR-0010).

### Enter in v1

ADR-0004 requires every Surface to assign Enter an action or an announced no-op.
**Enter follows the fact** (ADR-0017): on a record it opens the games behind
it, on a game it opens the replay, and on a card in the Replay Viewer's played
and drawn zones it moves the replay to the event where that card was played or
drawn. On **Card Browser**, **Deck detail**, **Live Game** during a game, and
every other **Replay Viewer** zone, Enter is the announced no-op "Nothing to do
here": those are places to read (ADR-0017, superseding this spec's earlier
ruling, which also covered Statistics and every Replay Viewer zone). With no
game in progress, Live Game's Enter says "Waiting for a game" (ADR-0017).

**Future — not in scope for implementation PRDs:** a card-detail drill-down
behind Enter, HSA's Collection Manager idiom ("Enter: select item for more
options"). The detail-line stream carries that content today; the door is marked
and unbuilt.

## Input states

Navigation, **Text mode**, and **Capture mode** are the only three input states;
there is no fourth. Each is entered only by an explicit act and each has a
no-commit exit (ADR-0011). An armed **Offer** is a pending flag inside
navigation state — exactly as armed delete is — not a fourth input state
(ADR-0014).

| State | Entered by | Commit | Abandon |
|---|---|---|---|
| Navigation | Default | — | — |
| **Text mode** | Enter on a field, Ctrl+F (never on Surface entry) | Enter | Escape |
| **Capture mode** | Enter on a chord row (Settings → Global hotkeys) | Next chord pressed, subject to the acceptance policy | Escape |

In **Text mode** keystrokes go to the field: Backspace erases; Left/Right move
the caret one character and speak the character crossed; Home/End jump to the
ends of the field (ADR-0004 as refined by ADR-0011). F1 works in Text mode and
speaks the rescue without leaving the field: "Typing in {field}. Enter commits,
Escape cancels." (ADR-0009). Text mode is owned by the input layer, not by any
Surface (ADR-0010).

## Asking

**StoneReader never invents a dialog and never asks unsolicited** (ADR-0014).
OS-owned questions are delegated to OS-native dialogs; StoneReader's own
questions are expressed in the existing grammar. The inventory of asking
idioms is closed — there is no fifth (ADR-0014):

| Idiom | Question shape | Where it lives |
|---|---|---|
| **Confirm** | "Are you sure?" — press the same key again | Armed delete (ADR-0004); single-modifier chord warning (ADR-0011) |
| **Offer** | Unsolicited proposition — accept by dedicated chord, ignore for free | ADR-0014; below |
| **Form field** | A parameter with a default — the question dissolves | [Import Replays](#import-replays)' stats toggle (ADR-0014) |
| **Picker** | Solicited choice among values | ADR-0011 |

**The Offer.** An **Offer** is an ephemeral Lane-1 announcement that arms a
single dedicated accept chord: **Ctrl+Enter**, bound to nothing else anywhere
in the app, so acceptance is always deliberate and no surface key is ever
shadowed (ADR-0014). Lifetime rules (ADR-0014):

1. An Offer arms **only in navigation state**. If its trigger fires during
   Text or Capture mode, the Offer is dropped, not queued.
2. **Any keypress other than Ctrl+Enter disarms it silently** and does its own
   normal work — declining costs zero keypresses and no speech.
3. With no Offer armed, Ctrl+Enter is an ordinary unbound non-universal chord:
   silent (ADR-0004).
4. An Offer fires **once per unique subject** — re-triggering on the same
   subject does not re-offer.
5. The announcement names the chord as a spoken word sequence (ADR-0011):
   "… — press Control Enter to …".

Ctrl+Enter is therefore a reserved app-wide chord no Surface may bind; Capture
mode's already-bound refusal covers it — "Control Enter is taken by Accept
offer" (ADR-0014). The one v1 Offer is the
[clipboard deckstring offer](#navigation-stack-window-title-topology).

**OS delegation.** The dialog ban is on *invention*, not on modality: for a
question the OS already owns, StoneReader delegates to the OS-native dialog —
standard Windows UI the audience drives fluently every day (ADR-0014). This is
the third delegation of its kind: speech exits via the User's screen reader
(ADR-0008), game history stays in the client (ADR-0013), files belong to the
OS. The one v1 user is [Import Replays](#import-replays)' multi-select file
dialog; a delegated OS dialog is accepted as OS-owned UI, the same way the
screen reader owns speech (ADR-0014).

## Announcement grammar

The **Announcer** owns every speech template and both **Speech lanes**; it is
the only module that imports the TTS output, and a Surface has no way to speak
except by returning data (ADR-0010). The Surface's one text hook is its
**Title line** formatter (ADR-0007, ADR-0010).

**Context-entry utterance** — fires identically on every landing route: screen
jump, drill-down, back-reveal, zone switch, in-place rebuild (filter or search
change, and a Replay Viewer turn step or event jump), and orientation reread.
No route-specific phrasing exists beyond the context-prefix rule below
(ADR-0007, ADR-0017).

| Context | Utterance |
|---|---|
| Horizontal list or zone | `"{Context label}, {title}, {position} of {count}"` |
| Vertical menu | `"{Context label}, {current option}"` — no position |
| Empty context | `"{Context label}: empty"` — always the user-facing label, never an internal id; an emptied menu says the same ("Odd Hunter versus Warrior: empty") |
| Waiting | `"{Surface name}, waiting for {subject}"` — a horizontal list with nothing to browse yet ("Live Game, waiting for a game"); its browsing, zone, and query keys say `"Waiting for {subject}"` (ADR-0017) |

**What changed comes first** (ADR-0017). A horizontal list may declare a
**surface-wide context prefix** — the Replay Viewer's turn. The prefix leads
the utterance on landing, orientation reread, and in-place rebuild, which are
the routes where it may have changed: `"Opponent's turn 3, Events, Threads of
Despair revealed, 2 of 20"`. A zone switch and an empty zone's repeats omit
it, because the turn did not change: `"Your board, Bloodmage Thalnos, 1 of
3"`. Every other route to the same place still sounds the same; the zone
switch is the one route that says only what changed.

**Title lines.** Every item has exactly one Title line — the shortest string
that distinguishes it from its neighbors in that list. One formatter produces
it, used verbatim in three places: the displayed row, the movement utterance,
and detail line 0. It is written for the ear ("3 attack, 2 health", never "3/2")
and the display shows exactly that string (ADR-0007). Title content per Surface
is this spec's decision under ADR-0007's distinguishability test; ADR-0007
delegates the order of detail lines 1+ to this spec as well. A record's Title
line carries what tells it apart, most important first, and omits the usual
case (ADR-0017).

**Data hygiene** (ADR-0017). Counts agree with their nouns everywhere ("1
win", "2 losses", "1 turn", "1 secret", "1 file chosen",
"Opponent deck, 1 card"). Class keys are spoken through one formatter
("Death Knight", never "Deathknight"). Card text is the text the collection
shows, with no markup: no "[x]", "@", "$", "#", "{n}" placeholders, or tags,
numbers the card data supplies filled in, a slot that names a minion type
spoken as the type ("get 2 random Naga"), and in-play variants left out. Set
names are the game's own names, never internal keys ("HERO_SKINS"). A card's
name is never its card id: a card missing from StoneReader's card data reads
"Unrecognized card", with the detail line "Not in StoneReader's card data
yet" in place of its cost, and a card the game hid stays "Unknown card".

**Movement and boundaries.** Moving the cursor speaks the bare title, option, or
detail line — no position appended. Shift+Up is the orientation key: it re-fires
the context-entry utterance with the current detail line in the item slot, and
on line 0 reproduces the entry utterance exactly. A boundary press (Up at first,
Down at last, Left/Right at the ends) repeats the current bare title (ADR-0007).
There is no edge cue: ADR-0008 killed the synthetic-earcon channel ADR-0007
anticipated, so the title repeat stands alone.

**Cursors.** The −1 "un-announced" detail state does not exist: after entry or
movement the detail cursor rests on line 0 and the first Down goes to line 1. A
non-empty context's item cursor always rests on a real item. Back-reveal keeps
the revealed Surface exactly as left; zone cursors persist across zone switches;
a screen jump to a previously visited Surface also finds it as left — jumps
reset the stack, not the target's innards (ADR-0007). Surfaces are lazy
singletons, created on first visit and alive for the app's lifetime, so
persistence is structural (ADR-0010). Nothing is reset on leaving a Surface;
in particular Card Browser's mana filter and committed search survive leaving
and re-entering (ADR-0007). **A fresh open is new content** (ADR-0017):
opening a Deck page or a Games list starts at its first option, opening a
replay starts at the game's first event, and F1 opens the Help menu on its
widget-type sentence with no search. Back-reveal still finds each of them as
left.

**Two speech lanes.** Lane 1 (movement, entry, drive-by queries, confirmations)
always interrupts instantly. Lane 2 (auto-narration of **Game events**) queues in
order among itself, never interrupts Lane 1, and is dropped entirely by any
Lane-1 keypress — current utterance cut, queued events discarded (ADR-0007). The
**Narrator** is the single Lane-2 producer: a service owned by no Surface, so
narration continues wherever the User is standing, tuned live by the
**Narration preset** (ADR-0010, ADR-0011).

**Queries and confirmations.** Drive-by queries are subject-first and never a
bare number: `"{Subject}, {value}"` — "Your deck, 23 cards". Confirmations are
`"{Object} {verb-past}"` — "Fireball copied", "Aggro Shaman deleted". When an
action changes what is under the cursor, the confirmation is followed by a
re-fired context-entry utterance; cursor-neutral actions get the confirmation
alone (ADR-0007). Filter and search state ride in the context label — "Mage
cards, 3 mana, Fireball, 1 of 12" (ADR-0007); the composition rule for a label
carrying several constraints is specced on [Cards](#cards).

**Naming.** Cards is the class menu. Card Browser is its collection
Drill-down. Decks is the record menu: All decks, each saved deck, and Other
games. Deck is one subject's page of records and actions. Games lists the
games behind one record. Deck detail lists one saved deck's cards. A
Surface's display name — its window title and heading entry — is its
registered name unless it names its subject: a Deck page says the subject
("Odd Hunter"), Deck detail says "{Deck name} cards", Card Browser says the
class choice ("Hunter cards"), Games says its context label, and the Sounds
menu says "{Card name} sounds" (ADR-0006, ADR-0017). Help takes the display
name of the Surface it was opened from ("Odd Hunter help", "Hunter cards
help"); All commands lists Surfaces by registered name ("Deck commands").

## Navigation stack, window title, topology

- A **Screen jump** — a Home letter, Enter on a Home menu option, or a
  system-wide hotkey — resets the stack to `[Home, target]`. Back from any
  jumped-to Surface goes Home; duplicate stack entries are structurally
  impossible (ADR-0006).
- A **Drill-down** pushes one level; back pops exactly one (ADR-0006).
- Back is an announced no-op at Home (ADR-0004, ADR-0006).
- On every landing, by any route, the navigation controller fires the
  game-audio stop, the window-title and heading update, and the context-entry
  utterance via the Announcer (ADR-0010, ADR-0017).
- Window title is `"{display name} — StoneReader"`, updated on every stack
  change (ADR-0006; display names under [Naming](#announcement-grammar)).
- The User always chose to be here: no Surface change happens without a keypress
  (ADR-0006).

**The window** (ADR-0006, ADR-0017). The window shows where the User is: a
heading with the stack path, the current Surface's list, and, on a horizontal
list, the current item's detail lines in a pane beside the list. The heading
names every Surface on the stack below Home by its display name, joined by
" › ", and reads "Home" at Home. A name that repeats its parent's name after
a space or ", " drops it — "Decks › Odd Hunter › Cards",
"Decks › Odd Hunter › Versus Mage", "Replays › Replay Viewer › Help" — while
the window title keeps the full display name. When the heading is too long
for the window, its start gives way so the current Surface stays visible.
The list shows the rows that fit, scrolled the least distance that keeps the
current row in view, with the current row highlighted, and redraws on every
landing, so a deletion or a new subject never leaves stale rows on screen. A
vertical menu has no detail pane. The window is render-only: no part of it
takes keyboard focus, and speech never reads from it (ADR-0010).
There is no status bar and no `wx.MenuBar` (ADR-0006).

**System-wide hotkeys** (native OS registration, ADR-0005; rebindable in
Settings, ADR-0011). These dispatch through the same command registry as any
other input route, so none can die silently (ADR-0010).

| Hotkey | Command | Effect |
|---|---|---|
| Ctrl+Shift+L | Jump to Live Game | Screen jump to Live Game, landing on Remaining Deck (ADR-0006); with no game in progress it lands on the waiting utterance and switches no zone (ADR-0017) |
| Ctrl+Shift+C | Jump to Cards | Screen jump to Cards (ADR-0006) |
| Ctrl+Shift+R | Jump to Replays | Screen jump to Replays (ADR-0006) |
| Ctrl+Shift+D | Speak deck counts | Speak-only: "Your deck, {n} cards" ("Your deck, 1 card"), or "Waiting for a game" with no game in progress — navigates nowhere (ADR-0006, ADR-0007, ADR-0017) |

(ADR-0006's table also carried Ctrl+Shift+O, jump to the live Opponent hand,
and Ctrl+Shift+H, speak opponent hand count; *this spec's amendment* retired
both with the live Opponent hand zone itself — the client owns opponent-hand
information live.)

The Live Game hotkey is a **compound command**: a screen jump plus an
explicit zone switch, exactly equivalent to jumping and then pressing the zone
letter. *This spec's ruling:* it does not conflict with ADR-0007's found-as-left
persistence, which governs what no command touched — the stack resets because
the jump says so, the active zone changes because the command says so, and every
zone's own cursor still persists (ADR-0006, ADR-0007).

**Clipboard deckstring offer.** On window activation with a deckstring on the
clipboard — on whichever Surface the User is standing — StoneReader arms an
**Offer**: "Deck code on clipboard — press Control Enter to import"
(ADR-0014, amending ADR-0006's "press Enter" wording). It never pushes a
Surface; **accepting resets the stack to `[Home, Decks, Import Deck]`** with
the code pre-filled — neither a pure jump nor a pure drill-down, ruled as a
reset because route invariance is the design's spine: accepting always lands
the same place, and back pops to Decks, where the imported deck will be
(ADR-0014, ADR-0006). This preserves the invariant that the User always chose
to be here. The Offer's unique subject is the clipboard content (the shipped
same-content guard is kept), and **StoneReader's own copies write that
guard** — C on Decks or a Deck page never leads to an offer to import the code
the app just handed you (ADR-0014). The shipped `wx.MessageDialog` clipboard
modal is retired, along with the `restore_focus` hack's motivating case
(ADR-0014).

## Game audio channel

**Game audio** is Hearthstone's own audio, extracted at runtime from the User's
own install. StoneReader never ships it, never fetches it from a third party,
and never lets it leave the machine; with no install found the channel is absent
and says so, and the app is fully functional without it (ADR-0008). The Unity
version is detected at runtime, not pinned (ADR-0008; verified in
[the extraction fact sheet](research/hearthstone-audio-extraction.md)). The
sixth bright line rides with the channel: **the app stays free and
non-commercial and carries "not affiliated with Blizzard Entertainment / assets
© Blizzard" notices** (ADR-0008) — no v1 Surface carries them, so they land with
the onboarding/installer effort (see [Deliberate exclusions](#deliberate-exclusions)).

Channel contract (ADR-0008):

1. Game audio never delays or preempts speech; it mixes underneath the lanes.
2. Starting a new clip replaces the one playing — at most one at a time.
3. Surface transitions stop it (so Escape/Backspace silence it as a side effect
   of back, with no change to their one meaning).
4. A bare Ctrl tap stops it without moving.
5. Nothing else stops it: arrowing detail lines and exploring zones let a clip
   play out.
6. StoneReader owns an app-level volume for it, independent of speech.

Two services back it — an extraction/index service and an async player — touched
by the UI at exactly three points: the controller's transitions-stop hook, the
input layer's bare-Ctrl stop, and Surfaces requesting clips by card id and event
(ADR-0010). Clip names carry the mapping (`VO_<CardID>_…_<Event>_<NN>`), and
card-specific Foley extends the same CardID scheme to voiceless cards
(research fact sheet, findings 7 and 11).

## Help generation

The **Help menu** is a view of the command registry, never hand-written. A
binding cannot be registered without its spoken help phrase, and the
widget-type sentence is generated from the Surface's declared type (ADR-0009,
ADR-0010). No per-surface help text exists anywhere; the "spoken help phrase"
column in every keymap table below is the registry entry for that binding, and
the registry — not this document — is the runtime source of truth, which matters
for the six rebindable chords (ADR-0011).

A key that cannot apply speaks one constant short announced no-op every time
("Nothing to do here", "No events in a live game"). DL-008's
diminishing-verbosity behavior is retired: no press counting, no adaptive
verbosity, never silence (ADR-0009). An empty zone is not such a case: it is a
place, and its key lands there (ADR-0017).

**Order** (ADR-0017). A Surface's screen-specific help options come in this
order: Enter's phrase first, then the Surface's keys in the order its keymap
table below lists them. Where that order differs from the order the Surface
registers its keys, the Surface declares which keys follow Enter. Universal
keys and All commands come last.

**Ranges** (ADR-0017). Bindings that share one help phrase are one option:
"1 to 9: jump to that position in the list", "0 to 8: show only cards of that
mana cost". Enter on such an option says "Press one of these keys to use
this". Slot no-ops — universal slots a Surface leaves at their default or
answers with a constant phrase, such as Live Game's Enter and PageUp/PageDown
— are not options. A surface-layer key that only explains itself, such as
Live Game's Y, is an option.

**Keymap tables.** Every keymap table below lists the help options first, in
help order. Rows marked "Widget-type layer", "Universal layer", or "Slot
default" follow them as reminders; help does not list them among the
screen-specific options.

---

# Surfaces

Keymap tables below list surface-layer bindings, slot fills, and slot no-ops;
the widget-type and universal layers apply on every Surface exactly as the
cross-cutting contracts state them, whether or not a table restates them as a
reminder.

## Home

**Widget type:** Vertical menu (ADR-0006).

**Reached and left:** The stack root. Reached by app start and by back from any
top-level Surface. Back at Home is an announced no-op: "Home — already at the
top" (ADR-0004, ADR-0006).

**Window title:** `Home — StoneReader` (ADR-0006). Heading: "Home"
(ADR-0017).
**Entry utterance:** `"Home, {current option}"` (ADR-0007) — "Home, Live
Game, waiting for a game".

**Options,** in order, each carrying a Home-scoped jump-and-activate letter
(ADR-0006). Enter or the letter performs a **Screen jump** — the stack resets to
`[Home, target]`.

| Order | Option title | Letter |
|---|---|---|
| 1 | "Live Game, waiting for a game", or "Live Game, turn {t} versus {Class}" during a game (ADR-0017) | L |
| 2 | "Decks" | D |
| 3 | "Cards" | C |
| 4 | "Replays" | R |
| 5 | "Settings" | S |

The Live Game option says what Live Game holds right now; its title follows
the game silently, and the next movement or reread speaks the new title
(ADR-0017). The turn counts the mulligan as turn 1.

`B` and `O` are **reserved**, not bound: HSA binds B = Battlegrounds and
O = Open Packs (ADR-0006). Letters are Home-scoped; on other Surfaces bare
letters belong to that Surface's own keymap (ADR-0006).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Open the current option | "Enter: open the selected screen" |
| L | Jump to Live Game | "L: go to Live Game" |
| D | Jump to Decks | "D: go to Decks" |
| C | Jump to Cards | "C: go to Cards" |
| R | Jump to Replays | "R: go to Replays" |
| S | Jump to Settings | "S: go to Settings" |
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Home / End | First / last option | Universal layer (ADR-0004) |
| Escape / Backspace | Back | Announced no-op at the root (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

Note that `L` is filled here as the Live Game jump; the listen slot's default
announced no-op does not apply on Home because the surface-layer binding is the
slot fill (ADR-0010). Delete and Space are unbound here and therefore silent.

**Speech:** Vertical-menu utterances only; no position is spoken (ADR-0007).

**Audio:** None. Landing on Home stops any playing clip, as every transition
does (ADR-0008).

**Settings that affect it:** None. The clipboard deckstring offer can fire here,
but it is not a Home behavior — it is app-wide (see
[Navigation stack, window title, topology](#navigation-stack-window-title-topology)).

---

## Live Game

**Widget type:** Horizontal list with zones — game state moves sideways
(ADR-0004, ADR-0010, ADR-0017).

**Reached and left:** Screen jump from Home (`L`, or Enter on option 1), or the
system-wide hotkey Ctrl+Shift+L (landing on Remaining Deck during a game).
Back goes Home (ADR-0006). Remaining Deck is the first zone, so the first
visit lands there; later visits find the zone as left (ADR-0007).

**Window title:** `Live Game — StoneReader` (ADR-0006). Heading: "Live Game"
(ADR-0017).
**Entry utterance:**

- **No game in progress:** `"Live Game, waiting for a game"` (ADR-0017).
  Live Game says what it is waiting for instead of landing on an empty zone.
- **During a game:** the zone's context-entry utterance —
  `"{Zone label}, {title}, {position} of {count}"`, or `"{Zone label}: empty"`
  for an empty zone (ADR-0007, ADR-0017). Labels carry **no turn prefix**:
  live, the turn is ambient — the client announces it — and the Replay
  Viewer's turn prefix exists only because turn stepping changes what every
  zone means (ADR-0013).

When a game starts or ends, the zones fill or empty silently; the next key
reads the new state (ADR-0017).

**Zones.** Live Game speaks the Replay Viewer's full dialect — ADR-0004's "one
dialect, live or replayed", completed by ADR-0013: the same fourteen navigable
zones and five speak-only queries, identical letters and help phrases, reading
the current `GameState` and nothing else (*this spec's amendment* to ADR-0013's
fifteen-zone inventory — see Shift+C below). Zone labels are the user-facing
strings below, no "zone" suffix (ADR-0007), and are shared with the Replay
Viewer with one exception: `D` is **Remaining Deck** — live, the deck zone
means what's left (`Zone.DECK` minus draws, grouped by card), not a snapshot
list. `Shift+N` joining the surface forces one rename: the shipped "Cards
Drawn" zone becomes **Your drawn** (ADR-0013). Two zones are live
asymmetries: **Y is a constant announced no-op** — see the history ruling
below — and **Shift+C is the constant announced no-op "The game announces
the opponent's hand"**: opponent-hand information is the client's to speak
live, the same client-redundancy principle that retired the timeline. The
zone remains fully navigable in the Replay Viewer, where the client is not
in the room.

| Key | Zone label |
|---|---|
| B | Your board |
| G | Opponent board |
| C | Your hand |
| S | Your secrets |
| Shift+S | Opponent secrets |
| V | Your hero |
| F | Opponent hero |
| W | Your weapon |
| Shift+W | Opponent weapon |
| D | Remaining Deck |
| P | Your played |
| Shift+P | Opponent played |
| N | Your drawn |
| Shift+N | Opponent drawn |

**No live history** (ADR-0013). The **Live game timeline** is retired; Live
Game holds zero buffered state. Mid-game play history is the client's own
feature — HSA's in-game `y` already speaks it there — so StoneReader
mirroring it would double the client the way doubled audio would (ADR-0008's
principle: the real client is in the room). Reviewing a finished game is the
Replay Viewer's job; every completed live game already persists as a Replay.

**Title lines and detail lines.** Singleton zones (heroes, weapons) are
one-item list zones (ADR-0003). Every zone follows the Replay Viewer's
card-zone and hero-zone formats, with these live divergences (line 0 is the
title verbatim, ADR-0007):

*Remaining Deck* — cards in printed-mana order, then name. Title
`"{Card name}, {n} copy"` / `"…, {n} copies"` (ADR-0007's worked example).
Lines: 1 `"{p} percent to draw"` — nearest whole percent, copies remaining
over cards remaining (ADR-0013); 2 `"{cost} mana"`; 3 `"{Type}"`;
4 `"{Attack} attack, {Health} health"` for minions and weapons; 5 card text.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| B / G | Jump to your board / opponent board | "B: your minions" / "G: opponent minions" (ADR-0003) |
| C | Jump to your hand | "C: your hand" (ADR-0003) |
| Shift+C | Announced no-op — "The game announces the opponent's hand" | "Shift+C: the game announces the opponent's hand" — *this spec's amendment*: live opponent-hand information is the client's |
| D | Jump to Remaining Deck | "D: jump to Remaining Deck" (ADR-0009's worked example) |
| S / Shift+S | Jump to your secrets / opponent secrets | "S: your secrets" / "Shift+S: opponent secrets" |
| V / F | Jump to your hero / opponent hero | "V: your hero" / "F: opponent hero" |
| W / Shift+W | Jump to your weapon / opponent weapon | "W: your weapon" / "Shift+W: opponent weapon" |
| P / Shift+P | Jump to your played / opponent played | "P: cards you played" / "Shift+P: cards your opponent played" |
| N / Shift+N | Jump to your drawn / opponent drawn | "N: cards you drew" / "Shift+N: cards your opponent drew" |
| A | Speak your mana | "A: how much mana you have" — speak-only, never changes the zone (ADR-0003, ADR-0007) |
| Shift+A | Speak opponent mana | "Shift+A: how much mana your opponent has" — speak-only |
| Shift+D | Speak opponent deck count | "Shift+D: how many cards are in your opponent's deck" — speak-only |
| R | Speak your hero power | "R: your hero power" — speak-only |
| Shift+R | Speak opponent hero power | "Shift+R: your opponent's hero power" — speak-only |
| 1–9 | Jump to position 1–9 in the current zone | "1 to 9: jump to that position in the list" (ADR-0003, ADR-0004) |
| 0 | Jump to position 10 | "0: jump to the tenth item" (ADR-0004) |
| Y | Announced no-op — "No events in a live game" | "Y: no events in a live game" — ADR-0013: play history is the client's feature; HSA's in-game `y` speaks it there |
| F5 / F6 | Announced no-op — "No events in a live game" | "F5: no events in a live game" / "F6: no events in a live game" — ADR-0015: event stepping is replay-only |
| Left / Right | Previous / next item in the zone | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Shift+Up / Shift+Down | Repeat line / read to last line | Widget-type layer (ADR-0004, ADR-0007) |
| Home / End | First / last item in the zone | Universal layer (ADR-0004) |
| Enter | Announced no-op — "Nothing to do here" | Slot no-op, not a help option — see [Enter in v1](#enter-in-v1) (ADR-0017) |
| PageUp / PageDown | Announced no-op — "No turns to step in a live game" | Slot no-op, not a help option — ADR-0013: there is no **Live game timeline** |
| L | Announced no-op — "No game audio during a live game" | Slot no-op — *this spec's ruling*: ADR-0008's listen-key surface enumeration (Cards, deck contents, replay zones) deliberately excludes Live Game, where the real client is already producing its own audio |
| Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

**During a game,** an empty zone is a place: its letter switches to it and
speaks `"{Zone label}: empty"`, and arrows, Home/End, and digits there repeat
it (ADR-0017). Speak-only queries follow the `"{Subject}, {value}"` shape —
"Your mana, 4 of 10", "Opponent deck, 22 cards", "Your hero power, Fireblast"
(ADR-0007).

**With no game in progress** (ADR-0017), every zone letter, speak-only query,
Shift+C, Y, F5, F6, digit, Enter, PageUp/PageDown, arrow, Home/End, and
Shift+Down speaks "Waiting for a game", and the zone does not change.
Shift+Up rereads "Live Game, waiting for a game". L, Tab, and Ctrl+F keep
their usual responses ("No game audio during a live game", "No groups on this
screen", "No search on this screen").

Letters HSA binds in-game that have no StoneReader meaning here are not
registered and therefore stay silent (ADR-0004: unbound non-universal keys
stay silent). Delete and Space are unbound here and likewise silent.

**Speech:** Zone switches fire the same context-entry utterance as any other
landing (ADR-0007). Lane-2 narration of the game arrives from the Narrator, not
from this Surface (ADR-0010); a Lane-1 keypress here drops the pending Lane-2
queue (ADR-0007).

**Audio:** **Live Game plays no game audio.** The real client is in the room
producing its own; doubling it is clutter (ADR-0008).

**Settings that affect it:** Narration preset (which Game events Lane 2 speaks);
Hearthstone log path (ADR-0011).

---

## Decks

**Widget type:** Vertical menu — records move up and down (ADR-0017,
superseding this spec's earlier horizontal-list ruling). (The Surface is named
Decks; see [Naming](#announcement-grammar).)

**Reached and left:** Screen jump from Home (`D`, or Enter on option 2); no
system-wide hotkey — Decks is not a mid-game surface and Home reaches it in two
keys (ADR-0006). Back goes Home. Back from a Deck page or Import Deck reveals
Decks as left (ADR-0007).

**Window title:** `Decks — StoneReader` (ADR-0006, using the Home option's
name). Heading: "Decks" (ADR-0017).
**Entry utterance:** `"Decks, {current option}"` (ADR-0007) — "Decks, All
decks, 3 wins, 3 losses, 1 tie". Decks is never empty: All decks and Import
deck… are always present.

**Options,** in order (ADR-0017):

| Order | Option title | Shown | Enter |
|---|---|---|---|
| 1 | `"All decks, {record}"` | Always | Opens the All decks [Deck](#deck) page — the whole **Stats corpus** |
| 2 | `"{Deck name}[, {Class}][, Wild][, {n} cards], {record}"` | One per saved deck, newest first | Opens that deck's Deck page |
| 3 | `"Other games, {record}"` | Only when the corpus holds games no saved deck counts | Opens the Other games Deck page |
| 4 | `"Import deck…"` | Always | Drills into [Import Deck](#import-deck) (ADR-0006) |

A saved deck's title says the class only when the name does not already
contain it, "Wild" only for Wild decks, and the card count only when the deck
does not hold 30 — "Blood Control, Death Knight, Wild, 29 cards, 2 wins, 0
losses, 1 tie"; "Odd Hunter, 1 win, 1 loss"; "Empty Mage, no games yet"
(ADR-0017).

**Records** (ADR-0012, ADR-0017). A record reads `"{W} wins, {L} losses"`,
appending `", {T} ties"` only when nonzero, with counts agreeing with their
nouns ("1 win, 1 loss, 1 tie"); a record with no games reads `"no games yet"`.
Records are computed from the replay store on every view — no caching, no
persisted aggregates. They count the **Stats corpus**: live-recorded games are
members by default, imported **Replays** are not but can join, and Space on
Replays or Import Replays' toggle sets membership (ADR-0012, ADR-0014). A game
counts under a saved deck when it is a constructed game attributed to that
deck's `deck_id`; the deck name is snapshotted at save time, so editing a deck
keeps its history (ADR-0012). Every other corpus game is in **Other games**:
unattributed games, games whose saved deck was deleted, and arena and
Battlegrounds games, which play no saved deck. All decks always equals the
saved decks plus Other games (ADR-0017). An imported replay is counted from
its own recorded perspective — a replay recorded from the opponent's side
attributes the wrong side's result; the toggle is the remedy, not detection
(ADR-0012, documented not solved).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Open the current option | "Enter: open the selected deck" |
| C | Copy the focused deck's code to the clipboard | "C: copy this deck's code" |
| Delete | Arm delete, then delete on the second press | "Delete: delete this deck, press twice" (ADR-0004) |
| Shift+Delete | Delete without confirmation | "Shift+Delete: delete this deck without asking" (ADR-0004) |
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Home / End | First / last option | Universal layer (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

On All decks, Other games, and Import deck…, C says "Nothing to copy here"
and Delete and Shift+Delete say "Nothing to delete here" (ADR-0017).

*This spec's ruling on surface letters:* surface-layer letter bindings are
available on any Surface, subject to ADR-0003's standing obligation to check
the letter against HSA first — the Replay Viewer's own speak-only queries (A,
R, Shift+A, …) are ADR-0003's precedent for non-zone letters. `C` is assigned
here and on the [Deck](#deck) page because HSA's in-game `c` ("look at your
hand") has no meaning on a deck-management Surface, and HSA's Collection
Manager `C` ("jump to add cards screen") belongs to deck editing, which does
not exist in v1 (checked against
[the HSA command reference](research/hsa-commands-reference.md)). Left/Right
and Space are unbound here and therefore silent.

**Speech:** Delete arms with "Press Delete again to delete {Deck name}" and
confirms as `"{Deck name} deleted"` followed by a re-fired context-entry
utterance, because the option under the cursor changed (ADR-0007). Copy is
cursor-neutral, so it gets the confirmation alone: `"Deck code copied"`
(ADR-0007).

**Audio:** None on the Surface itself; L is an announced no-op here because the
options are records, not cards (ADR-0008, ADR-0010).

**Settings that affect it:** Replay retention prunes the store the records are
computed over (ADR-0011, ADR-0012).

### Deck

**Widget type:** Vertical menu — the deck page (ADR-0017).

**Reached and left:** Drill-down from Decks (Enter on All decks, a saved deck,
or Other games) or from [Replays](#replays) (D on a game played with a saved
deck). Back pops one level to whichever Surface opened it (ADR-0006). Every
open starts at the first option, unarmed; back from Deck detail or Games finds
the page as left (ADR-0017).

**Window title:** `{Subject} — StoneReader`, where the subject is the saved
deck's name, "All decks", or "Other games" — `Odd Hunter — StoneReader`.
Heading: "Decks › Odd Hunter", or "Replays › Odd Hunter" when opened with D
(ADR-0017).
**Entry utterance:** `"{Subject}, {current option}"` — "Odd Hunter, Cards,
30"; "All decks, Games, 1 win, 0 losses, 100 percent" (ADR-0007, ADR-0017).

**Options,** in order (ADR-0017):

| Option title | Shown | Enter |
|---|---|---|
| `"Cards, {n}"` | Saved decks only | Drills into [Deck detail](#deck-detail-deck-contents) |
| `"Games, {record}, {p} percent"`, or `"Games, none yet"` with no games | Always | Opens [Games](#games) for every game the record counts; with no games, announces "No games yet" and stays |
| `"Last 20 games, {record}"` | Only when the record holds more than 20 games | Opens Games for the newest 20 |
| `"Versus {Class}, {record}"` | One per opponent class with a game, most games first | Opens Games for the games against that class |
| `"Copy deck code"` | Saved decks only | Copies the deck code: "Deck code copied" |
| `"Delete deck"` | Saved decks only | Arms: "Press Enter again to delete {Deck name}"; the second Enter deletes |

**Every record row opens the games behind it** (ADR-0017): the Games list it
opens holds exactly the games its record counts. The win rate is wins over
wins plus losses, in whole percent with halves rounding up; ties and unknown
results count as games but stay out of the rate, and the percent is said only
when some game was decided — "Games, 2 wins, 1 loss, 1 tie, 67 percent";
"Games, 0 wins, 0 losses" when every result is unknown (ADR-0012, ADR-0017).
The last-20 window is fixed (ADR-0012). The All decks and Other games pages
have no Cards, Copy deck code, or Delete deck options.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Open or act on the current option | "Enter: open the selected option" |
| Delete | Arm delete of the page's deck, then delete on the second press | "Delete: delete this deck, press twice" (ADR-0004) |
| Shift+Delete | Delete the page's deck without confirmation | "Shift+Delete: delete this deck without asking" (ADR-0004) |
| C | Copy the page's deck code | "C: copy this deck's code" |
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Home / End | First / last option | Universal layer (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

Delete, Shift+Delete, and C act on the page's deck from any option. On the
All decks and Other games pages they say "Nothing to delete here" and
"Nothing to copy here" (ADR-0017). Left/Right and Space are unbound and
silent.

**Speech:** Delete arms with "Press Delete again to delete {Deck name}"; Enter
on Delete deck arms with "Press Enter again to delete {Deck name}"; each needs
the same key again, and any cursor movement disarms (ADR-0004). Deleting
confirms `"{Deck name} deleted"` and pops one level — to Decks, or to Replays
when the page was opened with D — followed by that Surface's context-entry
utterance as a continuation: "Odd Hunter deleted", then "Decks, Other games,
2 wins, 1 loss, 1 tie" (ADR-0007, ADR-0017). The deleted deck's games move to
Other games. Copy is cursor-neutral: "Deck code copied" alone (ADR-0007).

**Audio:** None.

**Settings that affect it:** Replay retention prunes the store the records are
computed over (ADR-0011, ADR-0012).

### Deck detail (deck contents)

**Widget type:** Horizontal list, single zone — cards move sideways
(ADR-0017).

**Reached and left:** Drill-down from a saved deck's [Deck](#deck) page (Enter
on "Cards, {n}"); back pops one level to that page (ADR-0006, ADR-0017).

**Window title:** `{Deck name} cards — StoneReader` (ADR-0006, ADR-0017).
Heading: "Decks › Odd Hunter › Cards".
**Entry utterance:** `"{Deck name} cards, {title}, {position} of {count}"`, or
`"{Deck name} cards: empty"` (ADR-0007, ADR-0017) — "Odd Hunter cards, Arcane
Shot x2, 1 of 15".

**Rows:** the deck's cards, sorted by printed mana cost ascending, then name
without case distinctions. Copy counts stay together on one row. Sorting is a
presentation choice and does not change the saved deck code. Live Remaining
Deck and replay deck browsing use the same ordering; hands, boards, and
played/drawn history keep their game order.

Title `"{Card name} x{n}"` when the deck holds more
than one copy, `"{Card name}"` otherwise — ADR-0007 names this exact case
("a Deck Contents duplicate needs its count"). Lines: 1 `"{cost} mana"`;
2 `"{Type}"`; 3 `"{Attack} attack, {Health} health"` where applicable; 4 card
text.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| L | Open the **Sounds menu** for this card | "L: listen to this card's sounds" (ADR-0008) |
| Left / Right | Previous / next card | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Home / End | First / last card | Universal layer (ADR-0004) |
| Enter | Announced no-op — "Nothing to do here" | Slot default — see [Enter in v1](#enter-in-v1) (ADR-0017) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

**Deck detail is read-only in v1.** *This spec's ruling:* there is no card
add, remove, or reorder, and Delete is unbound here (and therefore silent).
ADR-0012's "editing a saved deck keeps its history" is a robustness statement
about attribution surviving a future editing capability, not evidence that one
exists; decks enter the app by import and leave it by delete. Copying and
deleting a deck happen on its Deck page.

**Audio:** L only, per the universal listen key (ADR-0008).

### Games

**Widget type:** Vertical menu (ADR-0017).

**Reached and left:** Drill-down from a [Deck](#deck) page record row (Games,
Last 20 games, or Versus {Class}); back pops one level to that page, found as
left (ADR-0006, ADR-0017). Every open starts at the newest game, unarmed; back
from the Replay Viewer finds the list as left (ADR-0017).

**Window title:** `{Context label} — StoneReader` — `Odd Hunter games —
StoneReader`. Heading: "Decks › Odd Hunter › Games" (ADR-0017).
**Context label** — names the selection (ADR-0017):

| Record row | Saved deck page | All decks page | Other games page |
|---|---|---|---|
| Games | "{Deck name} games" | "All games" | "Other games" |
| Last 20 games | "{Deck name}, last 20 games" | "All games, last 20 games" | "Other games, last 20 games" |
| Versus {Class} | "{Deck name} versus {Class}" | "All games versus {Class}" | "Other games versus {Class}" |

**Entry utterance:** `"{Context label}, {current option}"` — "Odd Hunter
games, Won against Mage in 8 turns, today 3:36 PM". A list emptied by deletion
says `"{Context label}: empty"` — "Odd Hunter versus Warrior: empty"
(ADR-0007, ADR-0017).

**Options:** the games the record counts, newest first. Each title is the
[Replays](#replays) row title, without the deck name when the list is one
saved deck's — "Won against Warrior in 8 turns, Wednesday"; on All decks and
Other games lists the deck name stays — "Won against Mage in 8 turns, today
3:36 PM, Odd Hunter" (ADR-0017). A Versus {Class} list already names the
class, so its rows leave it out, and the outcome reads "Won", "Lost",
"Tied", or "Result unknown" — "Won in 8 turns, Wednesday" (ADR-0017). There
is no import option.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Open this replay in the Replay Viewer | "Enter: open this replay" |
| Delete | Arm delete, then delete on the second press | "Delete: delete this replay, press twice" (ADR-0004) |
| Shift+Delete | Delete without confirmation | "Shift+Delete: delete this replay without asking" (ADR-0004) |
| Up / Down | Previous / next game | Widget-type layer (ADR-0004) |
| Home / End | First / last game | Universal layer (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

Space and D are unbound here and therefore silent (ADR-0017): a stats toggle
would remove the row from under the cursor, and the Deck Surface is already
beneath this list on the stack, where ADR-0006 forbids a Surface appearing
twice. Left/Right are silent.

**Speech:** As on Replays: Delete arms with "Press Delete again to delete
this replay" and confirms "Replay deleted" followed by the re-fired
context-entry utterance (ADR-0007). The Deck page's records follow the
deletion. A replay that cannot load says "Could not open replay; the file may
be invalid" and stays.

**Audio:** None.

**Settings that affect it:** Replay retention (ADR-0011).

### Import Deck

**Widget type:** Vertical menu — a form is a vertical menu whose options are
fields and actions (ADR-0004).

**Reached and left:** Drill-down from Decks ("Import deck…"), or by accepting
the clipboard **Offer**, which resets the stack to `[Home, Decks, Import
Deck]` with the code pre-filled (ADR-0014). Either way back pops one level to
Decks; so does a completed import, where the new deck is (ADR-0006).

**Window title:** `Import Deck — StoneReader` (ADR-0006). Heading: "Decks ›
Import Deck" (ADR-0017).
**Entry utterance:** `"Import Deck, {current option}"` (ADR-0007). The Surface
never lands the User in Text mode on entry (ADR-0004).

**Options,** in order (ADR-0004's worked example gives exactly these two):

1. `"Deck code, edit text"` — Enter enters Text mode on the field. Committing
   or abandoning the field re-lands on Import Deck.
2. `"Import"` — Enter imports the code in the field.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | On the field, start typing; on Import, import the code | "Enter: edit this field, or run this action" |
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Escape | Leave Text mode without committing, or back | Universal layer; Escape is never dead (ADR-0004) |
| Home / End | First / last option | Universal layer (ADR-0004); in Text mode, the ends of the field (ADR-0011) |
| F1 | Help — in Text mode, the rescue phrase | "F1: help for this screen" (ADR-0009) |
| Left / Right | Unbound in navigation; caret movement with spoken characters in Text mode | ADR-0004, ADR-0011 |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

**Speech:** The form has no name field, so an imported deck is named for its
class — "{Class} deck", numbered "{Class} deck 2" when that name is taken.
Import confirms as `"{Deck name} imported"` (ADR-0007's worked example) —
"Death Knight deck imported" — and pops to Decks, whose context-entry
utterance follows as a continuation. *This spec's decision:* a code that is
not a deck code is refused with "Deck code not recognized", and the field
keeps its contents, patterned on the refused-commit shape ADR-0011 specced
for an invalid path.

**Audio:** None.

---

## Cards

**Widget type:** Vertical menu. Classes appear in alphabetical order, followed
by Neutral and All cards. Enter opens the selected collection in Card Browser.
Up and Down move between choices. Home and End reach the first and last choice.

**Reached and left:** Screen jump from Home with C or Enter on option 3, or
Ctrl+Shift+C. Back goes Home. The menu keeps its cursor when revealed again.

**Window title:** `Cards — StoneReader`.
**Entry utterance:** `"Cards, {current option}"`.

### Card browser

**Widget type:** Horizontal list, single zone — cards move sideways
(ADR-0017). Cards are ordered by printed mana cost ascending, then name
without case distinctions.

**Which cards** (ADR-0017). Card Browser lists the cards a deck can hold:
collectible heroes, locations, minions, spells, and weapons. Hero skins,
other cosmetics, and internal cards whose names are bracketed tags
("[CORE 2024] …") are excluded. Each card name appears once: a printing
from a named set beats one from an unnamed placeholder set, a current
printing beats its Classic-format copy, and otherwise the newest printing
wins.

**Reached and left:** Enter on a class, Neutral, or All cards in Cards. Back
returns to Cards at the previous menu position. Tab and Shift+Tab cycle the
same order as the class menu. Mana and search filters persist across classes.
Choosing a menu option or changing a filter resets the card and detail cursors.
Abandoning search or returning from help or Sounds menu keeps the current card.

**Window title:** the class choice, without the mana or search filter —
`Hunter cards — StoneReader`, `All cards — StoneReader`. Heading:
"Cards › Hunter cards". Tab and Shift+Tab retitle the window and heading in
place (ADR-0017).
**Entry utterance:** `"{Context label}, {title}, {position} of {count}"`, where
the context label carries the active filter and search state (ADR-0007). Empty
results degrade to `"{Context label}: empty"`, which dissolves a separate "No
results" phrasing (ADR-0007).

**Filters and search compose.** *This spec's ruling:* class filter, mana filter,
and search are independent constraints that AND together; clearing one leaves
the others standing. The context label enumerates the active constraints,
filters first and search last:

| Active constraints | Context label |
|---|---|
| None | "All cards" |
| Class | "Mage cards" |
| Class + mana | "Mage cards, 3 mana" |
| Class + mana + search | "Mage cards, 3 mana, matching fire" |
| Search only | "All cards matching fire" |

ADR-0007's principle — filter and search state ride in the context label — is
what is normative; its worked string "Search results for fire" is superseded by
this composition rule, which cannot express a search that discards the filters
around it.

**Rows:** cards. Title `"{Card name}"` — the name suffices here (ADR-0007's own
example). Lines: 1 `"{cost} mana"`; 2 `"{Type}"`; 3 `"{Attack} attack,
{Health} health"` for minions, `"{Attack} attack, {Durability} durability"`
for weapons; 4 card text, as the collection shows it; 5 `"{Class}"`;
6 `"{Rarity}"`; 7 `"{Set}"` — the game's own set name ("The Grand
Tournament", "Cataclysm"), in title case where the game styles it in capitals
("Titans"), and no line at all for a set the game does not name (ADR-0017).
One fact per line, spoken text equal to displayed text (ADR-0007).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Tab / Shift+Tab | Next / previous class filter | "Tab: jump to the next class" / "Shift+Tab: jump to the previous class" (ADR-0004, mirroring HSA's Collection Manager — [command reference](research/hsa-commands-reference.md)) |
| Ctrl+F | Search cards | "Ctrl+F: search for a card" (ADR-0004) |
| 0–8 | Filter by that exact mana cost; re-press clears | "0 to 8: show only cards of that mana cost" (ADR-0003, ADR-0004) |
| 9 | Filter to 9 mana or more; re-press clears | "9: show only cards costing 9 or more" (ADR-0004) |
| PageUp / PageDown | Move ten cards back / forward, clamped at the ends | "Page Up: jump ten cards back" / "Page Down: jump ten cards forward" (ADR-0004's paging slot) |
| L | Open the **Sounds menu** for this card | "L: listen to this card's sounds" (ADR-0008) |
| Left / Right | Previous / next card | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Home / End | First / last card in the whole filtered list | Universal layer (ADR-0004) — list-scoped, not page-scoped; see the ruling below the table |
| Enter | Announced no-op — "Nothing to do here" | Slot default — see [Enter in v1](#enter-in-v1) (ADR-0017) |

*This spec's rulings on the two collection-paging keys.* **Home/End are
list-scoped** — first and last of the whole filtered list — per ADR-0004's
universal layer, which ADR-0010 forbids a Surface from shadowing. HSA's
page-scoped Home/End is an artifact of its visual grid, which StoneReader does
not have; this is the same reasoning ADR-0004 already applied when it
reinterpreted HSA's PageUp/PageDown. **A page is ten cards** — the same span the
digit keys address (1–9 and 0) — so PageUp/PageDown move the cursor ten items
and clamp at the ends. Delete and Space are unbound here and therefore silent.

**Speech:** A filter or search change is an in-place rebuild and therefore fires
the full context-entry utterance with the new context label (ADR-0007). Numbers
never switch zones (ADR-0003, ADR-0004).

**Audio:** L only. The collection is where card flavor becomes browsable
(ADR-0008).

**Settings that affect it:** Game audio volume; Hearthstone install path (both
via the Sounds menu, ADR-0011).

---

## Replays

**Widget type:** Vertical menu — records move up and down (ADR-0017,
superseding this spec's earlier horizontal-list ruling).

**Reached and left:** Screen jump from Home (`R`, or Enter on option 4) or the
system-wide hotkey Ctrl+Shift+R. Back goes Home (ADR-0006). Back from the
Replay Viewer, Import Replays, or a Deck page opened with D reveals Replays as
left (ADR-0007).

**Window title:** `Replays — StoneReader` (ADR-0006). Heading: "Replays"
(ADR-0017).
**Entry utterance:** `"Replays, {current option}"` (ADR-0007) — "Replays, Won
against Mage in 8 turns, today 3:36 PM, Odd Hunter". Replays is never empty:
"Import replays…" is always present.

**Options:** stored games, **newest first**, then **"Import replays…"** last —
the flow ends where its results appear (ADR-0014, ADR-0017).

*Game options* — title (ADR-0017):

`"{Outcome} {Class} in {n} turns, {when}[, {deck}][, {game type}][, {format}][, imported][, not counted]"`

Each part after the first is said only when it applies, so the usual case is
short and the unusual is heard first (ADR-0007's distinguishability test,
ADR-0017):

| Part | Spoken |
|---|---|
| Outcome | "Won against", "Lost to", "Tied with", or "Result unknown against", then the opponent's class and the turn count — "Lost to Death Knight in 1 turn" |
| when | Local time: "today 3:36 PM", "yesterday 9:10 PM", the bare weekday for two to six days ago ("Wednesday"), otherwise "August 9", with the year when it is not this year ("December 31, 2025"). Omitted when the time cannot be read |
| deck | The deck name snapshotted when the game was saved, when the game is attributed to a deck (ADR-0012) |
| game type | Only when not Ranked, spoken by family: "Practice" (against the AI), "Friendly" (a friendly challenge), "Tavern Brawl", "Battlegrounds", "Battlegrounds Duos", "Arena", "Underground Arena", "Duels", "Heroic Duels", "Mercenaries"; any other type in title case ("Casual"). Unknown values are omitted, never spoken as "Unknown" |
| format | Only when not Standard: "Wild", "Classic", "Twist". Unknown values are omitted |
| imported | For a game imported rather than recorded live |
| not counted | For a game outside the **Stats corpus**. Membership rides in the title (ADR-0017, superseding ADR-0012's detail line) |

Examples: "Won against Mage in 8 turns, today 3:36 PM, Odd Hunter"; "Lost to
Death Knight in 1 turn, yesterday 9:10 PM, Casual, Wild, imported, not
counted"; "Result unknown against Warrior in 5 turns, August 9, Practice".
Games have no detail lines (ADR-0017).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Open this replay in the Replay Viewer; on "Import replays…", drill into Import Replays | "Enter: open this replay" (ADR-0006's drill-down, ADR-0014) |
| Space | Count this game in your stats, or stop counting it | "Space: count this game in your stats" (ADR-0012) |
| Delete | Arm delete, then delete on the second press | "Delete: delete this replay, press twice" (ADR-0004) |
| Shift+Delete | Delete without confirmation | "Shift+Delete: delete this replay without asking" (ADR-0004) |
| D | Open the [Deck](#deck) page of the saved deck this game was played with | "D: open this game's deck" (ADR-0017) |
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Home / End | First / last option | Universal layer (ADR-0004) |
| Ctrl+F | Announced no-op — "No search on this screen" | Slot default (ADR-0004); no ADR gives Replays a search |
| PageUp / PageDown, Tab / Shift+Tab, L | Announced no-op | Slot defaults (ADR-0010) |

**D follows the game to its deck** (ADR-0017): it drills into the Deck page
of the saved deck the game is attributed to, or announces "No saved deck for
this game" when the game is unattributed or its deck was deleted. On "Import
replays…", Space says "Nothing to count here", Delete and Shift+Delete say
"Nothing to delete here", and D says "Nothing to open here". Left/Right are
silent.

**Speech:** The Space toggle confirms verb-past and cursor-neutral —
`"Included in stats"` / `"Excluded from stats"`, with no re-entry utterance
(ADR-0012); the title's "not counted" changes with it and is heard on the next
arrival. Delete arms with "Press Delete again to delete this replay" and
confirms "Replay deleted" — a replay title is too long to be a confirmation's
object — followed by a re-fired context-entry utterance, because the option
under the cursor changed (ADR-0007). A replay that cannot load says "Could
not open replay; the file may be invalid" and stays.

**Audio:** None on this Surface (ADR-0008 places audio in the Replay Viewer's
events zone and on the listen key).

**Settings that affect it:** Replay retention (Unlimited or the last 100 / 500 /
1000 games, pruned oldest-first on write) (ADR-0011).

### Import Replays

**Widget type:** Vertical menu — a form is a vertical menu whose options are
fields and actions (ADR-0004, ADR-0014).

**Reached and left:** Drill-down from Replays ("Import replays…"); back pops
one level to Replays. So does a completed import, where the imported replays
are (ADR-0014).

**Window title:** `Import Replays — StoneReader` (ADR-0006's template).
Heading: "Replays › Import Replays" (ADR-0017).
**Entry utterance:** `"Import Replays, {current option}"` (ADR-0007). The
Surface never lands the User in Text mode on entry (ADR-0004).

**Options,** in order (ADR-0014):

1. `"Choose files, none chosen"`, becoming `"Choose files, {n} files chosen"`
   ("1 file chosen", ADR-0017's count agreement) — Enter opens the
   OS-native file dialog, multi-select, filtered to
   `.hsreplay`/`.xml`; the dialog's Cancel is the idiom's no-commit exit. The
   file field is ADR-0011's fifth value type: its editor is a delegated OS
   dialog (ADR-0014).
2. `"Count in stats, off"` — an ADR-0011 toggle, default off (ADR-0012's
   imported-out default), applied to this batch. ADR-0012's once-per-batch
   stats question is never asked: it dissolved into a visible, revisitable
   field with the right default (ADR-0014).
3. `"Import"` — the action. With nothing chosen it refuses with an
   announcement ("No files chosen") — ADR-0011's refused-commit shape.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | On Choose files, open the file dialog; on the toggle, flip it; on Import, import the chosen files | "Enter: edit this field, or run this action" |
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Escape / Backspace | Back | Universal layer (ADR-0004); the OS dialog's own Escape belongs to the OS dialog |
| Home / End | First / last option | Universal layer (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

**Speech:** Completion pops back to Replays: a verb-past confirmation followed
by the re-entry utterance (ADR-0007), speaking only nonzero parts —
`"{n} imported"`, appending `", {d} already in Replays"` (the store dedupes by
content hash) and `", {f} failed"` only when nonzero (ADR-0014, ADR-0012's
only-when-nonzero economy).

**Audio:** None.

---

## Replay Viewer

**Widget type:** Horizontal list with zones — game state moves sideways
(ADR-0003, ADR-0004, ADR-0010, ADR-0017).

**Reached and left:** Drill-down from Replays or [Games](#games) (Enter on a
game); back pops one level to whichever opened it (ADR-0006, ADR-0017).
**Every open starts at the beginning:** the Events zone at the game's first
event, with every other zone cursor reset. Back-reveal, from help or the
Sounds menu, still finds the Replay Viewer as left (ADR-0017).

**Window title:** `Replay Viewer — StoneReader` (ADR-0006). Heading: the path
that opened it — "Replays › Replay Viewer", or
"Decks › Odd Hunter › Games › Replay Viewer" (ADR-0017).

**Entry utterance:** the Replay Viewer's surface-wide context prefix is the
turn, `"Your turn {t}"` or `"Opponent's turn {t}"`, and the context label is
the zone label (ADR-0017). Landing, orientation reread, and in-place rebuilds
— a turn step or Enter's event jump — speak
`"{Prefix}, {Zone label}, {title}, {position} of {count}"`, or
`"{Prefix}, {Zone label}: empty"`. A zone switch omits the prefix, because the
turn did not change: `"{Zone label}, {title}, {position} of {count}"`.
Opening a replay says "Your turn 1, Events, Game started, Mage versus
Warrior, 1 of 11"; a landing mid-game says "Opponent's turn 3, Events,
Threads of Despair revealed, 2 of 20"; pressing B then says "Your board,
Bloodmage Thalnos, 1 of 3" (ADR-0017, superseding this spec's earlier
`"Turn {t}, {yours | opponent's}, {Zone label}"` label).

Zone cursors persist across switches, across turn steps, and across back-reveal
(ADR-0007, ADR-0010) — with one amendment: the **events cursor is the replay
position**, so a turn step repositions it to the new turn's first event
(ADR-0015). Every other cursor keeps the unamended rule. Opening a replay
resets them all (ADR-0017).

**Zones.** The letters mirror HSA exactly, inconsistencies included: distinct
letters for boards and heroes, a Shift modifier for hand/deck/weapon/secrets
(ADR-0003). Two HSA count-only commands are extended to navigable zones where
StoneReader has richer data — `D` (your deck) and `Shift+C` (opponent hand) —
with the letter convention preserved (ADR-0003). Zones with no HSA equivalent
take `P`/`Shift+P` (played) and `N`/`Shift+N` (drawn), both confirmed unbound in
HSA, and `Y` (events), which is **not** an unclaimed key — HSA binds it in-game
to the play-history log, and the binding stands on semantic fit alone; the "free
key" justification must never be cited for Y (ADR-0003, corrected against
[the HSA command reference](research/hsa-commands-reference.md)).

| Key | Zone label |
|---|---|
| B | Your board |
| G | Opponent board |
| C | Your hand |
| Shift+C | Opponent hand |
| S | Your secrets |
| Shift+S | Opponent secrets |
| V | Your hero |
| F | Opponent hero |
| W | Your weapon |
| Shift+W | Opponent weapon |
| D | Your deck |
| P | Your played |
| Shift+P | Opponent played |
| N | Your drawn |
| Shift+N | Opponent drawn |
| Y | Events |

Singleton zones (heroes, weapons) are one-item list zones browsable by
detail-line navigation, not special-cased "look at" commands (ADR-0003).

**The labels speak the recorded perspective.** *This spec's ruling:* "Your"
always means the replay's **Friendly Player** — whoever the replay was recorded
from, which may not be the User when the User is watching someone else's replay
(CONTEXT.md). The labels do not vary by replay. This is the same
documented-not-solved stance ADR-0012 takes on imported perspective, where a
replay recorded from the opponent's side attributes the wrong side's result and
the stats toggle is the remedy rather than detection.

**Title lines and detail lines** (ADR-0007 delegates both to this spec):

*Card zones* (boards, hands, secrets, weapons, deck, played, drawn) — title
`"{Card name}"`, extended to `"{Card name}, turn {t}"` in the played and drawn
zones where turn is what distinguishes neighbors. Lines: 1 `"{cost} mana"`;
2 `"{Attack} attack, {Health} health"` for minions; 3 status facts one per line
(taunt, divine shield, frozen, damaged); 4 card text; 5 `"Created by {source}"`
when a creation lineage exists.

*Your deck* — cards in printed-mana order, then name, unknown cards last.

*Hero zones* — title `"{Hero name}, {Health} health"`, plus `", {Armor} armor"`
when nonzero. Lines: hero power, weapon, and `"{n} secrets"` ("1 secret").

*Events zone* — title is the Narrator's phrase for that **Game event**
(ADR-0010 owns the phrasing seam): "You played Boar", "Opponent drew a card",
"Game over, won". A turn change reads "Start of turn": the context prefix
already names the side and number — "Opponent's turn 2, Events, Start of
turn, 1 of 1" (ADR-0017). A reveal that only restates a draw or play at the
same moment is not a separate event, and an enchantment wearing off is not
an event. A spell cast from hand is played like a minion ("Opponent played
Fireball"); a weapon that breaks reads "{Weapon} destroyed". A card created
straight into a hand (The Coin) is drawn, in the events and the drawn zones
alike. Lines: 1 `"Turn {t}"`; 2 the source card's title where the event has
one.

**Event scrubbing** (ADR-0015). The events zone is the Surface's **fine
axis**: the selected event renders every other zone at the game just after
that event. Scrub from inside the zone with Left/Right, 1–9/0, or Home/End,
or from **any** zone with `F5`/`F6` (previous / next event) — stay on the
board and watch it change event by event. A turn step lands the events
cursor on the turn's **first** event, so a turn reads forward; the turn's
last event carries the turn's final state, so stepping to it (or End in the
events zone) reads the turn as it ended. At the turn's edges F5/F6 clamp
and repeat the current title — turn boundaries are PageUp/PageDown's job. In
a turn with no events, F5/F6 say "Events: empty".

**Enter follows the fact** (ADR-0017). In the Your played, Opponent played,
Your drawn, and Opponent drawn zones, Enter moves the replay position to the
event where the focused card was played or drawn — that event's turn, and
that event in the events cursor — and lands in the Events zone on it, prefix
first: "Your turn 1, Events, You played Boar, 4 of 11". The landing plays the
event's sound like any event landing. A card played or drawn more than once
(returned to hand and replayed) goes to the event on the turn its row names;
twice in one turn, each row goes to its own event, the second row to the
second play or draw. With no matching event, Enter says "No event for this
card" and stays. In every other zone, and in an empty played or drawn zone,
Enter is the announced no-op "Nothing to do here".

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Go to the event where this card was played or drawn | "Enter: go to the event where this card was played or drawn" (ADR-0017) |
| PageUp / PageDown | Previous / next turn | "Page Up: go to the previous turn" / "Page Down: go to the next turn" — turn stepping is this Surface's coarse axis (ADR-0004) |
| F5 / F6 | Previous / next event, from any zone | "F5: go to the previous event" / "F6: go to the next event" — the fine axis without leaving the zone; speaks the event's title and fires its auto-play; clamps at the turn's edges (ADR-0015) |
| B / G | Jump to your board / opponent board | "B: your minions" / "G: opponent minions" (ADR-0003) |
| C / Shift+C | Jump to your hand / opponent hand | "C: your hand" / "Shift+C: opponent hand" (ADR-0003) |
| S / Shift+S | Jump to your secrets / opponent secrets | "S: your secrets" / "Shift+S: opponent secrets" |
| V / F | Jump to your hero / opponent hero | "V: your hero" / "F: opponent hero" |
| W / Shift+W | Jump to your weapon / opponent weapon | "W: your weapon" / "Shift+W: opponent weapon" |
| D | Jump to your deck | "D: jump to Remaining Deck" (ADR-0009) |
| P / Shift+P | Jump to your played / opponent played | "P: cards you played" / "Shift+P: cards your opponent played" |
| N / Shift+N | Jump to your drawn / opponent drawn | "N: cards you drew" / "Shift+N: cards your opponent drew" |
| Y | Jump to Events | "Y: the game's events" — the fine axis: the selected event sets the moment every zone reads (ADR-0015) |
| A | Speak your mana | "A: how much mana you have" — speak-only, never changes the zone (ADR-0003, ADR-0007) |
| Shift+A | Speak opponent mana | "Shift+A: how much mana your opponent has" — speak-only |
| Shift+D | Speak opponent deck count | "Shift+D: how many cards are in your opponent's deck" — speak-only |
| R | Speak your hero power | "R: your hero power" — speak-only |
| Shift+R | Speak opponent hero power | "Shift+R: your opponent's hero power" — speak-only |
| 1–9 | Jump to position 1–9 in the current zone | "1 to 9: jump to that position in the list" (ADR-0003, ADR-0004) |
| 0 | Jump to position 10 | "0: jump to the tenth item" (ADR-0004) |
| L | Open the **Sounds menu** for the focused card, or for an event's source card | "L: listen to this card's sounds" (ADR-0008) |
| Left / Right | Previous / next item in the zone | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Shift+Up / Shift+Down | Repeat line / read to last line | Widget-type layer (ADR-0004, ADR-0007) |
| Home / End | First / last item in the zone | Universal layer (ADR-0004) |
| Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

An empty zone is a place: its letter switches to it and speaks
`"{Zone label}: empty"`, and arrows, Home/End, Shift+Down, and digits there
repeat that, without the prefix (ADR-0017). Shift+Up there rereads with the
prefix: "Your turn 1, Your weapon: empty". Speak-only queries follow the
`"{Subject}, {value}"` shape — "Your mana, 4 of 10", "Opponent hero power,
Armor Up!" (ADR-0007). Delete and Space are unbound here and therefore
silent.

**Speech:** Turn stepping is speech-only (ADR-0008) and speaks the prefixed
context-entry utterance above — turn, zone, title, position. A turn step at
the first or last turn is a boundary: it repeats the current bare title, or
`"{Zone label}: empty"` (ADR-0007). There is no separate turn announcement
and no event count in it; the events zone is where events are counted,
browsed, and scrubbed. Scrubbing adds no utterance of its own: an event
landing — Left/Right in the zone or F5/F6 from anywhere — speaks the event's
title as always, and the zones simply read as of that event when visited — no
"after {event}" prefix anywhere (ADR-0015, ADR-0007's route invariance).

**Audio:** The **events zone auto-plays**: landing on an event plays that
event's sound — its card's Play/Attack/Death line, upgraded to card-specific
Foley by CardID where one exists and falling back to the generic base clip for
the common voiceless case — replacing any playing clip and mixing under the
event's narration (ADR-0008; research fact sheet findings 11–12). Opening a
replay and turn stepping are silent. Hero-power, discover, and emote-wheel
events stay silent, because names alone cannot identify their clips (research
fact sheet finding 13). **The signature sound** (ADR-0017): reaching the
game-over event plays the victory jingle for a win and the defeat jingle for
a loss or concession; a tie plays nothing. It is the one place StoneReader
marks a moment with sound beyond the event clips themselves. The auto-play,
jingle included, is always on with a Settings kill-switch (ADR-0008,
ADR-0017).

**Settings that affect it:** Replay auto-play (the kill-switch); Game audio
volume; Hearthstone install path (ADR-0011). Until game audio is ready, the
events zone is silent and the listen key says why: "Game audio is still
preparing" while its index builds, "Game audio is unavailable — no
Hearthstone install found" with no install, and "Game audio is unavailable —
couldn't read Hearthstone's audio files" when the install's audio cannot be
read (ADR-0008).

---

## Settings

**Widget type:** Vertical menu — one flat menu; nothing sits more than two
levels deep, and only individual chord rows sit at two (ADR-0011).

**Reached and left:** Screen jump from Home (`S`, or Enter on option 5); no
system-wide hotkey (ADR-0006). Back goes Home.

**Window title:** `Settings — StoneReader` (ADR-0006). Heading: "Settings"
(ADR-0017).
**Entry utterance:** `"Settings, {current option}"` (ADR-0007).

**Rows** — nine (seven value rows plus the Global-hotkeys drill-down and two
actions), in order. Value-row titles are `"{Label}, {current value}"`, so a
single Down-arrow sweep reads the whole configuration (ADR-0011); action rows
have no value and speak their label alone, like Restore all defaults always
has.

| Row | Type | Default | Row title example |
|---|---|---|---|
| Narration | Choice — Off / Key moments / Everything | Key moments | "Narration, key moments" |
| Game audio volume | Volume — 0–100 in steps of 10 | 80 | "Game audio volume, 80" |
| Replay auto-play | Toggle | On | "Replay auto-play, on" |
| Hearthstone install path | Path | Auto-detected | "Hearthstone install path, auto-detected" |
| Hearthstone log path | Path | Auto-detected | "Hearthstone log path, auto-detected" |
| Replay retention | Choice — Unlimited / last 100 / last 500 / last 1000 | Unlimited | "Replay retention, unlimited" |
| Global hotkeys | Drill-down — six chord rows | The ADR-0006 table | "Global hotkeys" |
| Check for updates | Action | — | "Check for updates" |
| Restore all defaults | Action, press-twice | — | "Restore all defaults" |

**Check for updates** (ADR-0016, *this spec's addition*): Enter announces
"Checking for updates", then the result — up to date, unavailable, or failed —
as its own announcement. A newer release arms the update **Offer** (ADR-0014):
"StoneReader {version} is available — press Control Enter to update". The same
Offer arms unsolicited, once per version, when a frozen build finds an update
at startup; a solicited re-check re-offers. Delete on this row is the announced
no-op "Nothing to reset here" — an action row has no default to restore.

Paths are the one unspeakable value: their titles say "auto-detected" or
"custom", with the full path on the detail line and in Text mode (ADR-0011).

**Editing idioms, by value type** (ADR-0011). Every idiom has a no-commit escape
hatch; nothing on this Surface has hidden staged state.

| Type | Enter does |
|---|---|
| Toggle | Flips it and announces the row's new title |
| Choice, Volume | Drills into a **Picker** — a vertical menu of the values with the cursor on the current one; Enter selects and pops back, re-announcing the parent row; back exits without change |
| Path | Enters **Text mode** on the field; Enter commits with validation announced (an invalid path refuses commit and keeps the previous value); Escape abandons |
| Chord | Enters **Capture mode** |
| File | Opens the delegated OS-native file dialog; the dialog's Cancel is the no-commit exit (ADR-0014's fifth value type) — no Settings row uses it in v1; its one user is [Import Replays](#import-replays)' Choose files |

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Change this setting | "Enter: change this setting" |
| Delete | Arm reset, then reset on the second press — "Press Delete again to reset {label} to {default}" | "Delete: reset this setting, press twice" (ADR-0011 on ADR-0004's idiom) |
| Shift+Delete | Reset this setting to its default without arming; on Restore all defaults, restore everything without arming | "Shift+Delete: reset this setting without asking" — *this spec's ruling*, ADR-0004's Shift-skips-confirmation composed with ADR-0011's Delete-as-reset |
| Up / Down | Previous / next setting | Widget-type layer (ADR-0004) |
| Home / End | First / last setting | Universal layer (ADR-0004) |
| Ctrl+F | Announced no-op — "No search on this screen" | Nine rows need no search; the announced no-op is the spec (ADR-0011) |
| Left / Right | Unbound and silent | Deliberately dead in vertical menus (ADR-0004, ADR-0011) |
| PageUp / PageDown, Tab / Shift+Tab, L | Announced no-op | Slot defaults (ADR-0010) |

Space is unbound here and therefore silent.

**Narration presets** — the Lane-2 content (ADR-0011). Membership test for Key
moments: *things you'd miss by not watching that change your next decision*. The
User's own plays are narrated by no preset, and neither are turn flips or card
draws on either side — the client announces those itself, and StoneReader does
not double the client (ADR-0013's principle; *this spec's amendment* to
ADR-0011's original table).

| Game event | Key moments | Everything |
|---|---|---|
| Opponent plays a card | yes | yes |
| Minion dies | yes | yes |
| Secret played / revealed | yes | yes |
| Game over (result) | yes | yes |
| Attacks (attacker → target) | — | yes |
| Hero power used | — | yes |
| Triggers / deathrattles | — | yes |

Per-surface PRDs may amend membership without reopening ADR-0011 — the Narrator
seam makes it one table (ADR-0011, ADR-0010).

**Apply, persist, reset.** Every change applies immediately (the preset re-tunes
the Narrator live; volume affects the next clip) and autosaves. No OK/Cancel and
no unsaved-changes state. Storage is `~/.stonereader/settings.json` — flat JSON,
missing key means default, unknown keys ignored, no schema versioning until a
real migration exists. First run means no settings file means all defaults;
there is no setup wizard (ADR-0011).

**Unavailable rows explain, never hide.** When game audio is unavailable, the
volume row stays visible and says why — "Game audio volume, unavailable — no
Hearthstone install found" with no install, or "Game audio volume,
unavailable — couldn't read Hearthstone's audio files" when the install's
audio cannot be read — and Enter there repeats the row instead of opening
the Picker (ADR-0011). While game audio is still preparing, the row shows
its value and stays editable.

**Deliberate exclusions from this Surface** (ADR-0011): no speech
rate/voice/synth settings (speech exits via the User's screen reader and was
never ours to mix); no HSA-letter rebinding (the letter keymap is the app's
identity); no visual or theme settings — the window's heading, list, and
detail pane draw with the system's own colours and fonts (ADR-0011,
ADR-0017).

### Global hotkeys (drill-down)

**Widget type:** Vertical menu (ADR-0011).

**Reached and left:** Drill-down from the Settings "Global hotkeys" row; back
pops one level to Settings (ADR-0011, ADR-0006).

**Window title:** `Global hotkeys — StoneReader` (ADR-0006). Heading:
"Settings › Global hotkeys" (ADR-0017).
**Entry utterance:** `"Global hotkeys, {current option}"` (ADR-0007).

**Rows:** four chord rows, titled `"{Label}, {chord}"` with the chord spoken as
a word sequence — "Jump to Live Game, Ctrl Shift L" (ADR-0011). The four are
the system-wide hotkey table above: Jump to Live Game, Jump to Cards, Jump to
Replays, Speak deck counts. Help reads these chords from the registry at speak
time, never from a static table, because they are mutable (ADR-0011, ADR-0009).

**Capture mode.** Enter on a chord row announces "Press the new shortcut for
{name}. Escape cancels." and enters **Capture mode**: the next chord pressed
becomes the candidate (ADR-0011).

Acceptance policy (ADR-0011):

| Candidate | Outcome |
|---|---|
| Bare key (no modifier) | Refused outright — a system-wide bare letter or F-key is indefensible |
| Single-modifier chord | Warning plus press-again confirm: "Shift C is a single-modifier shortcut; other apps, including Hearthstone Access, may use it. Press it again to bind anyway" |
| Two or more modifiers | Binds directly |
| Already bound inside StoneReader | Refused with its owner named: "Ctrl Shift C is taken by Jump to Cards" |
| OS registration fails | Failure announced; the previous binding is kept |

The reserved **Offer** chord refuses the same way: "Control Enter is taken by
Accept offer" (ADR-0014).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Record a new shortcut for this command | "Enter: record a new shortcut" (ADR-0011) |
| Delete | Arm reset to the default chord, then reset | "Delete: reset this shortcut, press twice" (ADR-0011) |
| Shift+Delete | Reset this shortcut to its default without arming | "Shift+Delete: reset this shortcut without asking" (ADR-0004, ADR-0011) |
| Up / Down | Previous / next hotkey | Widget-type layer (ADR-0004) |
| Escape | Cancel capture, or back | Universal layer (ADR-0004, ADR-0011) |
| Home / End | First / last hotkey | Universal layer (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

---

## Help menu

**Widget type:** Vertical menu, on the ordinary navigation stack (ADR-0004,
ADR-0009).

**Reached and left:** F1 from any Surface — a **Drill-down** that pushes one
level. Backspace/Escape returns. **F1 always opens help fresh**, on the
widget-type sentence with no search (ADR-0017); back from Universal keys or
All commands finds help as left. F1 inside any help Surface — the Help menu,
Universal keys, All commands, or a command reference — is an announced no-op
("Already in help"): help never stacks on help (ADR-0009).

**Window title:** `{Surface} help — StoneReader`, using the display name of
the Surface help was opened from — `Cards help — StoneReader`,
`Odd Hunter help — StoneReader` on the Odd Hunter Deck page,
`Hunter cards help — StoneReader` from Card Browser (ADR-0017). *This spec's
ruling, compositionally:* the Help menu's surface name is "{Surface} help"
(ADR-0009) and ADR-0006's template wraps every surface name. Heading: the
origin's path plus the help name, trimmed like every crumb —
"Decks › Odd Hunter › Help" (ADR-0017).
**Entry utterance:** `"{Surface} help, {current option}"` — the vertical-menu
form, with the widget-type sentence as the current option on entry (ADR-0007,
ADR-0009, ADR-0017).

**Options,** in order (ADR-0009, ADR-0017):

1. **The widget-type sentence**, generated from the Surface's declared type
   and naming only the type, since help's own name already names the
   Surface — "Horizontal list: Left and Right move between items, Up and
   Down read details." or "Menu: Up and Down move between options, Enter
   acts on the current one." (ADR-0017).
2. **Screen-specific options**, **key-first**: `"{Key}: {action phrase}"` —
   "D: jump to Remaining Deck". Enter's phrase comes first, then the Surface's
   keys in the order its keymap table above lists them; bindings that share
   one phrase are one option, and slot no-ops are not listed (see
   [Help generation](#help-generation)). Title-line rules apply.
3. **"Universal keys"** — a drill-down listing the app-wide layer: "Enter: act
   on the current item", "Escape or Backspace: go back", "Home and End: jump
   to the ends", "Page Up and Page Down: pages or turns where the screen has
   them", "Tab and Shift+Tab: jump between groups where the screen has them",
   "Ctrl+F: search where the screen has it", "F1: help for this screen", "L:
   listen to a card's sounds", "Ctrl: stop game audio", "Ctrl+Q or Alt+F4:
   quit StoneReader". The list is read-only. The structure carries the
   universal/screen-specific distinction; options are never individually
   labeled with it. Delete, Shift+Delete, and Space are surface-layer bindings
   and therefore appear in option group 2 on the Surfaces that bind them, not
   here.
4. **"All commands"** — a drill-down of per-surface sections in Home order,
   each Surface followed by its drill-downs: Home, Live Game, Decks, Deck,
   Deck detail, Games, Import Deck, Cards, Card Browser, Sounds menu, Replays,
   Replay Viewer, Import Replays, Settings, Global hotkeys. Each section, "{Surface}
   commands", lists that Surface's widget-type sentence and screen-specific
   options: the in-app command reference, generated from the same registry.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Do this command | "Enter: act on the current option" — pops help and performs that binding on the underlying Surface: help doubles as a command palette (ADR-0009) |
| Ctrl+F | Search help | "Ctrl+F: search help" (ADR-0009) |
| Up / Down | Previous / next help option | Widget-type layer (ADR-0004) |
| F1 | Announced no-op — "Already in help" | ADR-0009 |
| Escape / Backspace | Back | Universal layer (ADR-0004) |
| Home / End | First / last help option | Universal layer (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, L | Announced no-op | Slot defaults (ADR-0010) |

Options that cannot sensibly execute are announced no-ops (ADR-0009,
ADR-0004): the widget-type sentence, Enter's own option, Ctrl+F's option, and
Universal keys entries say "Nothing to do here"; an option shared by several
keys says "Press one of these keys to use this" (ADR-0017); All-commands
entries say "Only available on {Surface}". Destructive safety is unchanged: a
delete executed from help still only arms and asks for its second press
(ADR-0009). Ctrl+F filters the options by a case-insensitive match on their
text and re-lands on the first match.

**Speech:** Nothing bespoke — the vertical-menu grammar throughout (ADR-0007).

**Audio:** None; entering help is a surface transition and therefore stops any
playing clip (ADR-0008).

---

## Sounds menu

**Widget type:** Vertical menu — an ordinary vertical-menu Surface built from
the clip index (ADR-0008, ADR-0010).

**Reached and left:** The listen key **L** on any card under the cursor (Cards,
deck contents, Replay Viewer card zones) — a **Drill-down** that pushes one
level. Escape/Backspace backs out (ADR-0008).

**Window title:** `{Card name} sounds — StoneReader` (ADR-0006's template).
**Entry utterance:** `"{Card name} sounds, {current option}"` — the standard
vertical-menu utterance (ADR-0007, ADR-0008).

**Options:** that card's **Game audio** clips labeled by event — "Play",
"Attack", "Death", "Trigger 2", … — from the runtime index, whose clip names
carry the card-id→event mapping (ADR-0008; research fact sheet finding 7).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Enter | Play this sound | "Enter: play this sound" (ADR-0008) |
| Up / Down | Previous / next sound | Widget-type layer (ADR-0004) |
| Escape / Backspace | Back | Universal layer (ADR-0004) |
| Home / End | First / last sound | Universal layer (ADR-0004) |
| L | Announced no-op | Already in the Sounds menu; slot default (ADR-0010) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

There is no play-on-focus: menus act on Enter everywhere else, and rapid
arrowing would stutter through replaced clips (ADR-0008).

**Degenerate cases** (ADR-0008, and ADR-0004's no-silent-universal-key rule):

- Card with no clips: L announces `"{title}: no sounds"` and does **not** push
  the Surface.
- Game audio not ready: L says why and does not push — "Game audio is still
  preparing" while its index builds, "Game audio is unavailable — no
  Hearthstone install found" with no install, or "Game audio is unavailable —
  couldn't read Hearthstone's audio files" when the install's audio cannot be
  read.

**Audio:** Enter starts a clip, replacing any clip already playing. Backing out
of the Sounds menu is a surface transition and therefore stops it; ordinary
arrowing inside the menu does not (ADR-0008).

**Settings that affect it:** Game audio volume; Hearthstone install path
(ADR-0011).

---

# Deliberate exclusions

| Excluded | Reservation state |
|---|---|
| Battlegrounds toolset | Known fog on map #17; Home letter **B is reserved**, not bound, because HSA binds B = Battlegrounds (ADR-0006). HSA's Battlegrounds vocabulary is dense and distinct from its in-game vocabulary, so a future surface must re-derive its keys rather than reuse the Replay Viewer's (ADR-0003). HSA's 8 Battlegrounds wavs remain the earcon precedent if this ever graduates (ADR-0008). |
| Collection / pack tracking | Known fog on map #17; Home letter **O is reserved**, not bound, because HSA binds O = Open Packs (ADR-0006). |
| Mulligan helper | Not on this map. Named in ADR-0012 as one of the efforts that might need a filtered-list capability first; no key, letter, or topology slot is reserved for it. |
| Secrets helper (which secrets are still possible) | Known fog on map #17 (ADR-0013): the strongest remaining tracker-overlay idea, but it needs per-format secret-pool data — a research effort, not a spec ruling. No key is reserved; S/Shift+S are the secrets zones themselves. |
| Arena assist / drafting | Not on this map. ADR-0003 notes only the standing obligation that a future arena-drafting surface check HSA's vocabulary before picking keys. Arena games count in no saved deck's record, because they play no saved deck; they count in Other games and All decks (ADR-0012, ADR-0017). |
| Onboarding / installer | Explicitly out of scope on this map: first run means no settings file means all defaults, and there is no setup wizard — Settings is for divergence (ADR-0011). ADR-0008's required "not affiliated with Blizzard Entertainment / assets © Blizzard" notices land with this effort; no v1 Surface carries them. |

---

# Open questions

None. The last one — the prompt construct, how StoneReader asks the User a
question ([#35](https://github.com/akj/stonereader/issues/35)) — was resolved
by ADR-0014 and is folded in above: the closed
[asking-idiom inventory](#asking), the restated
[clipboard offer](#navigation-stack-window-title-topology), and
[Import Replays](#import-replays).
