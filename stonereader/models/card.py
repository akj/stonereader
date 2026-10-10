import re
from dataclasses import dataclass, field
from functools import cache
from string import capwords
from typing import Any, Dict, List, Optional, Sequence

from hearthstone.cardxml import load
from hearthstone.enums import CardSet, GameTag
from hearthstone.stringsfile import load_txt
from hearthstone_data import get_strings_file


CARD_CLASS_NAMES: dict[str, str] = {
    "DEMONHUNTER": "Demon Hunter",
    "DEATHKNIGHT": "Death Knight",
    "DRUID": "Druid",
    "HUNTER": "Hunter",
    "MAGE": "Mage",
    "NEUTRAL": "Neutral",
    "PALADIN": "Paladin",
    "PRIEST": "Priest",
    "ROGUE": "Rogue",
    "SHAMAN": "Shaman",
    "WARLOCK": "Warlock",
    "WARRIOR": "Warrior",
}


_SCRIPT_DATA_TAGS = (
    GameTag.TAG_SCRIPT_DATA_NUM_1,
    GameTag.TAG_SCRIPT_DATA_NUM_2,
    GameTag.TAG_SCRIPT_DATA_NUM_3,
    GameTag.TAG_SCRIPT_DATA_NUM_4,
    GameTag.TAG_SCRIPT_DATA_NUM_5,
    GameTag.TAG_SCRIPT_DATA_NUM_6,
)
# An "@" after a sentence or closing markup separates the variants the game
# swaps between during play; anywhere else it stands for the first script-data
# number.
_VARIANT_BREAK = re.compile(r"(?:(?<=[.!?)_\"])|(?<=</[bi]>))\s*@")
# A second variant that is only an italic note, like a Spellstone's
# "(Gain 3 Armor to upgrade.)", is part of the collection text.
_NOTE = re.compile(r"\s*<i>\([^@{}]*\)</i>\s*")
_SLOT = re.compile(r"\{(\d+)\}")
_PLURAL = re.compile(r"\|4\s*\(([^,)]*),([^)]*)\)")
_STANDALONE_NUMBER = re.compile(r"(?<![\d/])\d+(?![\d/])")
# Script data this large names a card by DBF ID rather than counting anything.
_LARGEST_COUNT = 999


def _card_text(template: str, script_data: Sequence[Optional[int]]) -> str:
    """Return card text as the collection shows it, with every marker resolved.

    Hearthstone card text is a template: "[x]" marks manual line breaks, "_" is
    a non-breaking space, "$" and "#" mark numbers that spell damage and
    healing modify, "{n}" and a bare "@" are filled from script data, an "@"
    after a sentence separates in-play variants, and "|4(card,cards)" agrees
    with the nearest number. The first variant is the collection text unless it
    has "{n}" slots for game state, such as a Jade Golem's size or "(3 left!)";
    then the plain variant, which comes last, is.
    """
    variants = _VARIANT_BREAK.split(re.sub(r"\[[xd]\]", "", template))
    text = variants[0]
    if _SLOT.search(text):
        text = next((v for v in reversed(variants) if not _SLOT.search(v)), text)
    elif len(variants) == 2 and _NOTE.fullmatch(variants[1]):
        text = f"{text} {variants[1]}"

    def script_number(index: int) -> Optional[int]:
        value = script_data[index] if index < len(script_data) else None
        return value if value is not None and value <= _LARGEST_COUNT else None

    slots = [script_number(int(index)) for index in _SLOT.findall(text)]
    if all(value is not None for value in slots):
        text = _SLOT.sub(lambda match: str(script_number(int(match.group(1)))), text)
    else:
        text = _SLOT.sub("", text)
    first = script_number(0)
    if first is None:
        # A bare "(@)" is a live counter with nothing to show outside a game.
        text = re.sub(r"(?:<i>)?\(@\)(?:</i>)?", "", text)
    text = text.replace("@", str(first or 0))
    text = _PLURAL.sub(lambda match: _agree(match, text), text)
    # ">/b>" is a closing-tag typo in the card data.
    text = re.sub(r"<[^>]+>|>/[bi]>", "", text)
    text = re.sub(r"[$#][ad]?(?=\d)|[$#{}]", "", text)
    text = text.replace("_", " ")
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r" (?=[,!?:;)]|\.(?!\.))", "", text)
    # Dropped slots can orphan the punctuation that joined them.
    return text.strip().lstrip(",;: ")


