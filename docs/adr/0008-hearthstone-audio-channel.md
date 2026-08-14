# Hearthstone audio: runtime extraction from the User's own install

## Status

Accepted (design contract, 2026-08-14). Implementation lands via PRDs opened
against the final UI spec (wayfinder map #17); nothing here ships code by
itself. Decided in ticket #22. Kills the synthetic-earcon channel ADR-0007
anticipated — its optional boundary edge cue is dead; the boundary
title-repeat stands alone.

## Context

Ticket #22 was chartered to design a sound-cue channel on the strength of an
HSA precedent — "discrete cues for card drawn, minion attacked, turn start."
Research falsified that premise: HSA's accessibility layer is speech-only for
standard play, and its entire cue inventory is 8 Battlegrounds wavs from the
2025 community fork (docs/research/hsa-sound-cues.md). With the precedent
gone, no surface on the map needed an earcon vocabulary.

The purpose that survived scrutiny is different: playing **Hearthstone's own
audio** — card voice lines while browsing, a soundscape while stepping
replays. That matters exactly where the game itself is silent: the Replay
Viewer is a soundless retelling of a game, and card flavor is largely audio a
blind User cannot otherwise browse. During a Live game the real client is
already producing its audio, so StoneReader adds nothing there.

Legality and feasibility were researched and verified end-to-end against a
live install (docs/research/hearthstone-audio-extraction.md): the audio is
unencrypted Unity AudioClips whose names carry the card-id→event mapping
(`VO_<CardID>_…_<Event>_<NN>`; 61,314 clips, 4,564 cards, indexable in ~8 s);
Blizzard's enforcement history strikes at asset *redistribution* (a 2022 DMCA
for hosting extracted art) while a decade of runtime-extraction tooling
(HearthstoneJSON, HSReplay, Deck Tracker) stands untouched — and Blizzard
actively ships per-build support manifests for the client-patching HSA mod.

## Decision

### The channel and its sourcing

**Game audio** is StoneReader's second output channel beside speech:
Hearthstone's own audio assets, **extracted at runtime from the User's own
Hearthstone installation**. Bright lines:

- StoneReader never ships Blizzard audio in its distribution.
- StoneReader never fetches audio from third-party hosts, including as a
  fallback.
- Extracted audio never leaves the User's machine (no caching or upload
  elsewhere).
- No install found → the channel is absent and says so; the app is fully
  functional without it.
- The Unity version is detected from the install at runtime (bundle headers
  are version-stripped), not hard-pinned.
- The app stays free and non-commercial and carries "not affiliated with
  Blizzard Entertainment / assets © Blizzard" notices.

### The channel contract (vs speech)

1. Game audio never delays or preempts speech. The speech lanes (ADR-0007)
   are untouched; audio mixes underneath them.
2. Starting any new sound replaces the one playing — at most one game-audio
   clip plays at a time.
3. Surface transitions stop game audio. Escape/Backspace therefore silence it
   as a side effect of back, with no change to their one meaning (ADR-0004).
4. A bare Ctrl tap stops game audio without moving — the same
   silence-the-speech gesture screen-reader users already hold for NVDA/JAWS,
   colliding with no command (a lone modifier is never a key).
5. Nothing else stops it: ordinary navigation (arrowing detail lines,
   exploring zones) lets a sound play out.
6. StoneReader owns an app-level volume for game audio, independent of speech
   (speech exits via the screen reader and was never ours to mix).

### Surfaces

- **Live Game: no game audio.** The real client is in the room playing its
  own; doubling it is clutter (the double-cue hazard,
  docs/research/hsa-sound-cues.md).
- **Replay Viewer events zone: auto-play on event-stepping.** Landing on an
  event plays that event's sound (its card's Play/Attack/Death line; non-VO
  event SFX pending the bundle survey ticket), replacing any playing sound so
  the new one is heard, mixed under the event's narration. Always on, with a
  Settings kill-switch. Turn-stepping is speech-only — the events zone is
  where you go to listen.
- **The listen key: universal L.** On any card under the cursor (Cards, Deck
  Contents, replay zones), L drills into a **Sounds** vertical menu — options
  labeled by event ("Play", "Attack", "Death", "Trigger 2", …), standard
  entry utterance, **Enter plays** the focused sound, Escape backs out. L is
  unbound in-game and in HSA's Collection Manager
  (docs/research/hsa-commands-reference.md), so no muscle-memory collision.
  On a card with no sounds, L announces "{title}: no sounds" without pushing;
  with no install present, L announces that game audio is unavailable — no
  universal key dies silently (ADR-0004).

### Settings handoff (ticket #25)

Game-audio volume; replay auto-play kill-switch; Hearthstone install path
(auto-detected, overridable) beside the existing log-path plumbing.

## Alternatives considered and rejected

- **Synthetic earcon channel** (the ticket's original charter). Rejected: its
  HSA precedent was falsified, and no current surface has the two problems
  earcons genuinely solve (per-item predicates under rapid browsing, async
  external events). HSA's Battlegrounds cues remain the precedent if
  Battlegrounds tools ever graduate from fog.
- **Shipping audio assets in the app.** Rejected: no Blizzard policy permits
  it, the Legal FAQ's license is expressly non-transferable, and asset
  hosting is the one adjacent behavior Blizzard has actually DMCA'd.
- **Fetching from third-party hosts (wiki).** Rejected: scraping-ToS breach,
  a fraction of the coverage, and it moves redistribution risk onto
  StoneReader.
- **Auto-fire during all replay navigation** (sounds as side effects of every
  step). Rejected in favor of events-zone-only auto-play: turn-stepping stays
  crisp and speech-first.
- **Play-on-focus in the Sounds menu.** Rejected: menus act on Enter
  everywhere else, and rapid arrowing would stutter through replaced clips.
- **A dedicated Escape stop.** Rejected: Escape is centrally bound to back
  (ADR-0004); a conditional consume-first-press would give a universal key
  two meanings. Transitions-stop plus bare-Ctrl covers the intent.
- **Any-keypress stops audio** (mirroring the Lane-2 drop). Rejected by
  design intent: clips are short and deliberate; traversing card text while a
  voice line finishes is the normal case, not an interruption.

## Consequences

**Positive.** A designed second channel with testable invariants (never
delays speech; one clip at a time; transitions silence it). Replays gain the
game's own voices; the collection becomes browsable flavor. The sourcing
posture matches the ecosystem's only untouched pattern and the strongest
accessibility precedent Blizzard has. The extraction pipeline is verified,
small (two pip deps), and index-once-per-patch cheap.

**Negative.** A new module seam — extraction, index cache, an async player,
a bare-Ctrl listener — lands in the module-seams design (ticket #24). L is
claimed app-wide. Settings grows three items. Events with no voice line stay
silent until the SFX survey settles whether the game's punctuation sounds are
extractable. The EULA-gray residue of runtime extraction is accepted and
mitigated (bright lines above); an explicit blessing via
accessibility@blizzard.com is a realistic future de-risk.
