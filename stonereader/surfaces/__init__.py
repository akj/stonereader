"""Declarative application Surface definitions (ADR-0010)."""

from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.cards import build_cards
from stonereader.surfaces.deck_detail import build_deck_detail
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.home import build_home
from stonereader.surfaces.import_deck import ImportDeckField, build_import_deck
from stonereader.surfaces.import_replays import build_import_replays
from stonereader.surfaces.replays import build_replays
from stonereader.surfaces.replay_viewer import CurrentReplay, build_replay_viewer

__all__ = [
    "CurrentDeck",
    "CurrentReplay",
    "DeckData",
    "ImportDeckField",
    "build_deck_detail",
    "build_cards",
    "build_decks",
    "build_home",
    "build_import_deck",
    "build_import_replays",
    "build_replays",
    "build_replay_viewer",
]
