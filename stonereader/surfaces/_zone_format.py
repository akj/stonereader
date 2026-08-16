"""Shared Replay Viewer and Live Game card/hero zone formatting."""

from __future__ import annotations

from typing import TypeAlias

from stonereader.models.card import Card
from stonereader.models.game_state import GameEntity, Hero, PlayedCard


CardItem: TypeAlias = GameEntity | PlayedCard | None


def card_title(item: CardItem, *, with_turn: bool = False) -> str:
    name = card_name(item) or "Unknown card"
    if with_turn and isinstance(item, PlayedCard):
        return f"{name}, turn {item.turn}"
    return name


def card_name(item: CardItem) -> str:
    if item is None:
        return ""
    # A missing entity name is hidden information even if a synthetic or stale
    # base-card reference happens to be present; never reveal through fallback.
    return item.name


def card_detail_lines(item: CardItem) -> list[str]:
    if item is None:
        return []
    card = _base_card(item)
    cost = item.cost if isinstance(item, GameEntity) else (card.cost if card else 0)
    lines = [f"{cost} mana"]
    card_type = (
        item.card_type
        if isinstance(item, GameEntity)
        else (card.card_type if card else "")
    )
    if card_type == "MINION":
        if isinstance(item, GameEntity):
            lines.append(f"{item.current_attack} attack, {item.current_health} health")
        elif card is not None and card.attack is not None and card.health is not None:
            lines.append(f"{card.attack} attack, {card.health} health")
    if isinstance(item, GameEntity):
        for tag, label in (
            ("TAUNT", "Taunt"),
            ("DIVINE_SHIELD", "Divine shield"),
            ("FROZEN", "Frozen"),
        ):
            if item.tags.get(tag):
                lines.append(label)
        if card is not None and card.health is not None and item.current_health < card.health:
            lines.append("Damaged")
    if card is not None and card.text:
        lines.append(card.text)
    if isinstance(item, GameEntity) and item.creation_lineage:
        lines.append(f"Created by {item.creation_lineage}")
    return lines


def hero_title(hero: Hero) -> str:
    title = f"{hero.name}, {hero.health} health"
    if hero.armor:
        title += f", {hero.armor} armor"
    return title


def hero_detail_lines(
    hero: Hero,
    weapon: GameEntity | None,
    secrets: int,
) -> list[str]:
    # The engine does not currently populate Hero.hero_power, so retain the
    # explicit fallback until that data gap is closed.
    power = hero.hero_power or "No hero power"
    weapon_name = card_name(weapon) if weapon is not None else "No weapon"
    return [power, weapon_name or "Unknown card", f"{secrets} secrets"]


def _base_card(item: CardItem) -> Card | None:
    return item.base_card if item is not None else None
