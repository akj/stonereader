"""Read-only Deck detail Surface."""

from __future__ import annotations

from stonereader.models.card import Card
from stonereader.surfaces._deck_data import CurrentDeck, DeckData, spoken_enum
from stonereader.surfaces._game_audio import CardAudioIndex, open_sounds_for_card
from stonereader.surfaces.sounds_menu import SoundsMenuHolder
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import SurfaceSpec, WidgetType, ZoneSpec


def build_deck_detail(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    data: DeckData,
    current_deck: CurrentDeck,
    *,
    audio_index: CardAudioIndex | None = None,
    sounds: SoundsMenuHolder | None = None,
) -> ActiveSurface:
    """Build the lazy singleton that reads the app's current deck."""
    engine: HorizontalListEngine | None = None

    def items() -> tuple[tuple[Card, int], ...]:
        return data.resolve(current_deck.get()).cards

    def title(item: tuple[Card, int]) -> str:
        card, count = item
        return f"{card.name} x{count}" if count > 1 else card.name

    def detail_lines(item: tuple[Card, int]) -> list[str]:
        card, _count = item
        lines = [f"{card.cost} mana", spoken_enum(card.card_type)]
        if card.card_type in {"MINION", "WEAPON"}:
            if card.attack is not None and card.health is not None:
                lines.append(f"{card.attack} attack, {card.health} health")
        if card.text:
            lines.append(card.text)
        return lines

    def listen() -> None:
        if engine is None or audio_index is None or sounds is None:
            raise RuntimeError("Deck detail game-audio dependencies are not active")
        current = engine.current_item()
        if not isinstance(current, tuple) or not isinstance(current[0], Card):
            announcer.noop("No card focused")
            return
        card, _count = current
        open_sounds_for_card(
            announcer,
            nav,
            audio_index,
            sounds,
            card_id=card.id,
            card_name=card.name,
            title=title(current),
        )

    spec = SurfaceSpec(
        "Deck detail",
        WidgetType.HORIZONTAL_LIST,
        context_label=lambda: current_deck.get().name,
        zones=[
            ZoneSpec(
                "cards",
                "Cards",
                items,
                title,
                detail_lines,
            )
        ],
        slot_noops=(
            {}
            if audio_index is not None and sounds is not None
            else {Slot.LISTEN: "Game audio is not available"}
        ),
        slot_fills=(
            {
                Slot.LISTEN: Command(
                    "deck_detail.listen",
                    "L: listen to this card's sounds",
                    listen,
                )
            }
            if audio_index is not None and sounds is not None
            else {}
        ),
        display_name=lambda: current_deck.get().name,
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, HorizontalListEngine):
        raise TypeError("Deck detail requires a horizontal-list engine")
    engine = surface.engine
    return surface
