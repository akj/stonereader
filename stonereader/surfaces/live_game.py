"""Fourteen-zone current-state Live Game Surface."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from stonereader.models.card import Card
from stonereader.models.game_state import GameState
from stonereader.surfaces._game_surface import (
    card_items,
    card_zone,
    hero_items,
    opponent_hero_details,
    player_hero_details,
    require_engine,
    singleton,
)
from stonereader.surfaces._zone_format import hero_title
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, SurfaceSpec, WidgetType, ZoneSpec


class CurrentGame:
    """App-owned latest-running-game seam shared by the Surface and hotkeys."""

    def __init__(self) -> None:
        self._state: GameState | None = None
        self._subscribers: list[Callable[[], None]] = []

    def get(self) -> GameState | None:
        return self._state

    def on_state(self, prev: GameState | None, curr: GameState) -> None:
        """Store only a running Game and notify render subscribers silently."""
        del prev
        self._state = curr if curr.game_state == "RUNNING" else None
        self._notify()

    def reset(self) -> None:
        """Clear state when the tracker resets its Power.log stream."""
        self._state = None
        self._notify()

    def subscribe(self, on_change: Callable[[], None]) -> None:
        if on_change not in self._subscribers:
            self._subscribers.append(on_change)

    def _notify(self) -> None:
        for subscriber in tuple(self._subscribers):
            subscriber()


@dataclass(frozen=True)
class RemainingDeckItem:
    card: Card
    copies: int
    cards_remaining: int


def build_live_game(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    current_game: CurrentGame,
) -> ActiveSurface:
    """Build the lazy singleton Live Game Surface."""
    engine: HorizontalListEngine | None = None

    def state() -> GameState | None:
        return current_game.get()

    def remaining_deck() -> list[RemainingDeckItem]:
        current = state()
        if current is None:
            return []
        counts = Counter(
            entity.card_id
            for entity in current.player_deck
            if entity.card_id and entity.base_card is not None
        )
        cards = {
            entity.card_id: entity.base_card
            for entity in current.player_deck
            if entity.card_id and entity.base_card is not None
        }
        return [
            RemainingDeckItem(cards[card_id], copies, current.player_deck_count)
            for card_id, copies in sorted(
                counts.items(),
                key=lambda pair: (cards[pair[0]].cost, cards[pair[0]].name),
            )
        ]

    def query(subject: str, value: Callable[[GameState], str]) -> None:
        current = state()
        if current is None:
            announcer.noop("No game in progress")
            return
        announcer.query(subject, value(current))

    # Remaining Deck is intentionally first: Home -> L starts there, while the
    # lazy singleton still preserves the found-as-left zone after first visit.
    zones = [
        ZoneSpec(
            "remaining_deck",
            "Remaining Deck",
            remaining_deck,
            _remaining_deck_title,
            _remaining_deck_details,
            Chord("d"),
            "D: jump to Remaining Deck",
        ),
        card_zone(
            "your_board",
            "Your board",
            "b",
            "B: your minions",
            card_items(state, "player_board"),
        ),
        card_zone(
            "opponent_board",
            "Opponent board",
            "g",
            "G: opponent minions",
            card_items(state, "opponent_board"),
        ),
        card_zone(
            "your_hand",
            "Your hand",
            "c",
            "C: your hand",
            card_items(state, "player_hand"),
        ),
        card_zone(
            "your_secrets",
            "Your secrets",
            "s",
            "S: your secrets",
            card_items(state, "player_secrets"),
        ),
        card_zone(
            "opponent_secrets",
            "Opponent secrets",
            "s",
            "Shift+S: opponent secrets",
            card_items(state, "opponent_secrets"),
            shift=True,
        ),
        ZoneSpec(
            "your_hero",
            "Your hero",
            hero_items(state, "player_hero"),
            hero_title,
            player_hero_details(state),
            Chord("v"),
            "V: your hero",
        ),
        ZoneSpec(
            "opponent_hero",
            "Opponent hero",
            hero_items(state, "opponent_hero"),
            hero_title,
            opponent_hero_details(state),
            Chord("f"),
            "F: opponent hero",
        ),
        card_zone(
            "your_weapon",
            "Your weapon",
            "w",
            "W: your weapon",
            singleton(state, "player_weapon"),
        ),
        card_zone(
            "opponent_weapon",
            "Opponent weapon",
            "w",
            "Shift+W: opponent weapon",
            singleton(state, "opponent_weapon"),
            shift=True,
        ),
        card_zone(
            "your_played",
            "Your played",
            "p",
            "P: cards you played",
            card_items(state, "player_played"),
            with_turn=True,
        ),
        card_zone(
            "opponent_played",
            "Opponent played",
            "p",
            "Shift+P: cards your opponent played",
            card_items(state, "opponent_played"),
            shift=True,
            with_turn=True,
        ),
        card_zone(
            "your_drawn",
            "Your drawn",
            "n",
            "N: cards you drew",
            card_items(state, "player_drawn"),
            with_turn=True,
        ),
        card_zone(
            "opponent_drawn",
            "Opponent drawn",
            "n",
            "Shift+N: cards your opponent drew",
            card_items(state, "opponent_drawn"),
            shift=True,
            with_turn=True,
        ),
    ]

    bindings = [
        Binding(
            Chord("a"),
            Command(
                "live.query_mana",
                "A: how much mana you have",
                lambda: query(
                    "Your mana",
                    lambda current: f"{current.player_mana} of {current.player_max_mana}",
                ),
            ),
        ),
        Binding(
            Chord("a", shift=True),
            Command(
                "live.query_opponent_mana",
                "Shift+A: how much mana your opponent has",
                lambda: query(
                    "Opponent mana",
                    lambda current: (
                        f"{current.opponent_mana} of {current.opponent_max_mana}"
                    ),
                ),
            ),
        ),
        Binding(
            Chord("d", shift=True),
            Command(
                "live.query_opponent_deck",
                "Shift+D: how many cards are in your opponent's deck",
                lambda: query(
                    "Opponent deck",
                    lambda current: f"{current.opponent_deck_count} cards",
                ),
            ),
        ),
        Binding(
            Chord("r"),
            Command(
                "live.query_hero_power",
                "R: your hero power",
                lambda: query(
                    "Your hero power",
                    lambda current: current.player_hero.hero_power or "No hero power",
                ),
            ),
        ),
        Binding(
            Chord("r", shift=True),
            Command(
                "live.query_opponent_hero_power",
                "Shift+R: your opponent's hero power",
                lambda: query(
                    "Opponent hero power",
                    lambda current: (
                        current.opponent_hero.hero_power or "No hero power"
                    ),
                ),
            ),
        ),
        Binding(
            Chord("y"),
            Command(
                "live.no_events",
                "Y: no events in a live game",
                lambda: announcer.noop("No events in a live game"),
            ),
        ),
        Binding(
            Chord("c", shift=True),
            Command(
                "live.opponent_hand",
                "Shift+C: the game announces the opponent's hand",
                lambda: announcer.noop("The game announces the opponent's hand"),
            ),
        ),
    ]
    bindings.extend(
        Binding(
            Chord(str(position)),
            Command(
                f"live.position.{position}",
                "1 to 9: jump to that position in the list",
                lambda position=position: require_engine(
                    engine, "Live Game"
                ).jump_to_position(position),
            ),
        )
        for position in range(1, 10)
    )
    bindings.append(
        Binding(
            Chord("0"),
            Command(
                "live.position.10",
                "0: jump to the tenth item",
                lambda: require_engine(engine, "Live Game").jump_to_position(10),
            ),
        )
    )

    spec = SurfaceSpec(
        "Live Game",
        WidgetType.HORIZONTAL_LIST,
        zones=zones,
        bindings=bindings,
        slot_noops={
            Slot.COARSE_AXIS: "No turns to step in a live game",
            Slot.LISTEN: "No game audio during a live game",
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, HorizontalListEngine):
        raise TypeError("Live Game requires a horizontal-list engine")
    engine = surface.engine
    current_game.subscribe(engine.refresh)
    return surface


def _remaining_deck_title(item: RemainingDeckItem) -> str:
    noun = "copy" if item.copies == 1 else "copies"
    return f"{item.card.name}, {item.copies} {noun}"


def _remaining_deck_details(item: RemainingDeckItem) -> list[str]:
    percentage = (
        int((item.copies * 100 / item.cards_remaining) + 0.5)
        if item.cards_remaining > 0
        else 0
    )
    card = item.card
    lines = [
        f"{percentage} percent to draw",
        f"{card.cost} mana",
        card.card_type.replace("_", " ").title(),
    ]
    if (
        card.card_type in {"MINION", "WEAPON"}
        and card.attack is not None
        and card.health is not None
    ):
        lines.append(f"{card.attack} attack, {card.health} health")
    if card.text:
        lines.append(card.text)
    return lines
