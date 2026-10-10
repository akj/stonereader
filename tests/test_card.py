"""Card text, set names, and deck eligibility against the real card database."""

from __future__ import annotations

import re

import pytest
from hearthstone.cardxml import load

from stonereader.models.card import CardDatabase, set_name

_MARKUP = re.compile(r"\[[xd]\]|[@$#{}<>|]")


@pytest.fixture(scope="module")
def card_db() -> CardDatabase:
    return CardDatabase.load()


@pytest.mark.parametrize(
    ("card_id", "text"),
    [
        pytest.param(
            "CATA_585",
            "Deal 8 damage to a damaged minion. "
            "Return this to hand with any excess damage.",
            id="at-sign-is-script-data-1",
        ),
        pytest.param(
            "BT_481",
            "Battlecry: Summon two random 0-Cost minions. "
            "(Upgrades each time a friendly minion dies!)",
            id="absent-script-data-is-0",
        ),
        pytest.param(
            "REV_353",
            "Battlecry: Summon a Gargon Companion. "
            "Infuse (4): Summon another. Infuse (8): And another!",
            id="numbered-slots-are-script-data",
        ),
        pytest.param(
            "DAL_007",
            "Summon 1 1/1 Imp. (Upgrades each turn!)",
            id="plural-agrees-with-count-not-stats",
        ),
        pytest.param(
            "DED_504",
            "Tradeable Summon 2 1/1 Imps. (Upgrades by 2 when Traded!)",
            id="plural-many",
        ),
        pytest.param(
            "TRL_316",
            "Battlecry: If your Hero Power dealt 8 damage this game, "
            "summon Ragnaros the Firelord.",
            id="in-game-counter-variants-dropped",
        ),
        pytest.param(
            "CFM_602",
            "Choose One - Summon a Jade Golem; "
            "or Shuffle 3 copies of this card into your deck.",
            id="jade-golem-plain-variant",
        ),
        pytest.param(
            "CATA_131",
            "Battlecry: Gain a temporary Mana Crystal. "
            "If you spent 4 Mana while holding this, it's permanent.",
            id="plain-variant-comes-last",
        ),
        pytest.param(
            "LOOT_051",
            "Deal 2 damage to a minion. (Gain 3 Armor to upgrade.)",
            id="spellstone-note-kept",
        ),
        pytest.param(
            "DRG_600",
            "Battlecry: Summon 1 random Demon.",
            id="bare-counter-dropped",
        ),
        pytest.param(
            "CATA_530",
            "Herald. Your hero has Lifesteal this turn.",
            id="card-reference-is-not-a-count",
        ),
        pytest.param(
            "HERO_06bp",
            "Hero Power +1 Attack this turn. +1 Armor.",
            id="hero-power-attack-and-armor-markers",
        ),
        pytest.param(
            "BG24_Reward_134",
            "At the start of each turn, get 2 random Naga.",
            id="noun-slot-is-a-minion-type-not-a-count",
        ),
        pytest.param(
            "CS2_089",
            "Restore 8 Health to your hero.",
            id="healing-marker",
        ),
    ],
)
def test_card_text_is_the_collection_text_without_markup(
    card_db: CardDatabase, card_id: str, text: str
) -> None:
    card = card_db.get_card_by_id(card_id)

    assert card is not None
    assert card.text == text


def test_no_card_in_the_database_speaks_markup(card_db: CardDatabase) -> None:
    templates, _ = load()
    marked_templates = [
        card.id
        for card in templates.values()
        if _MARKUP.search(card.description or "")
    ]
    marked_texts = {
        card.id: card.text
        for card in card_db.cards_by_id.values()
        if _MARKUP.search(card.text)
    }

    assert len(marked_templates) > 10_000
    assert len(card_db.cards_by_id) == len(templates)
    assert marked_texts == {}


@pytest.mark.parametrize(
    ("card_set", "name"),
    [
        ("CORE", "Core"),
        ("EXPERT1", "Classic"),
        ("ISLAND_VACATION", "Perils in Paradise"),
        ("RETURN_OF_THE_LICH_KING", "March of the Lich King"),
        ("CATACLYSM", "Cataclysm"),
        ("TITANS", "Titans"),
        ("LOOTAPALOOZA", "Kobolds & Catacombs"),
        ("HERO_SKINS", ""),
        ("PLACEHOLDER_202204", ""),
        ("TEST", ""),
    ],
)
def test_set_name_is_the_game_name(card_set: str, name: str) -> None:
    assert set_name(card_set) == name


def test_every_deck_card_set_line_is_a_spoken_name(card_db: CardDatabase) -> None:
    deck_cards = [card for card in card_db.collectible_cards if card.deckable]
    names = {card.card_set: set_name(card.card_set) for card in deck_cards}

    assert sorted(key for key, name in names.items() if not name) == [
        "PLACEHOLDER_202204"
    ]
    assert [
        name for name in names.values() if "_" in name or name.isupper()
    ] == []


def test_deckable_keeps_playable_heroes_and_drops_hero_skins(
    card_db: CardDatabase,
) -> None:
    rexxar = card_db.get_card_by_id("ICC_828")
    alleria = card_db.get_card_by_id("HERO_05a")

    assert rexxar is not None and rexxar.card_type == "HERO" and rexxar.deckable
    assert alleria is not None and alleria.collectible and not alleria.deckable
    assert [
        card.id
        for card in card_db.collectible_cards
        if card.deckable and card.card_set == "HERO_SKINS"
    ] == []
