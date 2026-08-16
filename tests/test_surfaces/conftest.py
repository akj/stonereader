from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from hearthstone.deckstrings import write_deckstring
from hearthstone.enums import FormatType

from stonereader.db import get_connection, init_db
from stonereader.models.card import Card, CardDatabase
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.surface import SurfaceSpec, WidgetType

from tests.support import FakeSpeech


@dataclass
class Harness[T]:
    context: T
    speech: FakeSpeech
    announcer: Announcer
    sink: _SinkCore
    nav: NavigationController
    events: list[str]
    titles: list[str]
    activated: list[ActiveSurface]
    surface: ActiveSurface | None = None

    def set_surface(self, surface: ActiveSurface) -> ActiveSurface:
        """Make a directly built Surface the harness's active test subject."""
        self.surface = surface
        self.sink.set_active(surface.registry)
        return surface

    @property
    def active_surface(self) -> ActiveSurface:
        if self.activated:
            return self.activated[-1]
        if self.surface is None:
            raise RuntimeError("No Surface is active in this harness")
        return self.surface

    @property
    def subject_surface(self) -> ActiveSurface:
        if self.surface is None:
            raise RuntimeError("No directly built Surface is in this harness")
        return self.surface

    @property
    def horizontal(self) -> HorizontalListEngine:
        engine = self.active_surface.engine
        assert isinstance(engine, HorizontalListEngine)
        return engine

    @property
    def vertical(self) -> VerticalMenuEngine:
        engine = self.active_surface.engine
        assert isinstance(engine, VerticalMenuEngine)
        return engine

    def list_engine(self, name: str) -> HorizontalListEngine:
        engine = self.nav.peek(name).engine
        assert isinstance(engine, HorizontalListEngine)
        return engine

    def menu(self, name: str) -> VerticalMenuEngine:
        engine = self.nav.peek(name).engine
        assert isinstance(engine, VerticalMenuEngine)
        return engine

    def press(self, chord: Chord) -> bool:
        return self.sink.handle_chord(chord)

    def type(self, text: str) -> None:
        for character in text:
            if character == " ":
                chord = Chord("space")
            else:
                chord = Chord(
                    character.lower(),
                    shift=character.isalpha() and character.isupper(),
                )
            self.press(chord)


def make_harness[T](context: T) -> Harness[T]:
    """Build the shared speech -> announcer -> sink -> navigation test seam."""
    events: list[str] = []
    titles: list[str] = []
    activated: list[ActiveSurface] = []
    speech = FakeSpeech(events)
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: events.append("stop"))

    def activate(surface: ActiveSurface) -> None:
        activated.append(surface)
        sink.set_active(surface.registry)
        events.append(f"activate:{surface.spec.name}")

    nav = NavigationController(
        titles.append,
        announcer,
        lambda: events.append("stop"),
        activate,
    )
    return Harness(
        context,
        speech,
        announcer,
        sink,
        nav,
        events,
        titles,
        activated,
    )


class LandingEngine:
    def on_landing(self, continues: bool = False) -> None:
        del continues


def placeholder_surface(name: str) -> ActiveSurface:
    return ActiveSurface(
        SurfaceSpec(name, WidgetType.VERTICAL_MENU, options=lambda: []),
        LandingEngine(),
        CommandRegistry(),
    )


@pytest.fixture
def db_conn() -> Iterator[sqlite3.Connection]:
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()


def make_card(
    dbf_id: int,
    name: str,
    *,
    card_class: str = "NEUTRAL",
    card_type: str = "MINION",
    cost: int = 1,
    attack: int | None = None,
    health: int | None = None,
    text: str = "",
    durability: int | None = None,
) -> Card:
    return Card(
        id=f"CARD_{dbf_id}",
        dbf_id=dbf_id,
        name=name,
        cost=cost,
        attack=attack,
        health=health,
        text=text,
        rarity="COMMON",
        card_class=card_class,
        card_type=card_type,
        card_set="TEST",
        durability=durability,
    )


def make_card_db(*cards: Card) -> CardDatabase:
    card_db = CardDatabase()
    for card in cards:
        card_db.cards_by_id[card.id] = card
        card_db.cards_by_dbf_id[card.dbf_id] = card
    return card_db


def make_deckstring(
    cards: list[tuple[int, int]],
    *,
    hero: int = 274,
) -> str:
    return write_deckstring(
        cards=cards,
        heroes=[hero],
        format=FormatType.FT_STANDARD,
    )
