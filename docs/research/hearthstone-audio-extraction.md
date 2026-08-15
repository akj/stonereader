---
title: Hearthstone audio in a companion app — legality and extraction pipeline
sources:
  - https://www.blizzard.com/en-us/legal/fba4d00f-c7e4-4883-b8b9-1b4500a402ea/blizzard-end-user-license-agreement
  - https://www.blizzard.com/en-us/legal/dd76b654-f2c4-4aaa-ba49-ca3122de2376/blizzard-video-policy
  - https://www.blizzard.com/en-us/legal/c1ae32ac-7ff9-4ac3-a03b-fc04b8697010/blizzard-legal-faq
  - https://github.com/github/dmca/blob/master/2022/05/2022-05-18-blizzard.md
  - https://us.forums.blizzard.com/en/hearthstone/t/addressing-hearthstone-accessibility/97531
  - https://hearthstonejson.com/
  - https://github.com/K0lb3/UnityPy
fetch_date: 2026-08-14
verified_against: local install, Hearthstone build 36.2.0.248348, Unity 6000.3.11f1
wayfinder_ticket: akj/stonereader#22, akj/stonereader#32
---

# Hearthstone audio in a companion app — legality and extraction pipeline

Can StoneReader play Hearthstone's own audio (card voice lines, event
sounds)? **Yes — extracted at runtime from the user's own install, never
shipped or fetched.** The pipeline below was verified end-to-end against a
live install. Not legal advice.

## Three distribution models

| | 1. Ship assets in the app | 2. Extract at runtime from the user's own install | 3. Fetch from third-party hosts |
|---|---|---|---|
| Blizzard permission | None exists | None explicit; the user's own EULA §1.B license covers their copy | None; hosts can't sublicense |
| Who bears EULA risk | StoneReader | The user, on their own licensed copy | StoneReader |
| Direct adverse precedent | **Yes — 2022-05-18 DMCA for asset hosting** | None in 10+ years of HearthSim/HDT/HSReplay | Scraping-ToS breach |
| DMCA §1201 circumvention | n/a | Low — assets carry no encryption/DRM | n/a |
| Coverage | Full but gigabytes | **Full: 61,314 clips, all locales** | Small fraction |
| Verdict | **Don't** | **Recommended** | **Avoid** |

## Legal findings

1. **EULA (rev. 2024-03-21)**: §1.C.i forbids licensees to "Copy or reproduce
   … reverse engineer … or create derivative works based on or related to the
   Platform"; §2.A enumerates "All sounds, musical compositions, recordings,
   and sound effects" as Blizzard-owned. No fan/non-commercial carve-out
   exists. §1.C binds the *end user* running the extraction, not the shipper
   of code that performs it — the distinction separating model 2 from model 1.
2. **There is no Blizzard fan-content policy** covering software. The Video
   Policy licenses game audio **only in video productions**; the Legal FAQ's
   personal-use license is expressly **non-transferable** (licenses the user,
   never a redistributor) and requires retaining copyright notices. The
   official Hearthstone developer API serves no audio.
3. **Enforcement history draws the line at redistribution, not extraction.**
   Tolerated without incident since ~2014: HearthstoneJSON publicly
   redistributes extracted card data *and art*; HSReplay.net runs a paid
   business on it; Hearthstone Deck Tracker reads the client for years.
   Enforced: bots/cheats (Bossland, ~$8.6M), DRM circumvention (D2ROffline,
   §1201), and — the sharpest datapoint — a **2022-05-18 DMCA against GitHub
   repos purely for hosting extracted game art**. The enforcement line falls
   almost exactly on the model-1/model-2 boundary.
