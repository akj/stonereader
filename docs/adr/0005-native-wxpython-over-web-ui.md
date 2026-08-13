# StoneReader stays a native wxPython app; web and Electron UIs are rejected

## Status

Accepted (locked 2026-08-13 while charting the final-UI-design map, [#17](https://github.com/akj/stonereader/issues/17); recorded by ticket [#27](https://github.com/akj/stonereader/issues/27)).

## Context

While charting the final UI design, the obvious question surfaced: mainstream Hearthstone companions (Firestone) are web-stack apps, and a web or Electron UI would open richer visuals, easier styling, and a larger contributor pool. StoneReader's audience, however, is screen-reader users, and its identity is the HSA keymap — bare single-letter keys (B, G, V, F, C, D, …) that must fire reliably, plus speech that must keep flowing while Hearthstone, not StoneReader, holds focus. The evidence is collected in the [web-vs-native research fact sheet](../research/web-vs-native-platform.md).

## Decision

StoneReader remains a native wxPython desktop app. Speech stays on direct screen-reader APIs (accessible_output2 → NVDA Controller Client/Tolk-style native calls), global hotkeys on native OS registration, and all surfaces on native keyboard-navigable widgets.

## Alternatives considered and rejected

**Browser-based web app.** Rejected on four independent grounds, any one of which is fatal:

- *Keymap collision.* NVDA browse mode binds essentially every HSA letter to quick-nav (B=button, G=graphic, F=form field, C=combo box, D=landmark, …); of the ADR-0003 key set only Y survives. Escaping browse mode requires `role="application"`, which shifts all focus/keyboard responsibility onto the page, is honored inconsistently by JAWS, and can be overridden back by the NVDA user — so bare-letter keys are never guaranteed.
- *No global hotkeys.* The web platform has no API for system-wide shortcuts, so nothing works while Hearthstone has focus — the app's core scenario.
- *Unreliable speech.* aria-live is documented-inconsistent across screen readers and browsers, and NVDA deliberately suppresses live regions in background tabs (nvaccess/nvda#1318) — which alone kills live-game speech from a backgrounded app. Direct speech APIs are native-process-only.
- *Track record.* Neither web-stack tracker (Firestone) nor any Electron precedent offers shipped screen-reader support; blind-community sentiment on Electron apps is consistently negative.

**Electron.** Recovers global hotkeys (`globalShortcut`, though it fails silently on accelerator conflicts) but inherits every browse-mode, `role="application"`, and live-region problem above, plus the documented Electron screen-reader failure record (Atom/VS Code "neither seems usefully accessible" — Leonie Watson; RStudio shipping with Chromium accessibility disabled). All cost, one partial fix.

Prior art seals it: HSA, both Hearthstone Deck Tracker accessibility requests, Arena Tracker's shipped fix, and Radaelli's MTG Arena work all independently converge on the same shape StoneReader already has — a separate, keyboard-navigable, list-based **native** window, not an overlay and not a browser surface.

## Consequences

**Positive.** Bare-letter global keys, reliable direct speech, and native focus semantics are guaranteed by construction; the HSA keymap (ADR-0003/0004) stays implementable exactly as specced.

**Negative.** UI polish is bounded by wxPython's widget set; visual styling and contributor familiarity are worse than a web stack. These costs land on sighted developers, not on the audience the app exists for — the accepted trade.
