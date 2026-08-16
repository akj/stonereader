"""Holder-driven Sounds menu Surface (ADR-0008)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from stonereader.services._audio_index import CardClip
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType


class SoundsIndex(Protocol):
    def clips_for_card(self, card_id: str) -> list[CardClip]: ...

    def decode(self, clip_key: str) -> bytes: ...


class SoundsPlayer(Protocol):
    def play(self, wav_bytes: bytes) -> None: ...


@dataclass(frozen=True)
class _SoundsRequest:
    card_id: str
    card_name: str


class SoundsMenuHolder:
    """App-owned request holder reused by the singleton Sounds menu."""

    def __init__(self) -> None:
        self._request: _SoundsRequest | None = None

    def set(self, card_id: str, card_name: str) -> None:
        self._request = _SoundsRequest(card_id, card_name)

    def get(self) -> _SoundsRequest:
        if self._request is None:
            raise RuntimeError("No card has been selected for the Sounds menu")
        return self._request


def build_sounds_menu(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    holder: SoundsMenuHolder,
    audio_index: SoundsIndex,
    player: SoundsPlayer,
) -> ActiveSurface:
    """Build the vertical menu that plays only on Enter, never on focus."""
    engine: VerticalMenuEngine | None = None

    def display_name() -> str:
        return f"{holder.get().card_name} sounds"

    def play(clip_key: str) -> None:
        wav_bytes = audio_index.decode(clip_key)
        if wav_bytes:
            player.play(wav_bytes)

    def options() -> list[MenuOption]:
        request = holder.get()
        return [
            MenuOption(
                f"clip.{number}",
                lambda label=clip.event_label: label,
                lambda key=clip.clip_key: play(key),
            )
            for number, clip in enumerate(
                audio_index.clips_for_card(request.card_id),
                start=1,
            )
        ]

    def activate() -> None:
        if engine is None:
            raise RuntimeError("Sounds menu engine is not active")
        if not engine.activate_current():
            announcer.noop("Nothing to do here")

    spec = SurfaceSpec(
        "Sounds menu",
        WidgetType.VERTICAL_MENU,
        context_label=display_name,
        options=options,
        display_name=display_name,
        slot_fills={
            Slot.ENTER: Command(
                "sounds.play",
                "Enter: play this sound",
                activate,
            )
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Sounds menu requires a vertical-menu engine")
    engine = surface.engine
    return surface
