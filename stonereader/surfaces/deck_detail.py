"""Read-only Deck detail Surface."""

from __future__ import annotations

from stonereader.models.card import Card
from stonereader.surfaces._deck_data import CurrentDeck, DeckData, spoken_enum
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import SurfaceSpec, WidgetType, ZoneSpec


def build_deck_detail(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    data: DeckData,
    current_deck: CurrentDeck,
) -> ActiveSurface:
    """Build the lazy singleton that reads the app's current deck."""

    def items() -> tuple[tuple[Card, int], ...]:
        return data.resolve(current_deck.get()).cards

    def title(item: tuple[Card, int]) -> str:
        card, count = item
        return f"{card.name} x{count}" if count > 1 else card.name

    def detail_lines(item: tuple[Card, int]) -> list[str]:
        card, _count = item
        lines = [f"{card.cost} mana", spoken_enum(card.card_type)]
        if card.card_type == "WEAPON":
            if card.attack is not None and card.health is not None:
                lines.append(f"{card.attack} attack, {card.health} durability")
        elif card.card_type == "MINION":
            if card.attack is not None and card.health is not None:
                lines.append(f"{card.attack} attack, {card.health} health")
        if card.text:
            lines.append(card.text)
        return lines

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
        slot_noops={
            Slot.ENTER: "Nothing to do here",
            Slot.LISTEN: "Game audio is not available",
        },
        display_name=lambda: current_deck.get().name,
    )
    return build_active_surface(spec, announcer, universal_bindings, nav)
