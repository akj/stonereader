from __future__ import annotations

from dataclasses import dataclass

import pytest

from stonereader.services._replay_store import ReplayImportError
from stonereader.surfaces.import_replays import build_import_replays
from stonereader.surfaces.replays import build_replays
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import NavigationController

from tests.test_ui.conftest import FakeSpeech


@dataclass(frozen=True)
class Outcome:
    created: bool


class FakeStore:
    def __init__(self, outcomes: list[bool | Exception] | None = None) -> None:
        self.outcomes = list(outcomes or [])
        self.imported: list[tuple[str, str, bool]] = []

    def all_replays(self):
        return []

    def import_file(self, path, *, source: str, in_stats: bool):
        self.imported.append((str(path), source, in_stats))
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if isinstance(outcome, Exception):
            raise outcome
        return Outcome(outcome)


def _harness(
    selections: list[list[str]],
    outcomes: list[bool | Exception] | None = None,
):
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    store = FakeStore(outcomes)
    picks = list(selections)

    def choose_files() -> list[str]:
        return picks.pop(0)

    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    nav.register("Replays", lambda: build_replays(announcer, [], nav, store))
    nav.register(
        "Import Replays",
        lambda: build_import_replays(
            announcer,
            [],
            nav,
            store,
            choose_files,
        ),
    )
    nav.jump("Replays")
    sink.handle_chord(Chord("enter"))
    surface = nav._surfaces["Import Replays"]
    assert isinstance(surface.engine, VerticalMenuEngine)
    speech.calls.clear()
    return nav, sink, speech, store, surface.engine


def test_choose_files_cancel_keeps_previous_selection_and_relands():
    _nav, sink, speech, _store, engine = _harness(
        [["one.hsreplay", "two.xml"], []]
    )

    sink.handle_chord(Chord("enter"))
    assert engine.options_snapshot()[0][0] == "Choose files, 2 files chosen"
    assert speech.calls == [
        ("Import Replays, Choose files, 2 files chosen", True)
    ]

    before_cancel = list(speech.calls)
    sink.handle_chord(Chord("enter"))
    assert engine.options_snapshot()[0][0] == "Choose files, 2 files chosen"
    assert speech.calls == before_cancel


def test_toggle_announces_dynamic_title_and_applies_to_every_file():
    _nav, sink, speech, store, engine = _harness(
        [["one.hsreplay", "two.xml"]], [True, True]
    )
    sink.handle_chord(Chord("enter"))
    sink.handle_chord(Chord("down"))

    sink.handle_chord(Chord("enter"))

    assert engine.options_snapshot()[0][1] == "Count in stats, on"
    assert speech.calls[-1] == ("Count in stats, on", True)
    sink.handle_chord(Chord("down"))
    sink.handle_chord(Chord("enter"))
    assert store.imported == [
        ("one.hsreplay", "manual_import", True),
        ("two.xml", "manual_import", True),
    ]


def test_empty_import_is_refused_and_stays_on_form():
    nav, sink, speech, store, _engine = _harness([])
    sink.handle_chord(Chord("end"))

    sink.handle_chord(Chord("enter"))

    assert store.imported == []
    assert nav.stack == ("Home", "Replays", "Import Replays")
    assert speech.calls[-1] == ("No files chosen", True)


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([True, True], "2 imported"),
        ([False, False], "0 imported, 2 already in Replays"),
        (
            [ReplayImportError("bad"), ReplayImportError("worse")],
            "0 imported, 2 failed",
        ),
        (
            [True, False, ReplayImportError("bad")],
            "1 imported, 1 already in Replays, 1 failed",
        ),
    ],
)
def test_summary_composition_and_queued_back_to_replays(outcomes, expected):
    files = [f"replay-{index}.xml" for index in range(len(outcomes))]
    nav, sink, speech, _store, engine = _harness([files], outcomes)
    sink.handle_chord(Chord("enter"))
    sink.handle_chord(Chord("end"))

    sink.handle_chord(Chord("enter"))

    assert nav.stack == ("Home", "Replays")
    assert speech.calls[-2:] == [
        (expected, True),
        ("Replays, Import replays…, 1 of 1", False),
    ]
    assert engine.options_snapshot()[0][0] == "Choose files, none chosen"


def test_delete_and_space_are_unbound():
    _nav, sink, speech, _store, _engine = _harness([])

    assert sink.handle_chord(Chord("delete")) is False
    assert sink.handle_chord(Chord("space")) is False
    assert speech.calls == []
