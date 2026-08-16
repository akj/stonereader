"""Preset-filtered Lane-2 narration for derived Game events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from stonereader.models.card import CardDatabase
from stonereader.models.game_state import GameState
from stonereader.services._diff import diff
from stonereader.services._event_phrases import phrase
from stonereader.services._events import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    GameEnded,
    GameEvent,
    MinionDied,
    SecretPlayed,
    SecretRevealed,
    TurnChanged,
)
from stonereader.ui.announcer import Announcer


_KEY_MOMENTS = (
    TurnChanged,
    MinionDied,
    SecretPlayed,
    SecretRevealed,
    GameEnded,
)


class Narrator:
    """Translate tracker state pairs into preset-filtered Lane-2 speech."""

    def __init__(
        self,
        announcer: Announcer,
        preset_provider: Callable[[], str],
        card_db: CardDatabase,
    ) -> None:
        self._announcer = announcer
        self._preset_provider = preset_provider
        self._card_db = card_db

    def on_state(self, prev: GameState | None, curr: GameState) -> None:
        """Diff one tracker publication and narrate its admitted events."""
        preset = self._preset_provider()
        if preset == "off":
            return
        for event in diff(prev, curr):
            if not _included(event, preset):
                continue
            text = phrase(self._with_known_name(event), curr)
            if text is not None:
                self._announcer.narrate(text)

    def _with_known_name(self, event: GameEvent) -> GameEvent:
        if not isinstance(event, (CardDrawn, CardPlayed)) or event.name:
            return event
        card = event.base_card or self._card_db.get_card_by_id(event.card_id)
        if card is None:
            return event
        return replace(event, base_card=card, name=card.name)


def _included(event: GameEvent, preset: str) -> bool:
    if isinstance(event, CardPlayed):
        return event.controller != 1 and preset in {"key_moments", "everything"}
    if isinstance(event, _KEY_MOMENTS):
        return preset in {"key_moments", "everything"}
    if isinstance(event, (CardDrawn, AttackStarted)):
        return preset == "everything"
    return False