def _agree(match: re.Match[str], text: str) -> str:
    """Pick the singular or plural of a "|4(a,b)" choice by its nearest number."""
    before = _STANDALONE_NUMBER.findall(text, 0, match.start())
    after = _STANDALONE_NUMBER.findall(text, match.start())
    number = before[-1] if before else (after[0] if after else "")
    return (match.group(1) if number == "1" else match.group(2)).strip()


@cache
def _global_strings() -> dict[str, str]:
    """Return Hearthstone's English global strings by ID (GLOBAL.txt)."""
    with get_strings_file("enUS", "GLOBAL.txt").open(encoding="utf-8-sig") as strings:
        rows = load_txt(strings)
    return {key: row["TEXT"] for key, row in rows.items() if row.get("TEXT")}


# Newer sets whose global string ID the hearthstone package does not map yet.
_SET_NAME_KEYS = {
    "REVENDRETH": "GLOBAL_CARD_SET_REV",
    "RETURN_OF_THE_LICH_KING": "GLOBAL_CARD_SET_RLK",
    "PATH_OF_ARTHAS": "GLOBAL_CARD_SET_PA",
    "BATTLE_OF_THE_BANDS": "GLOBAL_CARD_SET_ETC",
    "TITANS": "GLOBAL_CARD_SET_TTN",
    "WONDERS": "GLOBAL_CARD_SET_WON",
    "WHIZBANGS_WORKSHOP": "GLOBAL_CARD_SET_TOY",
    "TUTORIAL": "GLOBAL_CARD_SET_TUT",
    "EVENT": "GLOBAL_CARD_SET_EVE",
    "ISLAND_VACATION": "GLOBAL_CARD_SET_VAC",
    "SPACE": "GLOBAL_CARD_SET_GDB",
    "EMERALD_DREAM": "GLOBAL_CARD_SET_EDR",
    "THE_LOST_CITY": "GLOBAL_CARD_SET_TLC",
    "TIME_TRAVEL": "GLOBAL_CARD_SET_TIME",
    "CATACLYSM": "GLOBAL_CARD_SET_CATA",
}


def set_name(card_set: str) -> str:
    """Return a card set's spoken name, or "" when the game data names none.

    CORE is "Core"; HERO_SKINS and the internal placeholder sets have no name.
    """
    key = _SET_NAME_KEYS.get(card_set)
    if key is None and card_set in CardSet.__members__:
        key = CardSet[card_set].name_global
    name = _global_strings().get(key or "", "")
    # The game styles a few names in capitals ("TITANS"); screen readers would
    # treat them as shouting or acronyms.
    return capwords(name) if name.isupper() else name


_DECK_CARD_TYPES = frozenset({"HERO", "LOCATION", "MINION", "SPELL", "WEAPON"})


