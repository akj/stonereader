from __future__ import annotations

from stonereader.models.game_state import GameEntity, Hero, PlayedCard
from stonereader.surfaces._zone_format import (
    card_detail_lines,
    card_title,
    hero_detail_lines,
)


def _newer_minion() -> GameEntity:
    """A minion whose id the card data lacks; its stats come from game tags."""
    return GameEntity(9, "ZZZ_001", None, "", 0, 5, 3, "MINION", "PLAY", 1, 1)


def test_unrecognized_and_hidden_cards_are_told_apart_never_by_id() -> None:
    newer = PlayedCard(9, "ZZZ_001", None, "", 9, 1)
    hidden = PlayedCard(10, "", None, "", 3, 2)

    assert card_title(newer, with_turn=True) == "Unrecognized card, turn 9"
    assert card_detail_lines(newer) == ["Not in StoneReader's card data yet"]
    assert card_title(hidden, with_turn=True) == "Unknown card, turn 3"
    assert card_detail_lines(_newer_minion()) == [
        "Not in StoneReader's card data yet",
        "5 attack, 3 health",
    ]


def test_hero_details_count_secrets_and_name_an_unrecognized_weapon() -> None:
    hero = Hero("HERO_08", "Jaina", 30, 0, "Fireblast", "MAGE")
    weapon = GameEntity(11, "ZZZ_002", None, "", 0, 3, 2, "WEAPON", "PLAY", 1, 1)

    assert hero_detail_lines(hero, None, 0) == ["Fireblast", "No weapon", "0 secrets"]
    assert hero_detail_lines(hero, weapon, 2) == [
        "Fireblast",
        "Unrecognized card",
        "2 secrets",
    ]
