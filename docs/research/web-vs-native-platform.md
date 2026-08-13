# Research fact sheet: web UI vs native for a screen-reader-first Hearthstone companion

Gathered 2026-08-13 while charting the final-UI-design wayfinder map
([#17](https://github.com/akj/stonereader/issues/17)); persisted into the repo by ticket
[#27](https://github.com/akj/stonereader/issues/27). This file is the canonical copy and is
cited by [ADR-0005](../adr/0005-native-wxpython-over-web-ui.md).

Verification: **[V]** verified directly (API/primary doc), **[S]** single secondary source,
**[?]** unverified.

## 1. Firestone

- **Stack [V]:** Angular 19 + NgRx, Nx monorepo, Electron 34 + `@overwolf/ow-electron`; distributed via Overwolf (3.68M downloads, v18.13.11 as of 2026-08-11). Effectively solo-authored (sebastientromp: 14.3k of 14.6k commits). Electron migration off Overwolf is in progress in-repo (`apps/electron-app`, `electron-prep.md`).
- **UI [V]:** 11 transparent Overwolf windows — each major surface has a desktop window plus a separate in-game overlay window. Top-level nav is a 14-way tab set (marked `@deprecated` in-repo); per-tab navigation state objects, no URL router. Manifest hotkeys: Alt+C, Alt+B, held Tab — all modifier-based, fire in-game.
- **Replay viewer** is a pure web app (Coliseum, `replays.firestoneapp.com`), now in-monorepo.
- **Features [S]:** deck tracker + overlays (secrets helper, counters, mulligan overlay), constructed stats/meta, deckbuilder, Battlegrounds (hero stats, MMR graphs, battle simulator, odds overlay), arena (run history, tier lists, draft-pick stats), Tavern Brawl, Mercenaries, collection/pack tracking + pity timers, profile, achievements, streams, Twitch extension.
- **Accessibility [V]:** `aria-live` 0 hits, `role="application"` 0 hits; `aria-label` ~31 hits, nearly all window chrome. The only a11y issue (#1012 "make tracker accessible") was self-filed by the maintainer 2025-11-04; no movement.

## 2. Hearthstone Deck Tracker (HearthSim)

- **Stack [V]:** C#/WPF/.NET Framework, 100% native, reads Power.log. 4.9k stars, actively maintained (last push 2026-08-12).
- **UI [V]:** 229 XAML files. Main window with native WPF menus; flyouts (deck editor, export, history, screenshot, **Options = 26 settings panes** across Tracker/Overlay/HSReplay/Streaming); ~7 separate windows (overlay, player, opponent, timer, stats, BG session, capturable overlay). Cards/timer can display as standalone windows instead of the overlay — a native-window escape hatch already exists.
- **Global hotkeys [V]:** `user32.dll RegisterHotKey` + `WM_HOTKEY`; ~17 predefined actions, user-rebindable in Options.
- **Plugins [V]:** `IPlugin` (.dll drop-in), `GameEvents.OnGameStart/OnTurnStart` etc., can inject a `MenuItem` into the main menu.
- **Accessibility [V]:** `AutomationProperties` — 0 hits repo-wide. Issue #4371 ("screen reader accessibility for deck tracking", 2021-12-14): open, untouched ~4.7 years; asked for a keyboard-navigable standard list window separate from the overlay, plus textual replay logs. #4534 (2024) closed as duplicate of #4371; maintainer was receptive, nothing shipped.

**Net: neither tracker has any shipped screen-reader support.**

## 3. Web vs native for screen-reader users (the platform evidence)

- **NVDA browse-mode quick-nav collision [V, official keyCommands]:** essentially the ENTIRE HSA keymap collides with browse-mode single-letter navigation — B=button, G=graphic, V=visited link, F=form field, C=combo box, D=landmark, S=separator, E=edit field, I=list item, R=radio, T=table, A=annotation, W=spelling error, O=embedded object, P=paragraph, N=non-linked text, 1–9=heading levels. Of the ADR-0003 key set, only Y survives. NVDA+shift+space (single-letter nav off) is a *user* action a page cannot trigger.
- **`role="application"` [V]:** MDN — author becomes "completely responsible for handling any and all keyboard input, focus management"; NVDA users can override back into browse mode (so keys are never guaranteed); JAWS honors it inconsistently (open FreedomScientific standards-support #640); content inside becomes unreachable to semantic navigation. No W3C APG practice page exists for it.
- **Global hotkeys [V]:** No web API, period. Keyboard Lock requires a focused fullscreen document. Chrome extension `chrome.commands` global commands are restricted to Ctrl+Shift+0-9. Native `RegisterHotKey` is system-wide (requires a modifier). Electron `globalShortcut` works but silently fails if another app owns the accelerator.
- **Speech [V]:** aria-live is documented-unreliable across NVDA/JAWS/browsers (TetraLogical, Scott O'Hara, Adrian Roselli Jan-2026 test matrix: only consistent behavior is "hidden regions do not announce"). NVDA deliberately suppresses live regions in background tabs (nvaccess/nvda#1318 — "we definitely shouldn't be reading live regions in the background"), which alone kills live-game speech from a backgrounded web app. Direct APIs (NVDA Controller Client, Tolk, accessible_output2 — what StoneReader uses; UIA notifications) are native-process-only.
- **Sentiment [V where quoted]:** Leonie Watson: Atom and VS Code "neither seems usefully accessible" (2018); RStudio shipped Electron with Chromium a11y forced off ("That is unacceptable" — blind user, rstudio#12321); WebAIM Survey 10: misbehaving interactive elements are the #2 most-problematic thing on the web after CAPTCHA.

## 4. Prior art

- **HSA [V, hearthstoneaccess.com]:** alive (changelog 2026-08-05), community-maintained since Guide Dev's 2022 burnout sunset; a patched `Assembly-CSharp.dll`, not a mod loader — breaks every Hearthstone patch; Blizzard-blessed but unofficial. Speech via **Tolk**, SAPI fallback, developed against NVDA; also ships **non-speech sound cues** and recorded tutorial narration. **HSA has no replay functionality at all** — StoneReader fills an empty niche.
- **HSA interaction model [V]:** vertical menus = Up/Down + Enter + **Backspace back**; horizontal lists = **Left/Right between items, Up/Down through the lines of the current item** (orthogonal axes); Tab/Shift+Tab jumps between groups (collection classes); single-letter screen shortcuts from the main menu (R/A/M/B/T/C/O/J/S); **F1 = context help everywhere**; PageUp/PageDown paging; bare key = your side, **Shift+key = opponent side** (or skip-confirmation); collection: Ctrl+F typed search, 0–7 mana filter; **no tabs anywhere**.
- **Arena Tracker [V]** — the one tracker that shipped screen-reader support (issue #146, closed completed 2023-11-10, C++/Qt): blind user asked for an arrow-navigable list; maintainer could not build that in Qt and shipped tab-stop labels instead; user satisfied. Follow-up breakage came from a silent download step with no accessible progress.
- **Lucas Radaelli, "Making MTG Arena Accessible To The Blind":** model everything as lists; shortcuts jump between lists and within them; TTS on focus with detail-on-demand; keep a reviewable message history because gameplay outpaces speech.
- **Convergence:** Radaelli's list-of-lists, the HSA model, both HSDT accessibility requests, and Arena Tracker's request all independently land on the same shape: **a separate, keyboard-navigable, list-based native window — explicitly not an overlay.** That is what StoneReader already is.

## Explicitly unverified

Firestone standalone-installer details (JS-rendered page); HSDT's practical NVDA behavior (only the 0-hit code search is verified); Overwolf overlay UIA exposure; any Blizzard native blind-accessibility shipping (searched 2023–2026, none found); HSA community size; r/Blind and forum.audiogames.net sentiment (both unreachable — blocked/403); no quantitative aria-live latency benchmark exists.