@dataclass(frozen=True)
class Card:
    """Represents a Hearthstone card with complete tag access."""

    id: str
    dbf_id: int
    name: str
    cost: int
    attack: Optional[int]
    health: Optional[int]
    text: str
    rarity: str
    card_class: str
    card_type: str
    card_set: str = ""
    collectible: bool = True
    durability: Optional[int] = None
    spell_school: str = ""
    flavor_text: str = ""
    artist: str = ""
    rune_blood: int = 0
    rune_frost: int = 0
    rune_unholy: int = 0
    tags: Dict[str, Any] = field(default_factory=dict)

    def has_tag(self, tag_name: str) -> bool:
        if not self.tags:
            return False
        return bool(self.tags.get(tag_name, 0))

    def get_tag(self, tag_name: str, default: Any = None) -> Any:
        if not self.tags:
            return default
        return self.tags.get(tag_name, default)

    @property
    def deckable(self) -> bool:
        """Return whether a deck can hold this card; hero skins are cosmetic."""
        return (
            self.collectible
            and self.card_type in _DECK_CARD_TYPES
            and self.card_set != "HERO_SKINS"
        )

    @classmethod
    def from_cardxml(cls, cardxml_card: Any) -> "Card":
        tags_dict: Dict[str, Any] = {}
        rune_blood = 0
        rune_frost = 0
        rune_unholy = 0
        script_data: list[Optional[int]] = []
        if hasattr(cardxml_card, "tags") and cardxml_card.tags:
            for tag_enum, value in cardxml_card.tags.items():
                tag_name = tag_enum.name if hasattr(tag_enum, "name") else str(tag_enum)
                tags_dict[tag_name] = value
            rune_blood = cardxml_card.tags.get(GameTag.COST_BLOOD, 0)
            rune_frost = cardxml_card.tags.get(GameTag.COST_FROST, 0)
            rune_unholy = cardxml_card.tags.get(GameTag.COST_UNHOLY, 0)
            script_data = [cardxml_card.tags.get(tag) for tag in _SCRIPT_DATA_TAGS]

        spell_school = ""
        if getattr(cardxml_card, "spell_school", None):
            ss = cardxml_card.spell_school
            spell_school = ss.name if hasattr(ss, "name") else str(ss)

        return cls(
            id=cardxml_card.id,
            dbf_id=cardxml_card.dbf_id if hasattr(cardxml_card, "dbf_id") else 0,
            name=cardxml_card.name or "",
            cost=cardxml_card.cost or 0,
            attack=cardxml_card.atk if cardxml_card.atk else None,
            health=cardxml_card.health if cardxml_card.health else None,
            text=_card_text(cardxml_card.description or "", script_data),
            rarity=cardxml_card.rarity.name if cardxml_card.rarity else "COMMON",
            card_class=(
                cardxml_card.card_class.name if cardxml_card.card_class else "NEUTRAL"
            ),
            card_type=cardxml_card.type.name if cardxml_card.type else "MINION",
            card_set=cardxml_card.card_set.name if cardxml_card.card_set else "",
            collectible=bool(cardxml_card.collectible),
            durability=cardxml_card.durability if cardxml_card.durability else None,
            spell_school=spell_school,
            flavor_text=getattr(cardxml_card, "flavortext", "") or "",
            artist=getattr(cardxml_card, "artist", "") or "",
            rune_blood=rune_blood,
            rune_frost=rune_frost,
            rune_unholy=rune_unholy,
            tags=tags_dict,
        )

    def to_speech_text(self) -> str:
        """Return card name only for navigation announcements (DL-004)."""
        return self.name

    def detail_lines(self) -> list[str]:
        """Return ordered detail lines for Up/Down inspection.

        Order matches HearthstoneAccess convention:
        name, cost, runes (DK), stats, text, spell school, type,
        rarity, set, flavor, artist.
        """
        lines = [
            self.name,
            f"{self.cost} mana",
        ]
        # Runes (Death Knight only)
        runes: list[str] = []
        if self.rune_blood:
            runes.append(f"{self.rune_blood} blood")
        if self.rune_frost:
            runes.append(f"{self.rune_frost} frost")
        if self.rune_unholy:
            runes.append(f"{self.rune_unholy} unholy")
        if runes:
            lines.append(", ".join(runes))
        # Stats — varies by card type
        if self.card_type == "WEAPON":
            # Weapons: health field holds durability
            if self.attack is not None and self.health is not None:
                lines.append(f"{self.attack} attack, {self.health} durability")
            elif self.attack is not None:
                lines.append(f"{self.attack} attack")
        elif self.attack is not None and self.health is not None:
            lines.append(f"{self.attack} attack, {self.health} health")
        elif self.attack is not None:
            lines.append(f"{self.attack} attack")
        elif self.health is not None:
            lines.append(f"{self.health} health")
        # Card text
        if self.text:
            lines.append(self.text)
        # Spell school
        if self.spell_school:
            lines.append(self.spell_school.lower())
        # Type
        lines.append(self.card_type.lower())
        # Rarity
        lines.append(self.rarity.lower())
        # Set
        if spoken_set := set_name(self.card_set):
            lines.append(spoken_set)
        # Flavor text
        if self.flavor_text:
            lines.append(self.flavor_text)
        # Artist
        if self.artist:
            lines.append(self.artist)
        return lines


