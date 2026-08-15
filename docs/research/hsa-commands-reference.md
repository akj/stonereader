---
title: HSA command reference (canonical transcription)
source: https://hearthstoneaccess.com/commands.html
fetch_date: 2026-08-13
hsa_changelog_date: 2026-08-05
hsa_game_version: 36.2.0.248348
wayfinder_ticket: akj/stonereader#26
---

# Hearthstone Access keyboard commands — canonical transcription

This is a faithful, complete transcription of every command listed on
[hearthstoneaccess.com/commands.html](https://hearthstoneaccess.com/commands.html)
as fetched 2026-08-13. It is organized by surface, following the page's own
section structure. Key names, capitalization, and Shift/Ctrl notation are
preserved exactly as written on the source page — including its inconsistencies
(e.g. some Shift-variants are written `Shift+x`, others `Shift + Enter`; some
opponent-side keys are written as a capital letter alone, e.g. `I`/`K`/`W`/`Q`
in Battlegrounds, rather than `Shift+i` etc.). Where the source page itself
contains an apparent typo or malformed fragment, it is transcribed verbatim
with a `[sic]` note rather than silently corrected.

This document is the citable reference for StoneReader keymap design; cite it
instead of the live page, which may change.

## Global (available everywhere)

| Key | Action | Notes |
|---|---|---|
| Escape | Open game menu | |
| F1 | Get help for current screen or prompt | Contextual help |
| F4 | Open social menu | |
| F8 | Toggle Accessibility | Allows game to be controlled with mouse when off, or keyboard commands when on |
| F14 | Force Accessibility off | |
| F15 | Force Accessibility on | |
| F11 | Decrease game speed in games against AI | So opponents play slower |
| F12 | Increase game speed in games against AI | So opponents play faster |

## Menus & non-game screens

### Vertical menu navigation

| Key | Action | Notes |
|---|---|---|
| UpArrow | Read previous option | |
| DownArrow | Read next option | |
| Enter | Confirm option | |
| Backspace | Go back | |
| Shift+UpArrow | Reread current option | |
| Home | Read first option | |
| End | Read last option | |

### Main menu shortcut keys

Jumps to and activates the corresponding option.

| Key | Action | Notes |
|---|---|---|
| R | Play Ranked | |
| A | Play Casual | |
| M | Modes | |
| B | Battlegrounds | |
| T | Tavern Brawl | |
| C | My Collection | |
| O | Open Packs | |
| J | Journal | |
| S | Shop | |

### Horizontal lists of items (e.g. cards, hero choices)

These commands also apply during gameplay wherever a horizontal list of items
is presented (per the page's own note under "Playing the Game").

| Key | Action | Notes |
|---|---|---|
| RightArrow | Read next item | |
| LeftArrow | Read previous item | |
| Home | Read first item | |
| End | Read last item | |
| DownArrow | Read next line of current item | |
| UpArrow | Read previous line of current item | |
| Shift+DownArrow | Read from current to last line of item | |
| Shift+UpArrow | Repeat current line of item | |

## In-game (constructed/"Playing the Game")

The horizontal-list commands above also work during gameplay.

| Key | Action | Notes |
|---|---|---|
| Tab | Read next valid play | |
| Shift+Tab | Read previous valid play | |
| 1–0 (number row) | Jump to the first through tenth item in a list | 1–0 covers 10 positions |
| Enter | Play card, attack with your minion, or select target | |
| Backspace | Cancel current action | |
| e | End turn | |
| Shift+e | End turn without asking for confirmation | Only if more valid plays exist |
| a | See how much mana you have (and corpses if relevant) | |
| Shift+a | See how much mana your opponent has (and corpses if relevant) | |
| c | Look at your hand | |
| Shift+c | Count the cards in your opponent's hand | |
| b | Look at your minions | Your board |
| g | Look at your opponent's minions | Opponent's board |
| v | Look at your Hero | |
| f | Look at your opponent's Hero | |
| Shift+f | Send all your minions to attack your opponent's Hero | May need to repeat if not all minions attack |
| Ctrl+F | Make your currently selected minion attack the opponent's hero | |
| r | Look at your Hero Power | |
| Shift+r | Look at your opponent's Hero Power | |
| w | Look at your weapon | |
| Shift+w | Look at your opponent's weapon | |
| s | Look at your secrets | |
| Shift+s | Look at your opponent's secrets | |
| o | Read any anomalies affecting the current game | |
| d | Count the cards in your deck | |
| Shift+d | Count the cards in your opponent's deck | |
| i | Get more information about a focused card's Keywords | e.g. Battlecry, Taunt |
| k | Read base attack, health and any enchantments affecting a focused minion | |
| t | Trade or forge a card if possible | |
| y | Open the play history log | |
| Space | Access in-game emotes when selecting your Hero, or squelch your opponent's hero | |
| PageDown | Jump to related card lines | When reading a card with a related card, e.g. questlines or colossal cards |
| PageUp | Jump to original card lines | When reading a card with a related card, e.g. questlines or colossal cards |

## Collection Manager

The collection managers in both the Main Menu and Battlegrounds menu open to a
vertical menu where you can choose to browse your collection, and (in the
main collection) manage decks and craft cards. While browsing collection
items (cards, hero skins, etc.), the horizontal-list commands apply; the
following are also available while browsing items:

| Key | Action | Notes |
|---|---|---|
| PageDown | Scroll to next page | |
| PageUp | Scroll to previous page | |
| Tab | Jump to next class if applicable | |
| Shift+Tab | Jump to previous class if applicable | |
| Home | Read first card in page | |
| End | Read last card in page | |
| Ctrl+F | Search for an item | Opens a field to type text, then Enter to search |
| Enter | Select item for more options | |
| 0–7 (number row) | Filter cards by mana cost | Source page states **0–7**, not 0–9 |

### Deck editing

| Key | Action | Notes |
|---|---|---|
| Shift+Enter | Jump to crafting screen for a missing card | Source page writes this as "Shift + Enter" |
| C | Jump to add cards screen | |
| d | Jump to list of current cards in deck | |
| Space | Manage sideboard for E.T.C., Band Manager | Only when focused on it in the list of current cards in the deck |

## Battlegrounds

Horizontal-list commands are used to read cards and other items in
Battlegrounds. The page uses bare capital letters (rather than `Shift+x`
notation) for several opponent/no-confirmation variants in this section —
transcribed exactly as written.

| Key | Action | Notes |
|---|---|---|
| g | Read minions for sale | |
| c | Read hand | |
| a | Read gold | |
| I | Get information on card keywords | Written as bare capital `I` on source page |
| K | List enchantments on current card | Written as bare capital `K` on source page |
| t | Read tavern tier and Bartender | |
| u | Upgrade tavern | Reads cost and requires confirmation; press again to confirm |
| Shift+u | Upgrade tavern without confirmation | |
| f | Freeze/unfreeze tavern | Asks for confirmation |
| Shift+f | Freeze/unfreeze tavern without confirmation | |
| r | Refresh tavern | Reads cost if any and requires confirmation |
| Shift+r | Refresh tavern without confirmation | |
| p | Read Hero Power | |
| Shift+P | Read opponent's hero power during combat phase | Written as bare capital `P` on source page |
| d | Read buddy meter and Hero Buddy card | Source text: "d enter to purchase)" — appears to be missing an opening parenthesis/word on the live page; transcribed verbatim `[sic]`. Likely intends "(Space or Enter to purchase)" |
| Enter | Buy/sell minion | Requires confirmation |
| Space | Select minion to reorder | |
| LeftArrow, RightArrow, Home, End, number keys | Reorder selected minion | |
| m | Read my stats on leaderboard | Backspace to stop reading leaderboard |
| Shift+m | Quickly read my stats on leaderboard without losing focus | |
| n | Read next opponent's stats on leaderboard | Backspace to stop reading leaderboard |
| Shift+n | Quickly read next opponent's stats on leaderboard without losing focus | |
| l | Read leaderboard from top | Backspace to stop reading |
| o | Read minion families/races in current game, and anomalies if present | Also works during Hero selection |
| e | Read number of seconds left during Recruit Phase | |
| s | Read secrets or quests | |
| Shift+S | Read opponent's secrets or quests during combat phase | Written as bare capital `S` on source page |
| W | Read quest reward if applicable | Enter to activate; written as bare capital `W` on source page |
| Shift+W | Read opponent's quest reward during combat phase if applicable | |
| Q | Read your trinkets if applicable | Written as bare capital `Q` on source page |
| Shift+Q | Read opponent's trinkets if applicable | |

Not on the commands page but present in the site's changelog (see
"Out-of-scope notes" below) as of the 2026-08-05 entry: `J` / `Shift+J` /
double-press `J` to buy a dark-gift minion, and `Ctrl+Space` to activate a
board minion's ability. These postdate or were simply never folded into the
commands.html transcription and are flagged here for awareness only — they
are not part of the "faithful transcription of commands.html" scope of this
document.

## Interaction model

Structural conventions that recur across surfaces, per the source page:

- **Vertical menus** (main menu, most non-game screens): Up/Down move between
  options one at a time; Enter confirms the focused option; Backspace goes
  back a level; Shift+Up rereads the current option without moving; Home/End
  jump to the first/last option.
- **Horizontal lists** (cards, hero choices, and — per the page's explicit
  note — also usable mid-game): Left/Right move between items; Up/Down move
  between the *lines* of text within the currently-focused item (not between
  items); Shift+Down reads from the current line to the end of the item;
  Shift+Up repeats the current line; Home/End jump to the first/last item.
- **Tab / Shift+Tab as group jumps**: in-game, Tab/Shift+Tab step through
  valid plays; in the Collection Manager, Tab/Shift+Tab jump to the
  next/previous class tab.
- **PageUp/PageDown as paging**: in Collection, they page through browse
  results; in-game, they jump between a card's "original" and "related" card
  lines (questlines, colossal cards).
- **Bare key = your side; Shift+key = opponent's side, or skip-confirmation
  on a destructive/stateful action.** This is the dominant pattern in-game
  (b/g minions, v/f heroes, c/Shift+c hand, d/Shift+d deck, r/Shift+r hero
  power, w/Shift+w weapon, s/Shift+s secrets, a/Shift+a mana) and in
  Battlegrounds (m/n self/next-opponent leaderboard reads, s/Shift+S
  secrets/quests, W/Shift+W quest reward, Q/Shift+Q trinkets). The pattern is
  *not* uniform, though: some pairs use genuinely distinct letters instead of
  a Shift pair (b/g for boards, v/f for heroes), and some Shift variants mean
  "skip confirmation" rather than "opponent" (Shift+e end turn without
  confirming, Shift+u/Shift+f/Shift+r in Battlegrounds skip the
  upgrade/freeze/refresh confirmation prompt). There is no single governing
  rule — see ADR-0003 for how StoneReader treats this.
- **F1** is the universal contextual-help key, available on every screen and
  prompt.
- **1–0 on the number row** do positional jumps in-game (jump straight to the
  1st through 10th item in the current list of valid plays/targets).
- **0–7 on the number row** filter the Collection Manager's card browser by
  mana cost. Note this range is 0–7, not 0–9 — Hearthstone's own mana-cost
  buckets top out at "7 or more."

## Free keys

Letter keys (and number-key semantics) that HSA's commands.html does **not**
bind on a given surface. These are candidates StoneReader may claim for zones
that have no HSA equivalent — cross-checked against ADR-0003's existing picks.

### In-game (constructed) — the surface Replay/Card Browser mirror

Letters bound in-game (`Playing the Game` section): a, b, c, d, e, f, g, i, k,
o, r, s, t, v, w, y (16 letters; Shift-variants of these count as "bound," not
free, since the base letter is in use).

**Free:** h, j, l, m, n, p, q, u, x, z

ADR-0003 claims Y for events, P/Shift+P for played, and N/Shift+N for drawn
as HSA's "free" set for Replay's zones with no HSA equivalent.

- **P and N check out** — neither is bound anywhere in the in-game section.
- **Y does not check out.** `y` is bound on the live page: "Open the play
  history log." ADR-0003's premise that Y is free is **incorrect** as of this
  fetch — see Finding 1 below. (It may be a reasonable pick anyway on
  semantic grounds — "play history log" and StoneReader's proposed "events"
  zone are conceptually adjacent — but it is not actually an unclaimed key.)

### Battlegrounds

Letters bound in Battlegrounds: a, c, d, e, f, g, i, k, l, m, n, o, p, q, r,
s, t, u, w (19 letters, case-insensitive).

**Free:** b, h, j, v, x, y, z

(StoneReader has no Battlegrounds surface yet; listed for forward reference
per ADR-0003's closing note that future surfaces inherit the obligation to
check HSA's vocabulary before picking keys.)

### Collection Manager / Deck editing

Letters bound: c (jump to add-cards screen), d (jump to list of current deck
cards). Everything else is free, including all of e/f/g/h/i/j/k/l/m/n/o/p/q/
r/s/t/u/v/w/x/y/z/a/b.

Number-key semantics already claimed on this surface: 0–7 = mana-cost filter.
8 and 9 are not bound to anything by HSA here (the mana filter tops out at 7).

### Menus (main menu shortcuts)

Letters bound as main-menu jump shortcuts: R, A, M, B, T, C, O, J, S (9
letters). These are menu-specific jump keys, not really "free" elsewhere —
listed for completeness since they are the only letter bindings outside
in-game/Battlegrounds/Collection.

## Findings relevant to StoneReader keymap design

1. **ADR-0003's "Y is free" claim is wrong.** `y` is bound in-game to "Open
   the play history log" on the current commands.html. ADR-0003 assigns Y to
   StoneReader's Replay "events" zone on the premise that HSA doesn't use it.
   This should be revisited: either confirm Y was free at some earlier
   snapshot of the page and HSA added the binding since, or correct the ADR.
   The semantic overlap (play history ≈ events) may still make Y a reasonable
   choice, but the ADR's stated rationale ("free key") no longer holds.
2. **Collection Manager's mana-cost filter is 0–7, not 0–9.** ADR-0003
   describes Card Browser's number-key behavior as "0–9, single-select with
   re-press to clear." HSA's own range is 0–7 (matching Hearthstone's "7 or
   more" mana bucket). If StoneReader's Card Browser needs 8/9 buckets, those
   two digits are genuinely free (HSA doesn't use them for anything else on
   this surface either), but the ADR should be precise about which part of
   the 0–9 range is "mirroring HSA" (0–7) versus "StoneReader going further
   than HSA" (8–9).
3. **The friendly/opponent key pattern has a third shape, not just two.**
   ADR-0003 already notes B/G and V/F use distinct letters while others use
   Shift pairs. This transcription adds detail: several Shift-variants in
   Battlegrounds and in-game aren't "opponent" at all — they mean "same
   action, skip the confirmation prompt" (Shift+e end turn, Shift+u/Shift+f/
   Shift+r in Battlegrounds). Any StoneReader surface that reuses the
   Shift-modifier convention should keep these two meanings (opponent-side vs
   skip-confirmation) clearly distinct in its own key-binding docs, since HSA
   itself overloads Shift this way.
4. **P and N are confirmed free in-game**, validating ADR-0003's picks for
   Replay's "played" and "drawn" zones without qualification.
5. **HSA's Battlegrounds vocabulary is dense and mostly distinct from the
   in-game vocabulary** (e.g. `d` means "count your deck" in-game but "read
   buddy meter" in Battlegrounds; `t` means "trade/forge" in-game but "read
   tavern tier" in Battlegrounds). If StoneReader ever adds a Battlegrounds
   surface, it cannot simply reuse the in-game letter assignments — HSA
   itself does not, and the free-letter set for Battlegrounds (b, h, j, v, x,
   y, z) is different and smaller than the in-game free set.

## Out-of-scope notes

The site's changelog (https://hearthstoneaccess.com/changelog.html), dated
entries up to 2026-08-05 at fetch time, documents newer mechanics
(dark-gift buying via J/Shift+J/double-J, and Ctrl+Space to activate a board
minion) that are not reflected in commands.html's Battlegrounds section as
transcribed above. This document transcribes commands.html only, per the
wayfinder ticket's scope; the changelog gap is noted here in case a future
ticket needs it.
