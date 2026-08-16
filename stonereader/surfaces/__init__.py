"""Declarative application Surface definitions (ADR-0010)."""

from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.deck_detail import build_deck_detail
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.home import build_home
from stonereader.surfaces.import_deck import ImportDeckField, build_import_deck

__all__ = [
    "CurrentDeck",
    "DeckData",
    "ImportDeckField",
    "build_deck_detail",
    "build_decks",
    "build_home",
    "build_import_deck",
]
