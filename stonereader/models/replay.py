from dataclasses import dataclass
from typing import Tuple

from stonereader.models.game_state import GameState


@dataclass(frozen=True)
class ReplayState:
    """Complete game timeline as ordered sequence of GameState snapshots."""

    states: Tuple[GameState, ...]
    friendly_player_id: int
