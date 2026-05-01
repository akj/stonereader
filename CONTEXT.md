# StoneReader

Accessible Hearthstone deck tracker, deck manager, and replay viewer for screen-reader users on Windows.

## Language

**Zone** (game):
A region of the Hearthstone game state where a card currently lives — `HAND`, `DECK`, `PLAY`, `GRAVEYARD`, `SETASIDE`, `SECRET`, `REMOVEDFROMGAME`.
_Avoid_: "game zone", "card location"

**zone** (UI):
A navigable list in the StoneReader UI with a persistent cursor and a user-facing label.
_Avoid_: "pane", "section", "list", "region"

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

**Replay**:
A **Game** that has finished, loaded from an HSReplay XML file. The **User** navigates turn-by-turn through a `ReplayState`, which wraps `Tuple[GameState, ...]`.
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

## Relationships

- A UI **zone** either projects from a game **Zone** (e.g., the Remaining Deck zone is `Zone.DECK` minus draws) or is *synthesised* (Cards Drawn, Opponent Played) and corresponds to no single game **Zone**.
- Each UI **zone** owns one cursor; cursors persist across zone switches via `ZoneNavigationMixin`.
- One **Card** → many **Entities** (two Fireballs in a deck = two Entities pointing at the same Fireball **Card**). `CardDatabase` holds **Cards**; `GameState` holds **Entities**.
- A game has exactly one **Friendly Player** and one **Opponent** from the **User**'s perspective. Hearthstone's `player_id` (1 or 2) is server-assigned and only maps to Friendly/Opponent after resolution.
- In a **Live game**, the **Friendly Player** is always the **User**'s side. In a **Replay**, the **Friendly Player** is whoever the replay was recorded from — which may or may not be the **User** (the User might be watching someone else's replay). `ReplayState.friendly_player_id` is captured from the replay metadata, not from the User's identity.
- A **Game event** is always derivable from a pair of `GameState` snapshots; consumers never need access to **Packets**, the engine's internal block stack, or hslog/HSReplay APIs. Cases where a packet-level fact is needed for a **Game event** (block context for "was played from hand," mulligan completion timing, attack-in-progress) are lifted onto `GameState` itself so the diff function can recover them.

## Flagged ambiguities

- **Zone vs zone**: capital-Z `Zone` is the Hearthstone enum (`hearthstone.enums.Zone`); lowercase `zone` is the StoneReader UI navigable list. Both appear in the code — the imported `Zone` enum in `services/_engine.py` etc., and the `_*_ZONE` constants in `presenters/`. In prose, always pair the lowercase `zone` with its proper noun ("the Remaining Deck zone") so it's never bare.
- **Player vs Friendly Player**: code uses `player_` as shorthand for "Friendly Player" in attribute names; in prose, prefer "Friendly Player" so it doesn't collide with the generic Hearthstone idea of "a player" (there are two). When referring to either side abstractly, say "side." `player_id` (1 or 2) is the Hearthstone server-slot; it only maps to Friendly/Opponent after `FriendlyPlayerExporter` resolution.
