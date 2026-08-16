"""Pure turn views derived from replay snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from stonereader.models.game_state import GameState
from stonereader.models.replay import ReplayState
from stonereader.services._diff import diff
from stonereader.services._events import GameEvent


@dataclass(frozen=True)
class TurnView:
    """The final state and derived events for one Hearthstone turn."""

    number: int
    is_friendly: bool
    state: GameState
    events: tuple[GameEvent, ...]


def turns(replay: ReplayState) -> list[TurnView]:
    """Group ordered replay snapshots by the transition's post-state turn.

    This preserves the old viewer's shipped grouping rule: the first snapshot
    is treated as a cold-start transition and every later snapshot is paired
    with its predecessor. Turn-zero mulligan snapshots are folded into turn 1
    as its prelude instead of becoming a separately navigable turn.
    """
    grouped: dict[int, tuple[GameState, list[GameEvent]]] = {}
    previous: GameState | None = None
    for state in replay.states:
        number = max(1, state.turn)
        if number not in grouped:
            grouped[number] = (state, [])
        _last_state, events = grouped[number]
        events.extend(diff(previous, state))
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
