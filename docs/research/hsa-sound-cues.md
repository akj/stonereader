---
title: HSA non-speech sound cues — what actually ships
sources:
  - https://blindgamingclub.com/hearthstone/
  - https://github.com/HearthstoneAccess/HearthstoneAccess/blob/master/diff.patch
  - https://github.com/antonshusharin/DevTools/tree/master/Sounds
  - https://hearthstoneaccess.com/changelog.html
  - https://hearthstoneaccess.com/commands.html
fetch_date: 2026-08-14
wayfinder_ticket: akj/stonereader#22
---

# HSA non-speech sound cues — what actually ships

Research commissioned by ticket #22, whose original premise was "HSA precedent:
discrete cues for card drawn, minion attacked, turn start." **That premise is
false.** This document records what HSA actually does, because the finding
killed StoneReader's planned earcon channel and re-pointed the ticket.

## Findings

1. **The claimed cue list originates from an uncited fan page, not HSA.**
   blindgamingclub.com/hearthstone states verbatim that the mod provides
   "distinct sound cues for important game events, such as a card being drawn,
   a minion being attacked, or a new turn beginning" — no author, no date, no
   citations. Search-engine AI summaries regurgitate this sentence. No official
   HSA page makes the claim.

2. **HSA's accessibility layer is speech-only for standard play.** The
   published mod source (the 2021 `diff.patch` in the HearthstoneAccess GitHub
   org) hooks the exact code paths where Hearthstone already plays its own
   native audio and adds a speech call beside them. Turn start: the game's
   `ALERT_YourTurn_0v2.prefab` line is unchanged; HSA adds
   `AccessibleGameplay.Get().OnTurnStart()` → a string list sent to the screen
   reader. The four card-draw hooks (`OnDrawCard`, `OnRevealDrawnOpponentCard`,
   `OnDrawUnknownOpponentCard`, `OnCardToDeck`) are **empty stubs**. Minion
   attack goes to a speech describer. A sweep of every added line for
   `LoadAndPlay|PlayClip|PlayOneShot|AudioClip|.wav` finds no cue playback
   anywhere in the accessibility layer — the only added `PlaySound` calls are
   tutorial voice-over narration. All output funnels through
   `AccessibilityMgr.Output()` → Tolk (SAPI fallback).
   *Currency caveat*: that diff is the 2021 first release; the current
   community fork's source is deliberately unpublished. Finding 3 is the known
   delta.

3. **The only cues HSA ships are 8 Battlegrounds .wav files (2025, community
   fork).** The fork's build repo (`antonshusharin/DevTools`, `Sounds/`
   directory) holds the complete mod-shipped audio inventory: four
   `BATTLEGROUNDS_HOVER_*` cues flagging "this tavern minion completes a
   pair/triple (yours or your teammate's)" while arrow-keying Bob's tavern,
   and four `BATTLEGROUNDS_DUOS_PING_*` cues mapping the Duos ping wheel.
   Changelog 2025-07-01 corroborates ("sound design by Superblindman and
   CritterPup").

4. **No cue toggles, volume control, or verbosity levels exist in HSA** — the
   commands page and changelog have zero hits for sound/volume/verbosity
   controls beyond making Blizzard's own sound-options menu keyboard-navigable.
   This absence is architectural, not a design verdict: HSA inherited
   Blizzard's mixer for free and its speech exits via Tolk outside the mixer,
   so it never needed its own audio controls.

## What transfers to StoneReader

- **There is no HSA event-cue list to port.** Any StoneReader cue for
  draw/attack/turn-start would be a novel design, not a precedent match.
- **The transferable principle is HSA's selection criterion, not its
  inventory**: sound went exactly where speech is the wrong instrument —
  per-item state predicates during rapid keyboard browsing (too verbose to
  speak on every arrow press) and async events originating outside the user's
  own action (too intrusive to interrupt with). Everywhere else, speech.
- **The double-cue hazard**: HSA never had a cue-design problem for common
  events because Blizzard's well-produced audio already plays at the right
  moment. StoneReader runs *beside* that same audio during a Live game — a
  StoneReader draw cue would land on top of the game's own draw sound,
  uncoordinated. Events the game already sonifies are the *worst* cue
  candidates.

## Outcome for ticket #22

The planned synthetic-earcon channel was killed (2026-08-14). ADR-0007's
optional boundary edge cue dies with it; the boundary title-repeat stands
alone. The ticket re-pointed at Hearthstone-audio playback — see
[hearthstone-audio-extraction.md](hearthstone-audio-extraction.md).
