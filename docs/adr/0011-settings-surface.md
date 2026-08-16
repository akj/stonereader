# Settings surface: one flat menu, three input states, immediate apply

## Status

Accepted (design contract, 2026-08-15). Consumes the deferred handoffs from
ADR-0007 (Lane-2 narration content), ADR-0008 (game-audio controls), and
ADR-0006 (global-hotkey chords); refines ADR-0004's text mode with spoken
character navigation. Implementation lands via PRDs opened against the final
UI spec (wayfinder map #17); nothing here ships code by itself. Decided in
ticket #25.

## Context

The charter locked Settings' scope: speech behavior, global-hotkey
rebinding (the six system-wide chords only — the HSA letter keymap is the
app's identity and is not rebindable), plumbing, and game-audio controls.
Three ADRs have since parked decisions here: which Game events Lane 2
narrates (ADR-0007/0010), the audio volume / auto-play switch / install
path (ADR-0008), and the rebindable chord table (ADR-0006). No settings
persistence exists in the shipped app — every behavior is hardcoded, and
app data already lives under `~/.stonereader/` (logs, replay store). The
cautionary tale is HSDT's 26-pane options tree.

## Decision

### Inventory

Seven top-level rows plus a drill-down: **Narration** (preset), **Game
audio volume**, **Replay auto-play**, **Hearthstone install path**,
**Hearthstone log path**, **Replay retention**, **Global hotkeys**
(drill-down: six chord rows), and a final **Restore all defaults** row.

Exclusions, each deliberate: no speech rate/voice/synth settings (speech
exits via the User's screen reader and was never ours to mix, ADR-0008); no
HSA-letter rebinding (charter); no visual/theme settings (no sighted chrome
remains, ADR-0006).

### Shape

Settings is one flat vertical menu — nothing sits more than two levels deep,
and only individual chord rows sit at two. Row titles are
`"{Label}, {current value}"` ("Narration, key moments"; "Jump to Live Game,
Ctrl Shift L" — chords spoken as word sequences), so a single Down-arrow
sweep reads the whole configuration. Paths are the one unspeakable value:
their titles say "auto-detected" or "custom", with the full path on the
detail line and in text mode. No Ctrl+F — seven rows; the announced no-op
("No search on this screen", ADR-0004) is the spec.

### Editing idioms, by value type

- **Toggle** (Replay auto-play): Enter flips it and announces the row's new
  title.
- **Choice** (Narration, Retention) and **Volume** (0–100 in steps of 10):
  Enter drills into a **picker** — a vertical menu of the values, cursor on
  the current one; Enter selects and pops back, re-announcing the parent
  row; back exits without change. No cycling: a picker speaks its options,
  cycling hides them.
- **Path**: Enter enters text mode on the field; Enter commits (validation
  announced — an invalid path refuses commit and keeps the previous value),
  Escape abandons.
- **Chord**: Enter enters capture mode (below).
- **Files** (added by ADR-0014; first user is Import Replays' "Choose
  files" row): Enter opens the OS-native file dialog, multi-select; the
  row title carries the result ("{n} files chosen"). The editor is a
  *delegated* OS dialog, not an invented one — ADR-0014 owns that ruling.

Every idiom has a no-commit escape hatch; nothing on the surface has hidden
staged state.

**Text-mode refinement (extends ADR-0004 app-wide):** in text mode,
Left/Right move the caret one character and speak the character crossed;
Home/End jump to the ends of the field. ADR-0004 specced only the caret
movement; the spoken half is now contract.

### Capture mode — the third input state

Enter on a chord row announces "Press the new shortcut for {name}. Escape
cancels." and enters **capture mode**: the next chord pressed becomes the
candidate. Beside navigation and text mode, capture mode is the third input
state; there is no fourth.

Acceptance policy: at least one modifier is required — bare keys are
refused outright (a system-wide bare letter or F-key is indefensible). A
single-modifier chord is accepted only through a warning plus press-again
confirm ("Shift C is a single-modifier shortcut; other apps, including
Hearthstone Access, may use it. Press it again to bind anyway") — these
chords are stolen system-wide from every application, including HSA's
Shift+letter pairs and the OS clipboard keys, so the hazard is surfaced
exactly when it is live, in the press-twice idiom the app already speaks.
Two-or-more-modifier chords bind directly. A chord already bound within
StoneReader is refused with its owner named ("Ctrl Shift C is taken by
Jump to Cards"). If OS registration fails, the failure is announced and the
previous binding is kept.

### Narration presets (the Lane-2 content, deferred since ADR-0007)

One Choice setting, three presets. The membership test for Key moments:
*things you'd miss by not watching that change your next decision.* The
User's own plays are narrated by neither preset — you did them.

| Game event | Key moments | Everything |
|---|---|---|
| Turn flip | yes | yes |
| Opponent plays a card | yes | yes |
| Minion dies | yes | yes |
| Secret played / revealed | yes | yes |
| Game over (result) | yes | yes |
| Friendly Player draws (card name) | — | yes |
| Opponent draws (count only) | — | yes |
| Attacks (attacker → target) | — | yes |
| Hero power used | — | yes |
| Triggers / deathrattles | — | yes |

This table is the preset definition; per-surface PRDs may amend membership
without reopening this ADR — the Narrator seam (ADR-0010) makes it one
table. (The ui-spec later removed turn flips and opponent draws from every
preset as client-redundant — the client announces both itself, ADR-0013's
principle. The ui-spec table is current.)

### Apply, persist, reset

Every change applies immediately (the preset re-tunes the Narrator live;
volume affects the next clip) and autosaves. No OK/Cancel, no unsaved-changes
state — a staged-commit form would be the app's only surface with hidden
state. Delete on any row resets that setting to its default through the
app-wide press-twice idiom ("Press Delete again to reset {label} to
{default}"); the Restore-all-defaults row works the same way.

Storage: `~/.stonereader/settings.json` — flat JSON, missing key means
default, unknown keys ignored (forward-compatible), no schema versioning
until a real migration exists.

### Defaults

Narration **Key moments**; volume **80**; auto-play **On** (the setting is
ADR-0008's kill-switch); both paths **auto-detected**; retention
**Unlimited** (caps: last 100 / 500 / 1000 games, pruned oldest-first on
write — count caps degrade predictably where age caps punish infrequent
players); chords **the ADR-0006 table**. First run means no settings file
means all defaults — no setup wizard (onboarding is out of scope on this
map). Settings is for divergence.

### Unavailable rows explain, never hide

With no Hearthstone install found, the game-audio rows stay visible and
announce their reason ("Game audio volume, unavailable — no Hearthstone
install found"). Rows that vanish teach the User the app is haunted; rows
that explain teach them what to fix.

## Alternatives considered and rejected

- **Per-event narration toggles.** Rejected for presets: the HSDT options
  tree is the cautionary tale, and a per-event layer remains purely
  additive later if a preset boundary ever pinches.
- **Grouped settings tree** (Speech / Audio / Storage panes). Rejected:
  ten items fit one flat menu; only the six-chord clump earns a drill-down.
- **Enter-cycles for Choice values.** Rejected: cycling hides the option
  set; a picker speaks it.
- **Left/Right volume adjustment on the row.** Rejected: Left/Right are
  deliberately dead in vertical menus (ADR-0004) — silence there is the
  widget-type signal.
- **Hard two-modifier requirement for chords** (this ADR's first draft).
  Rejected after grilling as paternalistic; replaced by the
  warn-and-confirm path for single-modifier chords.
- **Auto-swap on chord conflict.** Rejected: it moves a binding the User
  didn't touch.
- **Staged OK/Cancel commit.** Rejected: the only hidden state in the app.
- **Hiding unavailable rows.** Rejected: see above.
- **Age-based retention.** Rejected: it punishes infrequent players.

## Consequences

**Positive.** The whole configuration is one Down-arrow sweep. The input
model closes at exactly three states — navigation, text mode, capture
mode — all entered explicitly, all with a no-commit exit. Lane-2 narration
content is finally defined in one amendable table. `settings.json` is
trivially inspectable and testable; immediate-apply plus autosave means the
file always mirrors the running app.

**Negative.** The frame-level input sink (ADR-0010) grows a third state to
own. Pickers add a drill-down hop per Choice edit. Delete-as-reset gives
the delete idiom a second reading on this one surface (reset, not remove) —
accepted because both are "destroy the current value, press twice to
confirm". The six chords become mutable state the help system (ADR-0009)
must read from the registry at speak time, never from this ADR's table.
