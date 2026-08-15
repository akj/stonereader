# StoneReader

Accessible Hearthstone deck tracker, deck manager, and replay viewer for screen-reader users on Windows.

## Language

**Zone** (game):
A region of the Hearthstone game state where a card currently lives — `HAND`, `DECK`, `PLAY`, `GRAVEYARD`, `SETASIDE`, `SECRET`, `REMOVEDFROMGAME`.
_Avoid_: "game zone", "card location"

**zone** (UI):
A navigable list in the StoneReader UI with a persistent cursor and a user-facing label.
_Avoid_: "pane", "section", "list", "region"

**Surface**:
A distinct place in the StoneReader UI the **User** can be — Home, Card Browser, Replay Viewer, a help screen. Surfaces stack; going back pops to the previous one. Each surface presents exactly one **Widget type**. See ADR-0004.
_Avoid_: "screen", "panel", "page", "view" (when naming the user-facing concept)

**Widget type**:
One of the two navigation shapes a **Surface** presents: **Vertical menu** or **Horizontal list**. There is no third type. See ADR-0004.
_Avoid_: "control type", "layout"

**Vertical menu**:
The **Widget type** for choosing among options: Up/Down move a cursor over options, Enter acts on the current one. Forms are vertical menus whose options are fields and actions.
_Avoid_: "list box", "menu screen"

**Horizontal list**:
The **Widget type** for browsing items with depth: Left/Right move between items, Up/Down read the detail lines of the current item.
_Avoid_: "card list", "browse mode"

**Screen jump**:
Reaching a **Surface** via a Home menu option, its Home letter, or a system-wide hotkey. A jump resets the surface stack to Home → target, so back from a jumped-to Surface always goes Home. See ADR-0006.
_Avoid_: "switch screen", "navigate to" (ambiguous with **Drill-down**)

**Drill-down**:
Reaching a **Surface** from within another (Replays → Replay Viewer, Decks → Import Deck, F1 → help). A drill-down pushes one level onto the surface stack; back pops exactly one. See ADR-0006.
_Avoid_: "sub-screen", "child screen"

**Text mode**:
The state in which keystrokes go to a text field instead of navigation. Entered only by an explicit act (never on surface entry); Enter commits and leaves, Escape leaves without committing.
_Avoid_: "edit mode", "input mode"

