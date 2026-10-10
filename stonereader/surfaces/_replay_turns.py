"""Pure turn views derived from replay snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from stonereader.models.game_state import GameState
from stonereader.models.replay import ReplayState
from stonereader.services._diff import diff
from stonereader.services._events import GameEvent


@dataclass(frozen=True)
class TurnEvent:
    """A derived event and the replay snapshot immediately after it."""

    event: GameEvent
    state: GameState


@dataclass(frozen=True)
class TurnView:
    """The final state and derived events for one Hearthstone turn."""

    number: int
    is_friendly: bool
    state: GameState
    events: tuple[TurnEvent, ...]


def turn_number(state: GameState) -> int:
    """Return the turn a snapshot belongs to; the mulligan counts as turn 1."""
    return max(1, state.turn)


def turns(replay: ReplayState) -> list[TurnView]:
    """Group ordered replay snapshots by the transition's post-state turn.

    This preserves the old viewer's shipped grouping rule: the first snapshot
    is treated as a cold-start transition and every later snapshot is paired
    with its predecessor. Turn-zero mulligan snapshots are folded into turn 1
    as its prelude instead of becoming a separately navigable turn.
    """
    grouped: dict[int, tuple[GameState, list[TurnEvent]]] = {}
    previous: GameState | None = None
    for state in replay.states:
        number = turn_number(state)
        if number not in grouped:
            grouped[number] = (state, [])
        _last_state, events = grouped[number]
        events.extend(TurnEvent(event, state) for event in diff(previous, state))
        grouped[number] = (state, events)
        previous = state

    return [
        TurnView(
            number=number,
            is_friendly=state.active_player_id == replay.friendly_player_id,
            state=state,
            events=tuple(events),
        )
        for number, (state, events) in sorted(grouped.items())
    ]
