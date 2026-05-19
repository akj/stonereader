# Replay and Card Browser navigation mirror Hearthstone Access

## Status

Proposed. Lands incrementally: Card Library/Browser first (low-risk, independent of PRD #7); Replay second, blocking on a PRD #7 revision that incorporates the keymap and expanded zone inventory documented below.

## Context

StoneReader's audience is screen-reader users on Windows, most of whom already use **Hearthstone Access** (HSA) — the third-party mod that wraps Hearthstone itself in a keyboard-only interface. HSA defines a deeply established keymap that its users have internalised: B for your board, G for opponent's board, V for your hero, F for opponent's hero, C for your hand, S for secrets, W for weapon, and so on.

Every divergence between HSA and StoneReader's keyboard surfaces is friction for that audience — they reach for B and get nothing.

HSA's keymap is internally inconsistent. Friendly/opponent pairs use different patterns: boards (B vs G) and heroes (V vs F) use distinct letters, while weapons (W / Shift+W), secrets (S / Shift+S), hand (C / Shift+C), deck (D / Shift+D), and mana (A / Shift+A) use a letter + Shift modifier. There is no governing rule; the pattern is accreted history. Numbers also have surface-dependent meaning in HSA: in-game they jump to items 1–10 in the current list, in My Collection they filter by mana cost. PRD #7's original draft had number keys switching **Replay** zones, which would have given numbers a third meaning unique to StoneReader.

## Decision

The **Replay** viewer and Card Library/Browser mirror HSA's exact key conventions, including the inconsistencies. Faithfulness wins over internal consistency.

Specific rules that follow:

- **Letter keys** switch to or announce specific game-state zones. Friendly/opponent pairs preserve HSA's case-by-case pattern: B/G for boards, V/F for heroes, Shift modifier for weapons/secrets/hand/deck/mana.
- **Numbers** do positional jumps in Replay (jump to item 1–10 in the current zone) and mana-cost toggles in Card Browser (0–9, single-select with re-press to clear). Numbers never switch zones.
- **Speak-only commands** in HSA (A, Shift+A, Shift+D, R, Shift+R) remain speak-only in StoneReader and do not change the active zone — they are drive-by queries.
- **Count-only HSA commands where StoneReader has richer data** (D for your deck, Shift+C for opponent hand) are extended to navigable zones in **Replay**. The letter and Shift convention is preserved.
- **Zones with no HSA equivalent** (events, played-this-game, drawn-this-game) get keys from HSA's "free" set — keys HSA uses for in-game actions that don't apply in Replay or Card Browser: Y for events, P / Shift+P for played, N / Shift+N for drawn.

Canonical reference: <https://hearthstoneaccess.com/commands.html>

## Alternatives considered and rejected

**A single consistent friendly/opponent rule** (e.g. all opponent = Shift+letter). Rejected because the cost of relearning falls entirely on the audience StoneReader exists for. HSA's inconsistencies are real but they are *familiar*.

**Number keys switch Replay zones** (PRD #7's original draft). Rejected because HSA already binds numbers to two surface-specific meanings (positional jump in-game, mana filter in collection); adding a third meaning in StoneReader loses the muscle-memory advantage and introduces inconsistency *within StoneReader* across surfaces.

**Singleton "look at" commands as 0-or-1-element list zones** (uniform with other zones). Rejected for the heroes/weapons/etc. case in favour of "list zones with one item, browsable by detail-line nav" — and rejected for the pure facts (A/Shift+A/Shift+D/R/Shift+R), which stay speak-only so HSA users get the drive-by query behaviour they already know.

## Consequences

**Positive.** HSA users get instant muscle-memory transfer into StoneReader's keyboard-driven surfaces. The keymap is documentable by pointing at HSA's commands page; a one-screen help reference inside StoneReader can defer to it.

**Negative.** A reader without HSA context sees an apparently arbitrary keymap — the B/G/V/F asymmetry and numbers-mean-different-things-in-different-surfaces look like bugs until you know the source. This ADR is the explanation. Future StoneReader surfaces (e.g. arena drafting, Battlegrounds review) inherit the obligation to check HSA's vocabulary before picking keys.