**Title line**:
The canonical one-line identity of an item — the shortest string that distinguishes it from its neighbors in its list. One formatter produces it; the displayed row, the movement utterance, and detail line 0 are this same string, written for the ear. See ADR-0007.
_Avoid_: "summary", "row text", "label" (that's the context's name, not the item's)

**Context-entry utterance**:
The single utterance spoken whenever the **User** lands in a context — by **Screen jump**, **Drill-down**, back-reveal, zone switch, in-place rebuild (filter/search), or orientation reread (Shift+Up). Route-invariant: the same place always sounds the same. See ADR-0007.
_Avoid_: "entry announcement" (suggests surface entry only — the utterance covers every landing route)

**Speech lane**:
One of the two priority classes an utterance belongs to. **Lane 1** (user-initiated: movement, entry, queries, confirmations) always interrupts. **Lane 2** (auto-narration of **Game events**) queues among itself, never interrupts Lane 1, and is dropped by any Lane-1 keypress. See ADR-0007.
_Avoid_: "channel" (reserved for output media — speech vs **Game audio**), "priority"

**Game audio**:
StoneReader's second output channel beside speech: Hearthstone's own audio assets (voice lines, event sounds), extracted at runtime from the **User**'s local Hearthstone installation — never shipped with the app, never fetched from elsewhere. Absent (and announced as such) when no install is found. See ADR-0008.
_Avoid_: "sound cues" (the abandoned earcon concept), "sound effects" (one kind of clip, not the channel)

**Sounds menu**:
The **Vertical menu** the listen key (L) drills into from any card under the cursor, listing that card's **Game audio** clips by event ("Play", "Attack", "Death", …); Enter plays the focused clip. See ADR-0008.
_Avoid_: "audio browser", "voice-line list"

**Help menu**:
The **Vertical menu** F1 pushes from any **Surface** (a **Drill-down**): the widget-type sentence first, then the surface's bindings key-first, then Universal-keys and All-commands drill-downs. Enter performs the chosen binding on the underlying Surface. Generated from the command registry — never hand-written. See ADR-0009.
_Avoid_: "help screen", "help dialog", "documentation"

**Card**:
The static definition of a Hearthstone card — name, cost, type, class. Loaded once from `hearthstone-data` XML and indexed in `CardDatabase`. The same **Card** object is shared by every runtime instance of that card.
_Avoid_: "card definition" (redundant)

**Entity**:
A runtime instance of a **Card** in a specific game. Has its own `entity_id`, references a **Card** via `base_card`, and carries per-game state (current **Zone**, controller, drawn turn, creation lineage). Mirrors the `Entity` concept in Hearthstone's `Power.log`.
_Avoid_: "card instance", "in-game card"

**User**:
The human running StoneReader — always a screen-reader user.
_Avoid_: "player" (when referring to the User), "the user"

**Friendly Player**:
The in-game side the **User** is playing as. Resolved at game start via `FriendlyPlayerExporter` (`WR-02`). In code, attributes prefixed `player_*` (`player_deck`, `player_hand`, `player_played`, `player_drawn`, `player_hero`) refer to this side.
_Avoid_: "self", "me", "us", bare "player" in prose

**Opponent**:
The in-game side opposing the **Friendly Player**. In code, attributes prefixed `opponent_*` refer to this side.
_Avoid_: "enemy", "them", "the other player"

**Game**:
A Hearthstone match. Either a **Live game** (currently being played) or a **Replay** (finished and loaded from a file). Both modes consume `GameState`.
_Avoid_: "match"

**Live game**:
A **Game** in progress. Source: `Power.log` real-time tail. State updates as events arrive. Tracking starts on `CREATE_GAME` and resets on game end.
_Avoid_: "current game", "active game"

**Live game timeline**:
The navigable history of a **Live game** while it is in progress.
_Avoid_: "live replay"

**Replay**:
A **Game** that has finished, loaded from a persisted source such as HSReplay XML or a StoneReader-saved game record. The **User** navigates turn-by-turn through a `ReplayState`, which wraps `Tuple[GameState, ...]`.
_Avoid_: "recording", "log" (`Power.log` is a different thing)

**Game event**:
An observable happening in a **Game** that downstream consumers can react to —
e.g. a card was drawn, a minion died, the turn flipped, the game ended.
**Game-mode-agnostic**: the same event types describe what happened whether the
**Game** is a **Live game** or a **Replay**. Derived from a pair of `GameState`
snapshots by a pure diff function, so the **Live game** pipeline (engine apply
→ new state → diff vs previous) and the **Replay** pipeline (User advances
turn → diff `states[i]` vs `states[i+1]`) produce **Game events** of the same
shape. Distinct from a **Packet**, which is a `Power.log`-specific input the
engine consumes; **Game events** are an output the rest of the system consumes.
_Avoid_: "narration event" (names a single consumer's purpose), "engine event"
(too narrow — Replays produce them too without an engine)

**Hearthstone Access** (or **HSA**):
The third-party Hearthstone accessibility mod (hearthstoneaccess.com), used as StoneReader's canonical reference for keyboard navigation conventions. StoneReader's **Replay** viewer and Cards surface mirror HSA's key conventions — including its internal inconsistencies — so that HSA users carry muscle memory across. See ADR-0003.
_Avoid_: "the mod", "HearthstoneAccess" (single word), generic "accessibility mod"

## Relationships

- A **Surface** presents exactly one **Widget type**; **Text mode** is a temporary state on top of a Surface, not a third type.
- A **Surface** is reached by a **Screen jump** (stack resets to Home → target) or a **Drill-down** (pushes one level); back pops one drill-down, goes Home from any jumped-to Surface, and is an announced no-op at Home.
- UI **zones** live on horizontal-list **Surfaces** (Live Game, Replay Viewer); switching zones changes what the list shows, never the **Widget type**.
- A UI **zone** either projects from a game **Zone** (e.g., the Remaining Deck zone is `Zone.DECK` minus draws) or is *synthesised* (Cards Drawn, Opponent Played) and corresponds to no single game **Zone**.
- Each UI **zone** owns one cursor; cursors persist across zone switches via `ZoneNavigationMixin`.
- Every item has exactly one **Title line**; everything else spoken (context label, position, "empty", confirmations) is ephemeral wrapping added by the announcement layer, never baked into item text.
- The **Context-entry utterance** wraps the **Title line**: `"{Context label}, {title}, {position} of {count}"` for **Horizontal lists** and zones, `"{Context label}, {current option}"` for **Vertical menus**, `"{Context label}: empty"` when empty.
- Every utterance belongs to exactly one **Speech lane**; a **Game event** may only ever speak on Lane 2.
- Every **Surface** has a **Help menu**, reached by F1; its options mirror the surface's bindings exactly (they are one registry), and Enter performs the chosen binding.
- **Game audio** never delays or preempts speech; at most one clip plays at a time (a new one replaces it); surface transitions and a bare Ctrl tap stop it; ordinary navigation lets it play out. A **Live game** surface never plays **Game audio** — the real client's audio is already present.
- One **Card** → many **Entities** (two Fireballs in a deck = two Entities pointing at the same Fireball **Card**). `CardDatabase` holds **Cards**; `GameState` holds **Entities**.
- A game has exactly one **Friendly Player** and one **Opponent** from the **User**'s perspective. Hearthstone's `player_id` (1 or 2) is server-assigned and only maps to Friendly/Opponent after resolution.
- In a **Live game**, the **Friendly Player** is always the **User**'s side. In a **Replay**, the **Friendly Player** is whoever the replay was recorded from — which may or may not be the **User** (the User might be watching someone else's replay). `ReplayState.friendly_player_id` is captured from the replay metadata, not from the User's identity.
- A **Live game timeline** and a **Replay** are both navigable histories of a **Game**, but only a **Replay** is loaded from a persisted finished-game source.
- After a **Live game** ends normally, its **Live game timeline** is automatically persisted as a **Replay**.
- An abandoned **Live game** is not persisted as a **Replay** because StoneReader did not observe a complete game result.
- A **Game event** is always derivable from a pair of `GameState` snapshots; consumers never need access to **Packets**, the engine's internal block stack, or hslog/HSReplay APIs. Cases where a packet-level fact is needed for a **Game event** (block context for "was played from hand," mulligan completion timing, attack-in-progress) are lifted onto `GameState` itself so the diff function can recover them.

## Flagged ambiguities

- **Zone vs zone**: capital-Z `Zone` is the Hearthstone enum (`hearthstone.enums.Zone`); lowercase `zone` is the StoneReader UI navigable list. Both appear in the code — the imported `Zone` enum in `services/_engine.py` etc., and the `_*_ZONE` constants in `presenters/`. In prose, always pair the lowercase `zone` with its proper noun ("the Remaining Deck zone") so it's never bare.
- **Player vs Friendly Player**: code uses `player_` as shorthand for "Friendly Player" in attribute names; in prose, prefer "Friendly Player" so it doesn't collide with the generic Hearthstone idea of "a player" (there are two). When referring to either side abstractly, say "side." `player_id` (1 or 2) is the Hearthstone server-slot; it only maps to Friendly/Opponent after `FriendlyPlayerExporter` resolution.
- **Live game timeline vs Replay**: "live replay" was rejected because external Hearthstone tools use **Replay** for finished-game review and "live" language for in-progress information.
