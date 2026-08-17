# StoneReader UI specification

## Purpose

This is the per-surface specification implementation PRDs open against. It folds
every decision locked in ADR-0003 through ADR-0014 into one document: the
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
[#35](https://github.com/akj/stonereader/issues/35)). No open questions
remain: every section is normative and PRD-ready. Nothing here ships code by
itself.

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
| [0012](adr/0012-deck-replay-statistics-surface.md) | **Stats corpus** membership, deck attribution, win-rate formula, the Statistics surface |
| [0013](adr/0013-live-game-current-state-full-dialect.md) | Live Game: full replay dialect current-state only, no **Live game timeline**, draw-chance line, bare labels |
| [0014](adr/0014-how-stonereader-asks.md) | Asking: the closed idiom inventory, the **Offer** and Ctrl+Enter, OS-dialog delegation, replay import |

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
their persistence across switches, zone-switch context-entry utterances, and the
constant "No {zone} on this screen" announced no-op for a bound-but-inapplicable
zone key (ADR-0010, ADR-0009). Vertical menus have no zone concept (ADR-0010).

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
*This spec's ruling:* on **Cards**, **Deck detail**, **Live Game**, and the
**Replay Viewer**'s zones, Enter is an announced no-op in v1 — the same call
ADR-0012 made explicitly for Statistics. Nothing on those Surfaces is acted on;
they are places to read.

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
change, and — by this spec's extension — a Replay Viewer turn step), and
orientation reread. No route-specific phrasing exists anywhere (ADR-0007).

| Context | Utterance |
|---|---|
| Horizontal list or zone | `"{Context label}, {title}, {position} of {count}"` |
| Vertical menu | `"{Context label}, {current option}"` — no position |
| Empty context | `"{Context label}: empty"` — always the user-facing label, never an internal id |

**Title lines.** Every item has exactly one Title line — the shortest string
that distinguishes it from its neighbors in that list. One formatter produces
it, used verbatim in three places: the displayed row, the movement utterance,
and detail line 0. It is written for the ear ("3 attack, 2 health", never "3/2")
and the display shows exactly that string (ADR-0007). Title content per Surface
is this spec's decision under ADR-0007's distinguishability test; ADR-0007
delegates the order of detail lines 1+ to this spec as well.

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
persistence is structural (ADR-0010). **This spec takes none of ADR-0007's
permitted transient opt-outs**: nothing is reset on leaving a Surface, and in
particular Cards' class filter, mana filter, and committed search survive
leaving and re-entering. Fresh state is what app restart is for (ADR-0007).

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

**Naming.** *This spec's ruling:* ADR-0006's names are canonical — the Surfaces
are **Cards** and **Decks**. "Card Browser" (ADR-0009's widget-type sentence)
and "Deck Manager" (ADR-0007's confirmation example) are stale shipped-name
example strings inside worked examples, not naming decisions; ADR-0006 names
these Surfaces where it decides the topology, and the window title and context
label are one user-facing string per Surface. Generated help therefore reads
"Cards is a horizontal list: Left and Right move between cards, Up and Down read
details."

## Navigation stack, window title, topology

- A **Screen jump** — a Home letter, Enter on a Home menu option, or a
  system-wide hotkey — resets the stack to `[Home, target]`. Back from any
  jumped-to Surface goes Home; duplicate stack entries are structurally
  impossible (ADR-0006).
- A **Drill-down** pushes one level; back pops exactly one (ADR-0006).
- Back is an announced no-op at Home (ADR-0004, ADR-0006).
- On every landing, by any route, the navigation controller fires the
  window-title update, the context-entry utterance via the Announcer, and the
  game-audio stop (ADR-0010).
- Window title is `"{Surface name} — StoneReader"`, updated on every stack
  change. There is no status bar and no `wx.MenuBar` (ADR-0006).
- The User always chose to be here: no Surface change happens without a keypress
  (ADR-0006).

**System-wide hotkeys** (native OS registration, ADR-0005; rebindable in
Settings, ADR-0011). These dispatch through the same command registry as any
other input route, so none can die silently (ADR-0010).

| Hotkey | Command | Effect |
|---|---|---|
| Ctrl+Shift+L | Jump to Live Game | Screen jump to Live Game, landing on Remaining Deck (ADR-0006) |
| Ctrl+Shift+C | Jump to Cards | Screen jump to Cards (ADR-0006) |
| Ctrl+Shift+R | Jump to Replays | Screen jump to Replays (ADR-0006) |
| Ctrl+Shift+D | Speak deck counts | Speak-only: "Your deck, {n} cards" — navigates nowhere (ADR-0006, ADR-0007) |

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
guard** — C on Decks never leads to an offer to import the code the app just
handed you (ADR-0014). The shipped `wx.MessageDialog` clipboard modal is
retired, along with the `restore_focus` hack's motivating case (ADR-0014).

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

Bound-but-inapplicable keys speak one constant short announced no-op ("No
{zone} on this screen") every time. DL-008's diminishing-verbosity behavior is
retired: no press counting, no adaptive verbosity, never silence (ADR-0009).

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

**Window title:** `Home — StoneReader` (ADR-0006).
**Entry utterance:** `"Home, {current option}"` (ADR-0007).

**Options,** in order, each carrying a Home-scoped jump-and-activate letter
(ADR-0006). Enter or the letter performs a **Screen jump** — the stack resets to
`[Home, target]`.

| Order | Option | Letter |
|---|---|---|
| 1 | Live Game | L |
| 2 | Decks | D |
| 3 | Cards | C |
| 4 | Replays | R |
| 5 | Settings | S |

`B` and `O` are **reserved**, not bound: HSA binds B = Battlegrounds and
O = Open Packs (ADR-0006). Letters are Home-scoped; on other Surfaces bare
letters belong to that Surface's own keymap (ADR-0006).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Enter | Open the current option | "Enter: open the selected screen" |
| L | Jump to Live Game | "L: go to Live Game" |
| D | Jump to Decks | "D: go to Decks" |
| C | Jump to Cards | "C: go to Cards" |
| R | Jump to Replays | "R: go to Replays" |
| S | Jump to Settings | "S: go to Settings" |
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

**Widget type:** Horizontal list with zones (ADR-0004, ADR-0010).

**Reached and left:** Screen jump from Home (`L`, or Enter on option 1), or the
system-wide hotkey Ctrl+Shift+L (landing on Remaining Deck). Back goes Home
(ADR-0006).

**Window title:** `Live Game — StoneReader` (ADR-0006).
**Entry utterance:** the zone's context-entry utterance —
`"{Zone label}, {title}, {position} of {count}"`, degrading to
`"{Zone label}: empty"` when the zone holds nothing, which is also what a Live
Game with no game in progress sounds like (ADR-0007). Labels carry **no turn
prefix**: live, the turn is ambient — the client announces it — and the Replay
Viewer's turn-carrying label exists only because turn stepping changes what
every zone means (ADR-0013).

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

*Remaining Deck* — title `"{Card name}, {n} copy"` / `"…, {n} copies"`
(ADR-0007's worked example). Lines: 1 `"{p} percent to draw"` — nearest whole
percent, copies remaining over cards remaining (ADR-0013); 2 `"{cost} mana"`;
3 `"{Type}"`; 4 `"{Attack} attack, {Health} health"` for minions and weapons;
5 card text.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Left / Right | Previous / next item in the zone | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Shift+Up / Shift+Down | Repeat line / read to last line | Widget-type layer (ADR-0004, ADR-0007) |
| Home / End | First / last item in the zone | Universal layer (ADR-0004) |
| B / G | Jump to your board / opponent board | "B: your minions" / "G: opponent minions" (ADR-0003) |
| C | Jump to your hand | "C: your hand" (ADR-0003) |
| Shift+C | Announced no-op — "The game announces the opponent's hand" | "Shift+C: the game announces the opponent's hand" — *this spec's amendment*: live opponent-hand information is the client's |
| S / Shift+S | Jump to your secrets / opponent secrets | "S: your secrets" / "Shift+S: opponent secrets" |
| V / F | Jump to your hero / opponent hero | "V: your hero" / "F: opponent hero" |
| W / Shift+W | Jump to your weapon / opponent weapon | "W: your weapon" / "Shift+W: opponent weapon" |
| D | Jump to Remaining Deck | "D: jump to Remaining Deck" (ADR-0009's worked example) |
| P / Shift+P | Jump to your played / opponent played | "P: cards you played" / "Shift+P: cards your opponent played" |
| N / Shift+N | Jump to your drawn / opponent drawn | "N: cards you drew" / "Shift+N: cards your opponent drew" |
| A | Speak your mana | "A: how much mana you have" — speak-only, never changes the zone (ADR-0003, ADR-0007) |
| Shift+A | Speak opponent mana | "Shift+A: how much mana your opponent has" — speak-only |
| Shift+D | Speak opponent deck count | "Shift+D: how many cards are in your opponent's deck" — speak-only |
| R | Speak your hero power | "R: your hero power" — speak-only |
| Shift+R | Speak opponent hero power | "Shift+R: your opponent's hero power" — speak-only |
| 1–9 | Jump to position 1–9 in the current zone | "1 to 9: jump to that position in the list" (ADR-0003, ADR-0004) |
| 0 | Jump to position 10 | "0: jump to the tenth item" (ADR-0004) |
| Y | Announced no-op — "No events in a live game" | ADR-0013: play history is the client's feature; HSA's in-game `y` speaks it there |
| F5 / F6 | Announced no-op — "No events in a live game" | ADR-0015: event stepping is replay-only; the phrase is Y's |
| PageUp / PageDown | Announced no-op — "No turns to step in a live game" | ADR-0013: there is no **Live game timeline** |
| Enter | Announced no-op | *This spec's ruling* under ADR-0004's requirement that every Surface assign Enter an action or an announced no-op; matches ADR-0012's Statistics precedent |
| L | Announced no-op — "No game audio during a live game" | *This spec's ruling*: ADR-0008's listen-key surface enumeration (Cards, deck contents, replay zones) deliberately excludes Live Game, where the real client is already producing its own audio; the phrase satisfies ADR-0004's no-silent-universal-key rule |
| Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

Pressing a zone letter for a zone currently holding nothing speaks the
constant "No {zone} on this screen" — every time, no press counting, never
silence (ADR-0009). Speak-only queries follow the `"{Subject}, {value}"`
shape — "Your mana, 4 of 10" (ADR-0007); with no game in progress they speak
the constant "No game in progress" (*this spec's ruling*, same
constant-no-op construct). Letters HSA binds in-game that have no StoneReader
meaning here are not registered and therefore stay silent (ADR-0004: unbound
non-universal keys stay silent). Delete and Space are unbound here and
likewise silent.

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

**Widget type:** Horizontal list, single zone. *This spec's ruling:* ADR-0007's
worked utterance for this Surface — "Aggro Shaman deleted. …, Burn Mage, 2 of 3"
— carries a position, and vertical menus get no position ("menus are small and
stable", ADR-0007), so the utterance is determinative. "Option row" in ADR-0006
and ADR-0012 is informal vocabulary, not a widget-type claim — ADR-0012
describes the Statistics rows the same way and Statistics is a horizontal list.
The two action rows are therefore ordinary items whose Enter acts, which is
exactly what Enter does on the current item (ADR-0004). (The Surface is named
Decks; see [Naming](#announcement-grammar).)

**Reached and left:** Screen jump from Home (`D`, or Enter on option 2); no
system-wide hotkey — Decks is not a mid-game surface and Home reaches it in two
keys (ADR-0006). Back goes Home.

**Window title:** `Decks — StoneReader` (ADR-0006, using the Home option's
name).
**Entry utterance:** `"Decks, {title}, {position} of {count}"`, or
`"Decks: empty"` (ADR-0007).

**Rows,** in order: every saved deck, then the two action rows **"Import
deck…"** and **"Statistics…"** last (ADR-0006 places Import Deck inside Decks;
ADR-0012 places Statistics beside it).

*Deck rows* — title `"{Deck name}"` (ADR-0007: the shortest distinguishing
string; ADR-0007's example utterance uses the bare name). Lines: 1
`"{Class}, {Format}"`; 2 `"{n} cards"`; 3 `"Last played {date}"` or `"Never
played"`.

*Action rows* — title is the row label; no detail lines. Enter drills down.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Left / Right | Previous / next deck | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Home / End | First / last row | Universal layer (ADR-0004) |
| Enter | Open the deck's contents; on an action row, drill into it | "Enter: open the selected deck" |
| Delete | Arm delete, then delete on the second press | "Delete: delete this deck, press twice" (ADR-0004) |
| Shift+Delete | Delete without confirmation | "Shift+Delete: delete this deck without asking" (ADR-0004) |
| C | Copy the deck code to the clipboard | "C: copy this deck's code" |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

*This spec's ruling on surface letters:* surface-layer letter bindings are
available on any Surface, not only on vertical menus, subject to ADR-0003's
standing obligation to check the letter against HSA first — the Replay Viewer's
own speak-only queries (A, R, Shift+A, …) are ADR-0003's precedent for non-zone
letters on a horizontal list. `C` is assigned here because HSA's in-game
`c` ("look at your hand") has no meaning on a deck-management Surface, and HSA's
Collection Manager `C` ("jump to add cards screen") belongs to deck editing,
which does not exist in v1 (checked against
[the HSA command reference](research/hsa-commands-reference.md)). Space is
unbound here and therefore silent.

**Speech:** Delete confirms as `"{Deck name} deleted"` followed by a re-fired
context-entry utterance, because the cursor's content changed. Copy is
cursor-neutral, so it gets the confirmation alone: `"Deck code copied"`
(ADR-0007).

**Audio:** None on the Surface itself; L is an announced no-op here because the
rows are decks, not cards (ADR-0008, ADR-0010).

**Settings that affect it:** None.

### Deck detail (deck contents)

**Widget type:** Horizontal list, single zone.

**Reached and left:** Drill-down from Decks (Enter on a deck row); back pops one
level to Decks (ADR-0006).

**Window title:** `{Deck name} — StoneReader` (ADR-0006).
**Entry utterance:** `"{Deck name}, {title}, {position} of {count}"`, or
`"{Deck name}: empty"` (ADR-0007).

**Rows:** the deck's cards. Title `"{Card name} x{n}"` when the deck holds more
than one copy, `"{Card name}"` otherwise — ADR-0007 names this exact case
("a Deck Contents duplicate needs its count"). Lines: 1 `"{cost} mana"`;
2 `"{Type}"`; 3 `"{Attack} attack, {Health} health"` where applicable; 4 card
text.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Left / Right | Previous / next card | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Home / End | First / last card | Universal layer (ADR-0004) |
| L | Open the **Sounds menu** for this card | "L: listen to this card's sounds" (ADR-0008) |
| Enter | Announced no-op | *This spec's ruling* — see [Enter in v1](#enter-in-v1) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

**Deck detail is read-only in v1.** *This spec's ruling:* there is no card
add, remove, or reorder, and Delete is unbound here (and therefore silent).
ADR-0012's "editing a saved deck keeps its history" is a robustness statement
about attribution surviving a future editing capability, not evidence that one
exists; decks enter the app by import and leave it by delete.

**Audio:** L only, per the universal listen key (ADR-0008).

### Import Deck

**Widget type:** Vertical menu — a form is a vertical menu whose options are
fields and actions (ADR-0004).

**Reached and left:** Drill-down from Decks ("Import deck…"), or by accepting
the clipboard **Offer**, which resets the stack to `[Home, Decks, Import
Deck]` with the code pre-filled (ADR-0014). Either way back pops one level to
Decks; so does a completed import, where the new deck is (ADR-0006).

**Window title:** `Import Deck — StoneReader` (ADR-0006).
**Entry utterance:** `"Import Deck, {current option}"` (ADR-0007). The Surface
never lands the User in Text mode on entry (ADR-0004).

**Options,** in order (ADR-0004's worked example gives exactly these two):

1. `"Deck code, edit text"` — Enter enters Text mode on the field.
2. `"Import"` — Enter imports the code in the field.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Enter | On the field, start typing; on Import, import the code | "Enter: edit this field, or run this action" |
| Escape | Leave Text mode without committing, or back | Universal layer; Escape is never dead (ADR-0004) |
| Home / End | First / last option | Universal layer (ADR-0004); in Text mode, the ends of the field (ADR-0011) |
| F1 | Help — in Text mode, the rescue phrase | "F1: help for this screen" (ADR-0009) |
| Left / Right | Unbound in navigation; caret movement with spoken characters in Text mode | ADR-0004, ADR-0011 |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

**Speech:** Import confirms as `"{Deck name} imported"` (ADR-0007's worked
example). *This spec's decision:* a failed import announces the failure and
keeps the field's contents, patterned on the refused-commit shape ADR-0011
specced for an invalid path.

**Audio:** None.

---

## Cards

**Widget type:** Horizontal list, single zone. Card Library is deleted; Home →
Cards opens the browser directly on All Cards, with class selection, search, and
the mana filter inside the list — one Surface, one keymap (ADR-0006). Generated
help reads "Cards is a horizontal list: Left and Right move between cards, Up
and Down read details" (ADR-0009's sentence, under this spec's
[Naming](#announcement-grammar) ruling).

**Reached and left:** Screen jump from Home (`C`, or Enter on option 3) or the
system-wide hotkey Ctrl+Shift+C. Back goes Home (ADR-0006).

**Window title:** `Cards — StoneReader` (ADR-0006).
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
{Health} health"` for minions and weapons, `"{Durability} durability"` for
weapons' second stat; 4 card text; 5 `"{Class}"`; 6 `"{Rarity}"`; 7 `"{Set}"`.
One fact per line, spoken text equal to displayed text (ADR-0007).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Left / Right | Previous / next card | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Home / End | First / last card in the whole filtered list | Universal layer (ADR-0004) — list-scoped, not page-scoped; see the ruling below the table |
| Tab / Shift+Tab | Next / previous class filter | "Tab: jump to the next class" (ADR-0004, mirroring HSA's Collection Manager — [command reference](research/hsa-commands-reference.md)) |
| Ctrl+F | Search cards | "Ctrl+F: search for a card" (ADR-0004) |
| 0–8 | Filter by that exact mana cost; re-press clears | "0 to 8: show only cards of that mana cost" (ADR-0003, ADR-0004) |
| 9 | Filter to 9 mana or more; re-press clears | "9: show only cards costing 9 or more" (ADR-0004) |
| PageUp / PageDown | Move ten cards back / forward, clamped at the ends | "Page Down: jump ten cards forward" (ADR-0004's paging slot) |
| L | Open the **Sounds menu** for this card | "L: listen to this card's sounds" (ADR-0008) |
| Enter | Announced no-op | *This spec's ruling* — see [Enter in v1](#enter-in-v1) |

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

**Widget type:** Horizontal list, single zone.

**Reached and left:** Screen jump from Home (`R`, or Enter on option 4) or the
system-wide hotkey Ctrl+Shift+R. Back goes Home (ADR-0006).

**Window title:** `Replays — StoneReader` (ADR-0006).
**Entry utterance:** `"Replays, {title}, {position} of {count}"`, or
`"Replays: empty"` (ADR-0007).

**Rows:** finished games, **most recent first** — *this spec's decision*; row
order is per-surface spec territory, and ADR-0012's most-recently-played
ordering on Statistics is the precedent — then the action row **"Import
replays…"** last, the Decks action-row idiom: the flow ends where its results
appear (ADR-0014).

*Replay rows* — title
`"{Result} versus {Opponent class}, {n} turns"` — ADR-0007 names this Surface as
the case where "a replay row needs opponent/result/turn because bare names would
all sound alike". Lines: 1 `"{Date}, {time}"`; 2 `"Played {Deck name}"` or
`"Deck not detected"` (ADR-0012's attribution); 3 `"{Game type}, {Format}"`;
4 `"Counted in stats"` / `"Not counted"` — membership shows as a detail line,
never in the title (ADR-0012); 5 `"Live recorded"` / `"Imported"`.

*Action row* — title is the row label; no detail lines. Enter drills down.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Left / Right | Previous / next replay | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Home / End | First / last replay | Universal layer (ADR-0004) |
| Enter | Open this replay in the Replay Viewer; on the action row, drill into Import Replays | "Enter: open this replay" (ADR-0006's drill-down, ADR-0014) |
| Space | Count this game in your stats, or stop counting it | "Space: count this game in your stats" (ADR-0012) |
| Delete | Arm delete, then delete on the second press | "Delete: delete this replay, press twice" (ADR-0004) |
| Shift+Delete | Delete without confirmation | "Shift+Delete: delete this replay without asking" (ADR-0004) |
| Ctrl+F | Announced no-op — "No search on this screen" | Slot default (ADR-0004); no ADR gives Replays a search |
| PageUp / PageDown, Tab / Shift+Tab, L | Announced no-op | Slot defaults (ADR-0010) |

**Speech:** The Space toggle confirms verb-past and cursor-neutral —
`"Included in stats"` / `"Excluded from stats"`, with no re-entry utterance
(ADR-0012). Delete changes what is under the cursor, so its confirmation is
followed by a re-fired context-entry utterance (ADR-0007).

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
**Entry utterance:** `"Import Replays, {current option}"` (ADR-0007). The
Surface never lands the User in Text mode on entry (ADR-0004).

**Options,** in order (ADR-0014):

1. `"Choose files, none chosen"`, becoming `"Choose files, {n} files chosen"`
   — Enter opens the OS-native file dialog, multi-select, filtered to
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
| Up / Down | Previous / next option | Widget-type layer (ADR-0004) |
| Enter | On Choose files, open the file dialog; on the toggle, flip it; on Import, import the chosen files | "Enter: edit this field, or run this action" |
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

**Widget type:** Horizontal list with zones (ADR-0003, ADR-0004, ADR-0010).

**Reached and left:** Drill-down from Replays (Enter on a replay row); back pops
one level to Replays (ADR-0006).

**Window title:** `Replay Viewer — StoneReader` (ADR-0006).

**Entry utterance:** *this spec's ruling* — the Replay Viewer's context label
carries the turn the way Cards' label carries its filters:
`"Turn {t}, {yours | opponent's}, {Zone label}"`. The full utterance is
therefore
`"Turn {t}, {yours | opponent's}, {Zone label}, {title}, {position} of {count}"`
— "Turn 5, yours, Your board, Fireball, 1 of 3" — degrading to
`"Turn {t}, {yours | opponent's}, {Zone label}: empty"`. It fires identically on
every landing: drill-down from Replays, back-reveal, zone switch, orientation
reread, **and turn step**. A turn step is an in-place rebuild — this spec
extends ADR-0007's landing-route list with it, since a turn step changes what
every zone holds exactly the way a filter change does on Cards — so route
invariance holds: the same turn in the same zone always sounds the same. The
shipped bespoke turn utterance ("Turn 5, your turn, 3 events.") is replaced.

Zone cursors persist across switches, across turn steps, and across back-reveal
(ADR-0007, ADR-0010) — with one amendment: the **events cursor is the replay
position**, so a turn step repositions it to the new turn's first event
(ADR-0015). Every other cursor keeps the unamended rule.

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

*Hero zones* — title `"{Hero name}, {Health} health"`, plus `", {Armor} armor"`
when nonzero. Lines: hero power, weapon, secrets count.

*Events zone* — title is the Narrator's phrase for that **Game event**
(ADR-0010 owns the phrasing seam). Lines: 1 `"Turn {t}"`; 2 the source card's
title where the event has one.

**Event scrubbing** (ADR-0015). The events zone is the Surface's **fine
axis**: the selected event renders every other zone at the game just after
that event. Scrub from inside the zone with Left/Right, 1–9/0, or Home/End,
or from **any** zone with `F5`/`F6` (previous / next event) — stay on the
board and watch it change event by event. A turn step lands the events
cursor on the turn's **first** event, so a turn reads forward; the turn's
last event carries the turn's final state, so stepping to it (or End in the
events zone) reads the turn as it ended. At the turn's edges F5/F6 clamp
and repeat the current title — turn boundaries are PageUp/PageDown's job.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Left / Right | Previous / next item in the zone | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Shift+Up / Shift+Down | Repeat line / read to last line | Widget-type layer (ADR-0004, ADR-0007) |
| Home / End | First / last item in the zone | Universal layer (ADR-0004) |
| PageUp / PageDown | Previous / next turn | "Page Down: go to the next turn" — turn stepping is this Surface's coarse axis (ADR-0004) |
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
| L | Open the **Sounds menu** for the focused card | "L: listen to this card's sounds" (ADR-0008) |
| Enter | Announced no-op | *This spec's ruling* — see [Enter in v1](#enter-in-v1) |
| Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

Pressing a zone letter for a zone this replay has nothing in speaks the constant
"No {zone} on this screen" — every time, no press counting, never silence
(ADR-0009). Speak-only queries follow the `"{Subject}, {value}"` shape — "Your
mana, 4 of 10" (ADR-0007). Delete and Space are unbound here and therefore
silent.

**Speech:** Turn stepping is speech-only (ADR-0008) and speaks the context-entry
utterance above — turn, side, zone, title, position — so a turn step and a zone
switch are the same announcement with a different part changed. There is no
separate turn announcement and no event count in it; the events zone is where
events are counted, browsed, and scrubbed. Scrubbing adds no utterance of its
own: an event landing — Left/Right in the zone or F5/F6 from anywhere —
speaks the event's title as always, and the zones simply read as of that
event when visited — no "after {event}" prefix anywhere (ADR-0015, ADR-0007's
route invariance).

**Audio:** The **events zone auto-plays**: landing on an event plays that
event's sound — its card's Play/Attack/Death line, upgraded to card-specific
Foley by CardID where one exists and falling back to the generic base clip for
the common voiceless case — replacing any playing clip and mixing under the
event's narration (ADR-0008; research fact sheet findings 11–12). Turn stepping
is silent. Hero-power, discover, and emote-wheel events stay silent, because
names alone cannot identify their clips (research fact sheet finding 13). The
auto-play is always on with a Settings kill-switch (ADR-0008).

**Settings that affect it:** Replay auto-play (the kill-switch); Game audio
volume; Hearthstone install path (ADR-0011). With no install found, the events
zone is silent and the listen key announces that game audio is unavailable
(ADR-0008).

---

## Statistics

**Widget type:** Horizontal list, single zone (ADR-0012).

**Reached and left:** Drill-down from Decks ("Statistics…") — the only door in
v1. Back pops one level to Decks (ADR-0012, ADR-0006).

**Window title:** `Statistics — StoneReader` (ADR-0006).
**Entry utterance:** `"Statistics, {title}, {position} of {count}"` (ADR-0007).
Statistics are computed by a stats service on Surface entry — no caching, no
persisted aggregates (ADR-0012).

**Rows,** in this order (ADR-0012):

1. **All decks** — the overall record.
2. Every attributed deck identity and saved deck, ordered by most recently
   played. Zero-game saved decks are included, because a deck that vanished from
   Statistics would read as an attribution bug.
3. **Other games** — ambiguous or unattributed games, last. It still counts in
   the overall record.

**Title line:** `"{Name}, {W} wins, {L} losses"`, appending `", {T} ties"` only
when nonzero; zero-game decks say `"{Name}, no games yet"`. The percent
deliberately stays out of the title (ADR-0012).

**Detail lines,** one fact per line (ADR-0012):

1. `"Win rate, {p} percent"` — wins ÷ (wins + losses); `UNKNOWN` results are
   excluded from the rate, and abandoned games are absent from the store
   entirely.
2. `"Last 20 games, {w} wins, {l} losses"` — the fixed recency window, omitted
   when the total is 20 or fewer.
3. One line per **Opponent** class with at least one game, ordered by games
   played descending: `"Versus {class}, {w} wins, {l} losses"`.

**Corpus and attribution.** Statistics are computed over the **Stats corpus**:
live-recorded games are members by default, imported **Replays** are not but can
join, and Space on the Replays surface is the toggle (ADR-0012). Deck statistics
cover constructed games — ranked and casual, unfiltered; arena and Battlegrounds
games are excluded because neither plays a saved deck. Games are attributed by
`deck_id` with the deck name snapshotted at save time, so editing a deck keeps
its history and deleting one leaves its games under the snapshotted name
(ADR-0012). An imported replay is counted from its own recorded perspective —
a replay recorded from the opponent's side attributes the wrong side's result;
the toggle is the remedy, not detection (ADR-0012, documented not solved).

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Left / Right | Previous / next row | Widget-type layer (ADR-0004) |
| Up / Down | Previous / next detail line | Widget-type layer (ADR-0004) |
| Home / End | First / last row | Universal layer (ADR-0004) |
| Enter | Announced no-op | Explicitly a no-op in v1 (ADR-0012); the phrase is the registry's no-op default (ADR-0010) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

Delete and Space are unbound here and therefore silent — the stats-membership
toggle lives on Replays, where the game rows are (ADR-0012).

**Future — not in scope for implementation PRDs:** Enter drilling into the
deck's games as a filtered Replays view. It is real value but specs a
filtered-list capability this Surface does not own; the door stays marked for
whichever effort needs filtered lists first (ADR-0012).

**Data-layer work the PRDs inherit** (ADR-0012): the recorder plumbs the
detected deck id and name at save (the columns exist and have no writer); the
recorder writes `UNKNOWN` instead of a fabricated `TIED` when no playstate was
observed; an `in_stats` flag with live-recorded-in / imported-out defaults; a
one-time backfill migration on first post-upgrade launch, re-deriving
attribution from stored XML by the same exact-unique-match rule and logged; the
dead v1 `games` table is dropped, not revived.

**Settings that affect it:** Replay retention prunes the store the corpus is
computed over (ADR-0011; ADR-0012).

---

## Settings

**Widget type:** Vertical menu — one flat menu; nothing sits more than two
levels deep, and only individual chord rows sit at two (ADR-0011).

**Reached and left:** Screen jump from Home (`S`, or Enter on option 5); no
system-wide hotkey (ADR-0006). Back goes Home.

**Window title:** `Settings — StoneReader` (ADR-0006).
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
| Up / Down | Previous / next setting | Widget-type layer (ADR-0004) |
| Enter | Change this setting | "Enter: change this setting" |
| Delete | Arm reset, then reset on the second press — "Press Delete again to reset {label} to {default}" | "Delete: reset this setting, press twice" (ADR-0011 on ADR-0004's idiom) |
| Shift+Delete | Reset this setting to its default without arming; on Restore all defaults, restore everything without arming | "Shift+Delete: reset this setting without asking" — *this spec's ruling*, ADR-0004's Shift-skips-confirmation composed with ADR-0011's Delete-as-reset |
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

**Unavailable rows explain, never hide.** With no Hearthstone install found, the
game-audio rows stay visible and announce their reason — "Game audio volume,
unavailable — no Hearthstone install found" (ADR-0011).

**Deliberate exclusions from this Surface** (ADR-0011): no speech
rate/voice/synth settings (speech exits via the User's screen reader and was
never ours to mix); no HSA-letter rebinding (the letter keymap is the app's
identity); no visual or theme settings (no sighted chrome remains).

### Global hotkeys (drill-down)

**Widget type:** Vertical menu (ADR-0011).

**Reached and left:** Drill-down from the Settings "Global hotkeys" row; back
pops one level to Settings (ADR-0011, ADR-0006).

**Window title:** `Global hotkeys — StoneReader` (ADR-0006).
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
| Up / Down | Previous / next hotkey | Widget-type layer (ADR-0004) |
| Enter | Record a new shortcut for this command | "Enter: record a new shortcut" (ADR-0011) |
| Escape | Cancel capture, or back | Universal layer (ADR-0004, ADR-0011) |
| Home / End | First / last hotkey | Universal layer (ADR-0004) |
| Delete | Arm reset to the default chord, then reset | "Delete: reset this shortcut, press twice" (ADR-0011) |
| Shift+Delete | Reset this shortcut to its default without arming | "Shift+Delete: reset this shortcut without asking" (ADR-0004, ADR-0011) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F, L | Announced no-op | Slot defaults (ADR-0010) |

---

## Help menu

**Widget type:** Vertical menu, on the ordinary navigation stack (ADR-0004,
ADR-0009).

**Reached and left:** F1 from any Surface — a **Drill-down** that pushes one
level. Backspace/Escape returns. F1 inside help is an announced no-op ("Already
in help") — help never stacks on help (ADR-0009).

**Window title:** `{Surface} help — StoneReader`, e.g. `Cards help —
StoneReader`. *This spec's ruling, compositionally:* the Help menu's surface
name is "{Surface} help" (ADR-0009) and ADR-0006's template wraps every surface
name.
**Entry utterance:** `"{Surface} help, {current option}"` — the vertical-menu
form, with the widget-type sentence as the current option on entry (ADR-0007,
ADR-0009).

**Options,** in order (ADR-0009):

1. **The widget-type sentence**, generated from the Surface's declared type —
   "Cards is a horizontal list: Left and Right move between cards, Up and Down
   read details."
2. **Screen-specific bindings**, one option per binding, **key-first**:
   `"{Key}: {action phrase}"` — "D: jump to Remaining Deck". Title-line rules
   apply; these are the phrases in every keymap table above.
3. **"Universal keys"** — a drill-down listing the app-wide layer (Enter,
   Escape/Backspace, Home/End, PageUp/PageDown, Tab/Shift+Tab, Ctrl+F, F1, L,
   bare Ctrl, Ctrl+Q). The structure carries the universal/screen-specific
   distinction; options are never individually labeled with it. Delete,
   Shift+Delete, and Space are surface-layer bindings and therefore appear in
   option group 2 on the Surfaces that bind them, not here.
4. **"All commands"** — a drill-down of per-surface sections in Home order, each
   a nested vertical menu of that Surface's bindings: the in-app command
   reference, generated from the same registry.

**Keys**

| Key | Command | Spoken help phrase |
|---|---|---|
| Up / Down | Previous / next help option | Widget-type layer (ADR-0004) |
| Enter | Do this command | Pops help and performs that binding on the underlying Surface — help doubles as a command palette (ADR-0009) |
| Ctrl+F | Search help | "Ctrl+F: search help" (ADR-0009) |
| F1 | Announced no-op — "Already in help" | ADR-0009 |
| Escape / Backspace | Back | Universal layer (ADR-0004) |
| Home / End | First / last help option | Universal layer (ADR-0004) |
| PageUp / PageDown, Tab / Shift+Tab, L | Announced no-op | Slot defaults (ADR-0010) |

Options that cannot sensibly execute — Enter itself, Text-mode keys, All-commands
entries ("Only available on {surface}") — are announced no-ops (ADR-0009,
ADR-0004). Destructive safety is unchanged: a delete executed from help still
only arms and asks for its second press (ADR-0009).

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
| Up / Down | Previous / next sound | Widget-type layer (ADR-0004) |
| Enter | Play this sound | "Enter: play this sound" (ADR-0008) |
| Escape / Backspace | Back | Universal layer (ADR-0004) |
| Home / End | First / last sound | Universal layer (ADR-0004) |
| L | Announced no-op | Already in the Sounds menu; slot default (ADR-0010) |
| PageUp / PageDown, Tab / Shift+Tab, Ctrl+F | Announced no-op | Slot defaults (ADR-0010) |

There is no play-on-focus: menus act on Enter everywhere else, and rapid
arrowing would stutter through replaced clips (ADR-0008).

**Degenerate cases** (ADR-0008, and ADR-0004's no-silent-universal-key rule):

- Card with no clips: L announces `"{title}: no sounds"` and does **not** push
  the Surface.
- No Hearthstone install found: L announces that game audio is unavailable and
  does not push.

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
| Arena assist / drafting | Not on this map. ADR-0003 notes only the standing obligation that a future arena-drafting surface check HSA's vocabulary before picking keys. Arena games are excluded from deck statistics because they play no saved deck (ADR-0012). |
| Onboarding / installer | Explicitly out of scope on this map: first run means no settings file means all defaults, and there is no setup wizard — Settings is for divergence (ADR-0011). ADR-0008's required "not affiliated with Blizzard Entertainment / assets © Blizzard" notices land with this effort; no v1 Surface carries them. |

---

# Open questions

None. The last one — the prompt construct, how StoneReader asks the User a
question ([#35](https://github.com/akj/stonereader/issues/35)) — was resolved
by ADR-0014 and is folded in above: the closed
[asking-idiom inventory](#asking), the restated
[clipboard offer](#navigation-stack-window-title-topology), and
[Import Replays](#import-replays).
