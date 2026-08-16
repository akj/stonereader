# How StoneReader asks: no invented dialogs

## Status

Accepted (design contract, 2026-08-16). Builds on ADR-0004 (press-twice
confirm, the modal-dialog rejection), ADR-0006 (the clipboard offer, stack
semantics), ADR-0011 (input states, editing idioms), and ADR-0012 (the
once-per-batch stats question). Amends ADR-0006's clipboard clause and
ADR-0011's value-type list. Implementation lands via PRDs opened against
the final UI spec (wayfinder map #17); nothing here ships code by itself.
Decided in ticket #35.

## Context

Three decided behaviors need to ask the User something, and the design had
no way to ask: ADR-0004 rejected modal dialogs and ADR-0011 closed the
input model at exactly three states, none of them "question pending". The
clipboard deckstring offer (ADR-0006) was worded "press Enter to import" —
but Enter is a surface-owned slot on every Surface (ADR-0010), and window
activation can arrive in the middle of the User's own keypress, so Enter
as the accept would steal keystrokes aimed at the surface. Replay import
(ADR-0012) has no shipped UI at all: `ReplayStore.import_file()` has no
production caller, the package contains no file dialog of any kind, and
the once-per-batch stats question ("Count these N games in your stats?")
has no home.

The shipped clipboard flow is the app's one modal — a `wx.MessageDialog`
on window activation — and also its documented accessibility scar: screen
readers lose their place after dismissal (UAT Gap 3, D-06), patched by a
`restore_focus` hack whose docstring names this dialog as the motivating
callsite. The deciding grilling opened from the other side: native Windows
dialogs are idiomatic and well-supported by screen readers, so perhaps
modals are the right shape after all. The ruling below keeps the true half
of that instinct (delegation to OS-native dialogs) and bans the half that
already bit us (app-invented dialogs, unsolicited focus theft).

## Decision

### The ruling

**StoneReader never invents a dialog and never asks unsolicited.**
OS-owned questions are delegated to OS-native dialogs; StoneReader's own
questions are expressed in the existing grammar. The inventory of asking
idioms is closed — there is no fifth:

| Idiom | Question shape | Where it lives |
|---|---|---|
| **Confirm** | "Are you sure?" — press the same key again | Armed delete (ADR-0004); single-modifier chord warning (ADR-0011) |
| **Offer** | Unsolicited proposition — accept by dedicated chord, ignore for free | This ADR |
| **Form field** | A parameter with a default — the question dissolves | Import Replays' stats toggle (below) |
| **Picker** | Solicited choice among values | ADR-0011 |

### The Offer

An **Offer** is an ephemeral Lane-1 announcement that arms a single
dedicated accept chord: **Ctrl+Enter**, bound to nothing else anywhere in
the app, so acceptance is always deliberate and no surface key is ever
shadowed. An armed Offer is a pending flag inside navigation state —
exactly as armed delete is — not a fourth input state; ADR-0011's
three-state closure stands.

Lifetime rules:

1. An Offer arms **only in navigation state**. If its trigger fires during
   Text or Capture mode, the Offer is dropped, not queued.
2. **Any keypress other than Ctrl+Enter disarms it silently** and does its
   own normal work — declining costs zero keypresses and no speech.
3. With no Offer armed, Ctrl+Enter is an ordinary unbound non-universal
   chord: silent (ADR-0004).
4. An Offer fires **once per unique subject** — re-triggering on the same
   subject does not re-offer.
5. The announcement names the chord as a spoken word sequence (ADR-0011):
   "… — press Control Enter to …".

### The clipboard offer, restated

The first Offer: on window activation with a deckstring on the clipboard,
"Deck code on clipboard — press Control Enter to import". Its unique
subject is the clipboard content (the shipped same-content guard is kept),
and **StoneReader's own copies write that guard** — C-copy on Decks never
leads to an offer to import the code the app just handed you.

**Accepting resets the stack to Home → Decks → Import Deck** with the code
pre-filled. Accept can fire from any surface, so the landing must be
ruled: it is neither a pure jump nor a pure drill-down, and the reset wins
because route invariance is the design's spine — accepting always lands
the same place, and back pops to Decks, where the imported deck will be
(ADR-0006's own rationale). This amends ADR-0006's "press Enter to import"
wording and its "accepting drills into" clause.

### OS delegation, the carve-out

The dialog ban is on *invention*, not on modality: for a question the OS
already owns, StoneReader delegates to the OS-native dialog — standard
Windows UI the audience drives fluently every day, with screen-reader
support no homegrown Surface would match. This is the third delegation of
its kind: speech exits via the User's screen reader (ADR-0008), game
history stays in the client (ADR-0013), files belong to the OS. First
user: the multi-select file dialog in replay import. Plausible future
users: browse options for the install/log path rows (ADR-0011), should
they ever want one.

### Replay import

The flow ADR-0012 assumed now exists, fully in-grammar:

- **Door**: an **"Import replays…" action row, last on the Replays
  surface** — the Decks action-row idiom (ADR-0006/0012), and the flow
  ends where its results appear.
- **Import Replays** is a form — a vertical menu (ADR-0004) of three rows:
  1. `"Choose files, none chosen"` → `"{n} files chosen"` — Enter opens
     the OS-native file dialog, multi-select, filtered to
     `.hsreplay`/`.xml`; the dialog's Cancel is the idiom's no-commit
     exit.
  2. `"Count in stats, off"` — an ADR-0011 toggle, default off
     (ADR-0012's imported-out default), applied to this batch. The
     once-per-batch question is never asked: it dissolved into a visible,
     revisitable field with the right default.
  3. `"Import"` — the action. With nothing chosen it refuses with an
     announcement ("No files chosen") — ADR-0011's refused-commit shape.
- **Completion** pops back to Replays: a verb-past confirmation followed
  by the re-entry utterance (ADR-0007), speaking only nonzero parts —
  `"{n} imported"`, appending `", {d} already in Replays"` (the store
  dedupes by content hash) and `", {f} failed"` only when nonzero
  (ADR-0012's only-when-nonzero economy).
- The **file field** joins ADR-0011's editing idioms as the fifth value
  type: its editor is a delegated OS dialog.

## Alternatives considered and rejected

- **An app-invented modal for the clipboard offer** (shipped behavior).
  Rejected: declining is the common case for an unsolicited proposition,
  and the modal taxes exactly that path (a keypress plus a focus
  round-trip — the D-06 scar); activation races the User's in-flight
  keystrokes into the dialog's default button; dialogs are a second
  dialect that punches exempt zones into every contract invariant (F1
  from the registry, route-invariant utterances, no silent universal
  keys); and `ShowModal` nests an event loop while global hotkeys and
  Lane-2 narration keep firing.
- **Enter as the accept key** (ADR-0006's original wording). Rejected:
  Enter is a surface-owned slot (ADR-0010), and an unsolicited offer must
  never steal a keypress aimed at the surface.
- **Y as the accept key.** Rejected: it is a zone letter on the Replay
  Viewer — ambiguous exactly where offers can arrive.
- **Dissolving the offer into pure information** ("Deck code on
  clipboard", act on it by ordinary navigation). Rejected: it taxes the
  single most common import flow (copy in browser, Alt+Tab back) from one
  deliberate chord to a multi-key trek.
- **A prompt construct** — a question surface or fourth input state that
  captures the next keypress. Rejected: the modal dialog in a new coat,
  with the same stolen-keystroke hazard.
- **A discovered-files Surface** instead of the OS dialog. Rejected:
  Hearthstone never writes `.hsreplay`, so discovery is guesswork over
  other tools' folders, with no fallback when the scan finds nothing —
  and it slowly re-implements a file manager inside the two-widget
  grammar.
- **A typed path field** as the file mechanism. Rejected: maximally
  hostile ergonomics for deep paths, for zero machinery saved.
- **The stats question as a post-import Offer.** Rejected: the answer
  would be ephemeral (missing it means N Space presses on Replays), and
  it would stretch the Offer from unsolicited to mid-flow use on day one.
  The form field keeps the construct pure.
- **The stats question as a Yes/No picker after the dialog.** Rejected: a
  question that can be a default should not be asked at all.

## Consequences

**Positive.** The asking inventory is closed and testable: no app-invented
dialog exists, no utterance ever demands the next keypress, and ignoring
any Offer is free. The app's one shipped modal is retired along with the
`restore_focus` hack's motivating case. Replay import — door, files, stats
membership — lands with zero new grammar beyond one value type. Ctrl+Enter
gives every future unsolicited proposition a ready-made shape.

**Negative.** Ctrl+Enter becomes a reserved app-wide chord no Surface may
bind (capture mode's already-bound refusal covers it: "Control Enter is
taken by Accept offer"). The file field makes ADR-0011's value-type list
five long. An Offer is ephemeral by design: a missed announcement means
finding the import route by hand (mitigated: the code is still on the
clipboard, and Decks → Import deck… is never more than a few keys away).
A delegated OS dialog is still a real modal inside the app's process —
accepted as OS-owned UI, the same way the screen reader owns speech.
ADR-0006 and ADR-0011 carry amendment notes.