4. **The accessibility posture is active support, not tolerance.** Blizzard's
   2022 forum statement on HSA: "We've been in constant communication with
   GuideDev … implemented measures to make development of the mod easier …
   We're big fans of their work!" Verified on-disk: the retail client ships a
   Blizzard-authored `Hearthstone\Accessibility\` folder containing
   `hsa_manifest.json` — pinning `hearthstone_version`, an
   `accessibility_version`, a git commit on an `hsa` branch, and the
   `Assembly-CSharp.dll` SHA-256 — plus HSA's 8 Battlegrounds wavs. Blizzard
   engineers per-build support for a client-*patching* accessibility mod; a
   read-only accessibility companion is a far milder posture.
   **accessibility@blizzard.com** (opened in that post) is a realistic channel
   for an explicit blessing.

## Technical findings (verified on build 36.2.0.248348)

5. **Layout**: `Hearthstone\Data\Win\` holds 4,866 `.unity3d` bundles (~12 GB);
   the sound corpus is 576 per-asset addressable bundles (~2.9 GB) named
   `playsound_base_enus-*`, `soundotherminion_*`, `soundspell_*`,
   `soundmission_*`, `musicexpansion_*`, etc. The monolithic `sounds0.unity3d`
   described by older community guides **no longer exists**. Voice lines are
   locale-tagged (`_enus`). Engine is **Unity 6000.3.11f1** (read from
   `Hearthstone_Data/globalgamemanagers`).
6. **Format & tooling**: audio are standard Unity AudioClips with FSB5 (FMOD)
   Vorbis payloads — not Wwise, no encryption. Working Python stack:
   **UnityPy** (1.25.3, maintained) + **`fsb5`** for decode; both plain pip
   installs. Gotcha: **Blizzard strips the Unity version string from bundle
   headers** — set `UnityPy.config.FALLBACK_UNITY_VERSION` (detect the real
   version from `globalgamemanagers` at runtime) or UnityPy fails with
   `UnityVersionFallbackError`. This is why AssetRipper and the abandoned
   HearthSim tools (`unitypack`/`python-fsb5`, dead since 2021) choke.
   Verified end-to-end: bundle → AudioClip → FSB5 → playable RIFF/WAV in
   milliseconds.
7. **There is no mapping problem.** Clip names *are* the card→audio mapping:
   `VO_<CardID>_<Gender>_<Race>_<Event>_<NN>` (e.g.
   `VO_REV_956_Male_Dwarf_Play_01`), where CardID is exactly the
   HearthstoneJSON/CardDefs id StoneReader's card database already uses. Full
   index across all 576 bundles: **8.1 s, zero errors, 61,314 AudioClips,
   4,564 distinct card ids**; events `Attack` 4,839 · `Death` 4,536 · `Play`
   3,961 · `Trigger` 294 · `Emote` 33. Practical design: index once per game
   patch (cache to JSON), decode individual clips on demand. Non-VO event SFX
   are surveyed in the section below (ticket #32).
8. **Wiki fallback rejected**: hearthstone.wiki.gg serves voice-line wavs at
   stable `Special:FilePath` URLs, but its operator ToS forbids scraping,
   `robots.txt` disallows the endpoints, the CC BY-NC-SA license can't cover
   Blizzard's audio anyway, and coverage is a fraction of the local corpus.

## Non-VO event SFX survey (ticket #32)

Name-only rescan of the full install (no audio decoded), same build. Raw
survey with exhaustive name/bundle lists lives on the `research/sfx-survey`
branch (`docs/research/.sfx-survey-raw.md`).

9. **The sound corpus is bigger than the sound-named bundles.** Scanning all
   4,866 bundles (126 s, zero unreadable) finds **69,959** AudioClips: the 576
   sound-named bundles hold the 61,314 previously indexed; the other 4,290
   bundles contribute 8,645 more — and those hold most of the *generic*
   UI/gameplay SFX (`essential_*_global`, `initial_*_global`). A runtime index
   limited to the sound-named corpus would miss exactly the event clips below.
10. **Non-VO taxonomy** (16,775 clips, eight bundle-family clusters):
    card-specific play Foley (`playsound_*`: `<CardID>_Play`), card-specific
    attack/death Foley (`soundotherminion_*`: `<CardID>_Attack` / `_Death`),
    spell/effect SFX (`soundspell_*`), legendary play stingers
    (`soundlegend_*`), music (`heromusic_*`, `musicexpansion_*`), a 401-clip
    generic UI/gameplay library (`essential_*_global`), a 5,746-clip
    mode/board/skin catch-all (`initial_*_global`), and 97 ambiguous
    mission vocal-or-Foley clips.
11. **Card-id Foley extends the VO mapping.** Thousands of voiceless cards
    still have *card-specific* play/attack/death Foley addressable by the same
    CardID naming scheme as voice lines — one index covers both.
12. **Game-event → SFX from names alone: partial, and sufficient for the
    replay events zone.** Generic base clips are name-identifiable for the
    core events; most live in `essential_base_global-audio-0.unity3d` and
    `initial_base_global-*-audio-*` bundles:

    | Event | Names suffice? | Canonical clips |
    |---|---|---|
    | Turn start | Yes | `ALERT_YourTurn_0v2` |
    | End-turn button | Yes (small family) | `FX_EndTurn_Up` / `_Enemy` / `_Down` |
    | Card draw | Yes | `draw_card_1..3`; opponent `draw_card_and_add_to_hand_opp_1..3` |
    | Card play / drop | Yes | `play_card_from_hand_1..3`; `Minion_Drop_Basic_1..5` |
    | Attack | Yes | `FX_Minion_AttackLaunch` → `FX_Minion_AttackImpact[Mid/Large]`; hero: `Hero_Attack_Generic_Start_01` / `_End_01` |
    | Minion death | Yes | `Minion_Death_01..06` |
    | Damage | Partial | `Shared_Physical_Impact_01/02`; armor-only `Shared_Armor_Damage_1`; no generic health-damage clip |
    | Hero power | **No** | only icon UI (`hero_power_icon_flip_on/off`); activation SFX are hero/skin-specific |
    | Game start / mulligan / coin | Yes | `Mulligan` (+`A/B/C`), `the_coin_card`, `FX_MulliganCoin01_HeroCoinDrop` |
    | Victory / defeat | Yes | `victory_jingle`, `victory_screen_start`; `defeat_jingle`, `defeat_screen_start` |
    | Secret trigger | Yes | `FX_Secret_Trigger` (birth: `FX_Secret_Birth`) |
    | Discover / choice | **No** | card-specific only; no generic cue |
    | Emote wheel | **No** | nearest is `speech_bubble_open/close` |
13. **What names can't give**: hero-power activation, discover/choice, emote
    wheel, and the runtime *mix* — the client layers card/skin-specific
    variants over the base clips via prefab bindings this survey did not
    inspect, and no waveform was auditioned.

**Consequence for ADR-0008**: the Replay Viewer events zone *can* sound the
common voiceless case — a generic base clip per event type, upgraded to
card-specific Foley by CardID where one exists. Hero power, discover, and
emote-wheel events stay silent (or borrow a nearby UI clip) unless a curated
mapping is hand-built later.

## Hardening requirements for the extraction path

- Never cache, bundle, or upload extracted audio off the user's machine.
- Locate the install (registry/`Launcher.db`, user-overridable path) and
  **fail gracefully to no-audio** when absent — never fetch as a fallback.
- Detect the Unity version at runtime rather than hard-pinning.
- Ship prominent "not affiliated with Blizzard Entertainment / assets ©
  Blizzard" notices (the Legal FAQ's notice-retention requirement).
- Stay free and non-commercial — every untouched precedent shares this
  property.
