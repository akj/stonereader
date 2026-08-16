"""Shared Live Game and Replay Viewer Surface declarations."""

from __future__ import annotations

from collections.abc import Callable

from stonereader.models.game_state import GameState, Hero
from stonereader.surfaces._zone_format import (
    CardItem,
    card_detail_lines,
    card_title,
    hero_detail_lines,
)
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.surface import ZoneSpec


StateProvider = Callable[[], GameState | None]


def card_items(
    state: StateProvider,
    attribute: str,
) -> Callable[[], list[CardItem]]:
    def items() -> list[CardItem]:
        current = state()
        return [] if current is None else list(getattr(current, attribute))

    return items


def singleton(
    state: StateProvider,
    attribute: str,
) -> Callable[[], list[CardItem]]:
    def items() -> list[CardItem]:
        current = state()
        if current is None:
            return []
        item = getattr(current, attribute)
        return [] if item is None else [item]

    return items


def hero_items(
    state: StateProvider,
    attribute: str,
) -> Callable[[], list[Hero]]:
    def items() -> list[Hero]:
        current = state()
        return [] if current is None else [getattr(current, attribute)]

    return items


def player_hero_details(state: StateProvider) -> Callable[[Hero], list[str]]:
    return _hero_details(state, "player_weapon", "player_secrets")


def opponent_hero_details(state: StateProvider) -> Callable[[Hero], list[str]]:
    return _hero_details(state, "opponent_weapon", "opponent_secrets")


def card_zone(
    zone_id: str,
    label: str,
    key: str,
    help_phrase: str,
    items: Callable[[], list[CardItem]],
    *,
    shift: bool = False,
    with_turn: bool = False,
) -> ZoneSpec:
    return ZoneSpec(
        zone_id,
        label,
        items,
        lambda item: card_title(item, with_turn=with_turn),
        card_detail_lines,
        Chord(key, shift=shift),
        help_phrase,
    )


def require_engine(
    engine: HorizontalListEngine | None,
    surface_name: str,
) -> HorizontalListEngine:
    if engine is None:
        raise RuntimeError(f"{surface_name} engine is not active")
    return engine


def _hero_details(
    state: StateProvider,
    weapon_attribute: str,
    secrets_attribute: str,
) -> Callable[[Hero], list[str]]:
    def details(hero: Hero) -> list[str]:
        current = state()
        if current is None:
            return []
        return hero_detail_lines(
            hero,
            getattr(current, weapon_attribute),
            len(getattr(current, secrets_attribute)),
        )

    return details
