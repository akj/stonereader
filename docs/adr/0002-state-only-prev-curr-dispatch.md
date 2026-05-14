# State-only `(prev, curr)` dispatch with Game events as a downstream library

## Status

Accepted. Implemented across [#3](https://github.com/akj/stonereader/issues/3), [#4](https://github.com/akj/stonereader/issues/4), and [#5](https://github.com/akj/stonereader/issues/5); landed on `main` in commits `1db2deb`, `664145e`, `d77d4e2`.

## Context

The engine that consumes `Power.log` used to produce a stream of typed **Game events** (eleven subtypes — `CardDrawn`, `CardPlayed`, `MinionDied`, `TurnChanged`, `MulliganDone`, `CardRevealed`, `CardRemoved`, `AttackStarted`, `DamageDealt`, plus `GameStarted`/`GameEnded`) and dispatch them alongside a `GameState` snapshot to subscribers. In production code, only `GameStarted` and `GameEnded` were ever inspected by a subscriber. The other nine types were constructed, populated, asserted on in engine tests, fanned through the tracker, and dropped by the only consumer (`LiveGamePresenter`), which read the trailing `GameState` directly.

This was a shallow module: a wide interface (eleven event types, each with several fields and lifecycle invariants) for very little leverage at the seam (the subscriber callback). It also blocked future work. The **Replay** viewer (Phase 4) needs to narrate "what happened on turn 3" from a `Tuple[GameState, ...]` snapshot stream — but the engine's event-production paths were driven by `Packet` consumption, and the Replay viewer has no Packets to feed the engine. The event-production path was **Live game**-only, even though the **User**'s narration experience should be identical across **Game** modes (see CONTEXT.md, "Game event").

A separate transport-level concern: the Hearthstone-disappeared case (game process gone before a `PLAYSTATE` resolves) was signalled by the tracker synthesising a `GameEnded` event with no underlying packet. Lifecycle was a property of the dispatch shape, not of state.

We needed a dispatch surface that: (a) shared one implementation across **Live game** and **Replay**, (b) didn't require subscribers to pay the cost of event decoding when they only wanted state changes, and (c) modelled lifecycle as state, not as a special signal.

## Decision

The tracker dispatches `(prev: Optional[GameState], curr: GameState) -> None` to subscribers. There is no other channel. **Game events** live in a downstream library — a pure diff function (`stonereader/services/_diff.py`) that takes two `GameState` snapshots and returns the events that occurred between them. Subscribers wanting event-typed information call `diff(prev, curr)` inside their handlers. Subscribers wanting only state changes ignore the helper.

The `GameState` model carries the packet-level context the diff needs to recover events that aren't visible from raw entity zones (`block_stack`, `mulligan_complete`, `attack_in_progress`, see [`stonereader/models/game_state.py:148`](../../stonereader/models/game_state.py)). The engine writes these fields as it applies packets; future Replay loaders will populate them from HSReplay XML.

Lifecycle is a `GameState.game_state` field with three values — `"RUNNING"`, `"COMPLETE"`, `"ABANDONED"` ([`stonereader/models/game_state.py:139`](../../stonereader/models/game_state.py)). The Hearthstone-disappeared case becomes "the tracker publishes a final state with `game_state="ABANDONED"`" rather than a synthetic `GameEnded` envelope. The diff function spots `RUNNING → COMPLETE/ABANDONED` and emits `GameEnded`; the dispatch shape is unchanged.

`Engine.apply(packet)` returns `None`. The engine is a pure `Packet → GameState` reducer; its only output is the next `current_state`.

## Alternatives considered and rejected

**`EventBus` / `Selector` / `Channel` flexibility surface.** Subscribers register interest in specific event types; a routing layer fans matching events. Rejected as over-engineered for current consumer pressure: there is one consumer today (`LiveGamePresenter`) and it ignores nine of eleven types. A flexibility surface earns its keep when there are multiple consumers with divergent interests; we have none.

**`GameTick` envelope bundling state and events into a single delivery.** A `GameTick(prev, curr, events)` value is dispatched per state change. Rejected because it couples state delivery to event delivery: a state-only consumer (a future sighted-user redraw pane, for example) pays the cost of event decoding it doesn't use. The pure diff function gives the same access at the call site without coupling the channel.

**Three-method asymmetric subscription (`on_state` / `on_lifecycle` / `on_event`).** Subscribers implement separate callbacks for state changes, lifecycle transitions, and per-event notifications. Rejected because it splits a uniform `(prev, curr)` channel into three without justification: lifecycle and per-event information are both derivable from the same pair of states, so there's no reason to ship three subscription points.

## Consequences

**Positive.**

- One implementation of event derivation serves both **Live game** and **Replay**. The diff function has no engine reference, no I/O, no clock; it is the deepest test surface in the system, exhaustively unit-testable from `GameState` literals.
- The engine simplifies. Two parallel writes (state mutation + event emission) collapse to one. ~250 LoC of event-construction paths deleted.
- State-only consumers pay nothing for events they don't want. Event-typed consumers call `diff()` at the call site.
- Lifecycle is a property of state, not of the transport. `GameState.game_state="ABANDONED"` is interpretable in isolation (in a snapshot, in a test fixture, in a future replay file) without reconstructing a stream of synthetic events.
- The **D-07** invariant (subscribers never speak; speech is presenter-only and user-initiated) is preserved by the shape of the channel: the dispatch carries data, not user-facing intent.

**Negative.**

- Subscribers wanting events run `diff()` themselves. If many consumers want the same events, they each recompute. Today this is theoretical (one consumer); if it becomes real, memoisation can be added at the dispatch layer without changing the channel shape.
- The diff function is shipped before its primary consumer (Replay narration, Phase 4) exists. Pure functions are cheap to write and test, and the Live ↔ Replay symmetry is the load-bearing reason for the seam — but if Phase 4 reshapes substantially, parts of the diff may need revision.
- `GameState` grows fields the engine writes for the diff's benefit (`block_stack`, `mulligan_complete`, `attack_in_progress`). These are packet-level facts lifted onto state; Replay loaders will need to reconstruct them from HSReplay XML, which is non-trivial.
- The deletion test passes loudly: removing `_diff.py` would force the engine to grow event-emission paths back, the tracker to re-bundle events into its dispatch, and the future Replay viewer to re-implement event production from XML. This is the intended shape — the seam earns its keep — but it does mean the module is load-bearing even though its only current caller is `LiveGamePresenter`'s lifecycle branch.
