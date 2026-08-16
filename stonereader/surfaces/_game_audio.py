"""Shared Surface-side request logic for the universal LISTEN slot."""

from __future__ import annotations

from typing import Protocol

from stonereader.services._audio_index import CardClip
from stonereader.surfaces.sounds_menu import SoundsMenuHolder
from stonereader.ui.announcer import Announcer
from stonereader.ui.navigation import NavigationController


class CardAudioIndex(Protocol):
    @property
    def status(self) -> str: ...

    @property
    def reason(self) -> str: ...

    def clips_for_card(self, card_id: str) -> list[CardClip]: ...


def open_sounds_for_card(
    announcer: Announcer,
    nav: NavigationController,
    audio_index: CardAudioIndex,
    holder: SoundsMenuHolder,
    *,
    card_id: str | None,
    card_name: str,
    title: str,
) -> None:
    """Apply every LISTEN degenerate case before drilling down."""
    if not card_id:
        announcer.noop("No card focused")
        return
    if audio_index.status != "ready":
        announcer.noop(audio_index.reason)
        return
    clips = audio_index.clips_for_card(card_id)
    if not clips:
        announcer.noop(f"{title}: no sounds")
        return
    holder.set(card_id, card_name)
    nav.drill_down("Sounds menu")
