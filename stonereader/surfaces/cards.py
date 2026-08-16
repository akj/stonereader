"""Composable card-library Surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from stonereader.models.card import Card, CardDatabase
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, SurfaceSpec, WidgetType, ZoneSpec
from stonereader.ui.text_mode import TextSession


class TextModeSink(Protocol):
    def enter_text_mode(self, session: TextSession) -> None: ...

    def exit_text_mode(self) -> None: ...


_CLASS_FILTERS: tuple[tuple[str, str | None], ...] = (
    ("All", None),
    ("Demon Hunter", "DEMONHUNTER"),
    ("Death Knight", "DEATHKNIGHT"),
    ("Druid", "DRUID"),
    ("Hunter", "HUNTER"),
    ("Mage", "MAGE"),
    ("Neutral", "NEUTRAL"),
    ("Paladin", "PALADIN"),
    ("Priest", "PRIEST"),
    ("Rogue", "ROGUE"),
    ("Shaman", "SHAMAN"),
    ("Warlock", "WARLOCK"),
    ("Warrior", "WARRIOR"),
)
_CLASS_NAMES = {value: label for label, value in _CLASS_FILTERS if value is not None}


@dataclass
class _CardsState:
    class_filter: str | None = None
    mana_filter: int | None = None
    search: str = ""
    _cache_key: tuple[str | None, int | None, str] | None = None
    _cache: list[Card] = field(default_factory=list)

    def invalidate(self) -> None:
        self._cache_key = None

    def items(self, card_db: CardDatabase) -> list[Card]:
        key = (self.class_filter, self.mana_filter, self.search)
        if key != self._cache_key:
            filters: dict[str, object] = {}
            if self.class_filter is not None:
                filters["card_class"] = self.class_filter
            if self.mana_filter == 9:
                filters["min_cost"] = 9
            elif self.mana_filter is not None:
                filters["cost"] = self.mana_filter
            self._cache = card_db.search_cards(self.search, filters)
            self._cache_key = key
        return self._cache

    def context_label(self) -> str:
        class_name = (
            "All" if self.class_filter is None else _CLASS_NAMES[self.class_filter]
        )
        base = f"{class_name} cards"
        if self.search and self.class_filter is None and self.mana_filter is None:
            # The spec pins both comma-composed labels and this verbatim exception:
            # "Mage cards, 3 mana, matching fire" / "All cards matching fire".
            return f"All cards matching {self.search}"
        segments = [base]
        if self.mana_filter is not None:
            segments.append(
                "9 plus mana"
                if self.mana_filter == 9
                else f"{self.mana_filter} mana"
            )
        if self.search:
            segments.append(f"matching {self.search}")
        return ", ".join(segments)


def build_cards(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    card_db: CardDatabase,
    sink: TextModeSink,
) -> ActiveSurface:
    """Build the lazy-singleton Cards Surface and its persistent filters."""
    state = _CardsState()
    engine: HorizontalListEngine | None = None

    def items() -> list[Card]:
        return state.items(card_db)

    def reland() -> None:
        if engine is None:
            raise RuntimeError("Cards engine is not active")
        engine.on_landing()

    def cycle_class(direction: int) -> None:
        values = [value for _label, value in _CLASS_FILTERS]
        index = values.index(state.class_filter)
        state.class_filter = values[(index + direction) % len(values)]
        state.invalidate()
        reland()

    def set_mana_filter(mana: int) -> None:
        state.mana_filter = None if state.mana_filter == mana else mana
        state.invalidate()
        reland()

    def commit_search(value: str) -> None:
        state.search = value
        state.invalidate()
        sink.exit_text_mode()
        reland()

    def abandon_search() -> None:
        sink.exit_text_mode()
        reland()

    def open_search() -> None:
        sink.enter_text_mode(
            TextSession(
                "Search",
                state.search,
                announcer,
                commit_search,
                abandon_search,
            )
        )

    def page(delta: int) -> None:
        if engine is None:
            raise RuntimeError("Cards engine is not active")
        engine.page(delta)

    mana_bindings = [
        Binding(
            Chord(str(mana)),
            Command(
                f"cards.mana.{mana}",
                (
                    "9: show only cards costing 9 or more"
                    if mana == 9
                    else "0 to 8: show only cards of that mana cost"
                ),
                lambda mana=mana: set_mana_filter(mana),
            ),
        )
        for mana in range(10)
    ]
    forward_class = Command(
        "cards.class_cycle",
        "Tab: jump to the next class",
        lambda: cycle_class(1),
    )
    reverse_class = Command(
        "cards.class_cycle",
        "Tab: jump to the next class",
        lambda: cycle_class(-1),
    )
    forward_page = Command(
        "cards.page",
        "Page Down: jump ten cards forward",
        lambda: page(10),
    )
    reverse_page = Command(
        "cards.page",
        "Page Down: jump ten cards forward",
        lambda: page(-10),
    )
    spec = SurfaceSpec(
        "Cards",
        WidgetType.HORIZONTAL_LIST,
        context_label=state.context_label,
        zones=[
            ZoneSpec(
                "cards",
                "Cards",
                items,
                lambda card: card.name,
                _detail_lines,
            )
        ],
        bindings=mana_bindings,
        slot_fills={
            Slot.GROUP_JUMP: forward_class,
            Slot.SEARCH: Command(
                "cards.search",
                "Ctrl+F: search for a card",
                open_search,
            ),
            Slot.COARSE_AXIS: forward_page,
        },
        slot_reverse_fills={
            Slot.GROUP_JUMP: reverse_class,
            Slot.COARSE_AXIS: reverse_page,
        },
        slot_noops={
            Slot.ENTER: "Nothing to do here",
            Slot.LISTEN: "Game audio is not available",
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, HorizontalListEngine):
        raise TypeError("Cards requires a horizontal-list engine")
    engine = surface.engine
    return surface


def _detail_lines(card: Card) -> list[str]:
    lines = [f"{card.cost} mana", _display_enum(card.card_type)]
    if card.card_type == "MINION" and card.attack is not None and card.health is not None:
        lines.append(f"{card.attack} attack, {card.health} health")
    elif (
        card.card_type == "WEAPON"
        and card.attack is not None
        and card.health is not None
    ):
        # Card stores a weapon's durability in health; do not use its legacy field.
        lines.append(f"{card.attack} attack, {card.health} durability")
    if card.text:
        lines.append(card.text)
    if card.card_class:
        lines.append(_CLASS_NAMES.get(card.card_class, _display_enum(card.card_class)))
    if card.rarity:
        lines.append(_display_enum(card.rarity))
    if card.card_set:
        lines.append(card.card_set)
    return lines


def _display_enum(value: str) -> str:
    return value.replace("_", " ").title()