@dataclass
class CardDatabase:
    """Card database with indexed lookups and search."""

    cards_by_id: Dict[str, Card] = field(default_factory=dict)
    cards_by_dbf_id: Dict[int, Card] = field(default_factory=dict)
    cards_by_name: Dict[str, Card] = field(default_factory=dict)
    cards_by_class: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_type: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_set: Dict[str, List[Card]] = field(default_factory=dict)
    cards_by_cost: Dict[int, List[Card]] = field(default_factory=dict)
    collectible_cards: List[Card] = field(default_factory=list)

    @classmethod
    def load(cls) -> "CardDatabase":
        db, _ = load()
        card_db = cls()
        for card_data in db.values():
            card = Card.from_cardxml(card_data)
            card_db.cards_by_id[card.id] = card
            card_db.cards_by_dbf_id[card.dbf_id] = card
            card_db.cards_by_name[card.name.lower()] = card
            card_db.cards_by_class.setdefault(card.card_class, []).append(card)
            card_db.cards_by_type.setdefault(card.card_type, []).append(card)
            card_db.cards_by_set.setdefault(card.card_set, []).append(card)
            card_db.cards_by_cost.setdefault(card.cost, []).append(card)
            if card.collectible:
                card_db.collectible_cards.append(card)
        return card_db

    def get_card_by_id(self, card_id: str) -> Optional[Card]:
        return self.cards_by_id.get(card_id)

    def get_card_by_dbf_id(self, dbf_id: int) -> Optional[Card]:
        return self.cards_by_dbf_id.get(dbf_id)

    def get_card_by_name(self, name: str) -> Optional[Card]:
        return self.cards_by_name.get(name.lower())

    def deck_cards(self) -> List[Card]:
        """Return the cards a deck can hold, one printing per name.

        A printing from a named set beats one from an unnamed placeholder set,
        a current printing beats the Classic format's copy, and then the newest
        printing wins.
        """
        printings: Dict[str, Card] = {}
        for card in self.collectible_cards:
            if not card.deckable:
                continue
            name = card.name.casefold()
            kept = printings.get(name)
            if kept is None or _printing_rank(card) > _printing_rank(kept):
                printings[name] = card
        return list(printings.values())

    def search_cards(
        self, query: str = "", filters: Optional[Dict[str, Any]] = None
    ) -> List[Card]:
        if filters is None:
            filters = {}
        candidates = self.deck_cards()
        if "card_class" in filters:
            candidates = [c for c in candidates if c.card_class == filters["card_class"]]
        if "card_type" in filters:
            candidates = [c for c in candidates if c.card_type == filters["card_type"]]
        if "card_set" in filters:
            candidates = [c for c in candidates if c.card_set == filters["card_set"]]
        if "cost" in filters:
            candidates = [c for c in candidates if c.cost == filters["cost"]]
        if "min_cost" in filters:
            candidates = [c for c in candidates if c.cost >= filters["min_cost"]]
        if "max_cost" in filters:
            candidates = [c for c in candidates if c.cost <= filters["max_cost"]]
        if "rarity" in filters:
            candidates = [c for c in candidates if c.rarity == filters["rarity"]]
        if query:
            query_lower = query.lower()
            candidates = [
                c
                for c in candidates
                if query_lower in c.name.lower() or query_lower in c.text.lower()
            ]
        return sorted(candidates, key=card_sort_key)

    def get_cards_by_class(self, card_class: str) -> List[Card]:
        return self.cards_by_class.get(card_class, [])

    def get_cards_by_type(self, card_type: str) -> List[Card]:
        return self.cards_by_type.get(card_type, [])

    def get_cards_by_cost(self, cost: int) -> List[Card]:
        return self.cards_by_cost.get(cost, [])

    def get_cards_by_set(self, card_set: str) -> List[Card]:
        return self.cards_by_set.get(card_set, [])

    def total_cards(self) -> int:
        return len(self.cards_by_id)

    def total_collectible_cards(self) -> int:
        return len(self.collectible_cards)


def _printing_rank(card: Card) -> tuple[bool, bool, int]:
    """Rank printings of one name: named set, then not Classic format, then DBF ID."""
    # VANILLA reprints the 2014 cards for the Classic format; its DBF IDs are
    # newer than the current printings whose text and cost it predates.
    return bool(set_name(card.card_set)), card.card_set != "VANILLA", card.dbf_id


def card_sort_key(card: Card) -> tuple[int, str, int]:
    """Order collections and deck contents by mana, name, then printing."""
    return card.cost, card.name.casefold(), card.dbf_id
