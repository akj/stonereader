from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from stonereader.services._replay_store import ReplayImportError, ReplayStore
from stonereader.surfaces.import_replays import build_import_replays
from stonereader.surfaces.replay_viewer import CurrentReplay
from stonereader.surfaces.replays import build_replays
from stonereader.ui.chords import Chord

from .conftest import Harness, make_card_db, make_harness


@dataclass(frozen=True)
class Outcome:
    created: bool


class FakeStore:
    def __init__(self, outcomes: list[bool | Exception] | None = None) -> None:
        self.outcomes = list(outcomes or [])
        self.imported: list[tuple[str, str, bool]] = []

    def all_replays(self):
        return []

    def import_file(
        self,
        src_path: Path,
        *,
        source: str,
        in_stats: bool,
    ) -> Outcome:
        self.imported.append((str(src_path), source, in_stats))
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if isinstance(outcome, Exception):
            raise outcome
        return Outcome(outcome)


def _harness(
    selections: list[list[str]],
    outcomes: list[bool | Exception] | None = None,
) -> Harness[FakeStore]:
    store = FakeStore(outcomes)
    harness = make_harness(store)
    picks = list(selections)

    def choose_files() -> list[str]:
        return picks.pop(0)

    harness.nav.register(
        "Replays",
        lambda: build_replays(
            harness.announcer,
            [],
            harness.nav,
            cast(ReplayStore, store),
            make_card_db(),
            CurrentReplay(),
        ),
    )
    harness.nav.register(
        "Import Replays",
        lambda: build_import_replays(
            harness.announcer,
            [],
            harness.nav,
            store,
            choose_files,
        ),
    )
    harness.nav.jump("Replays")
    harness.press(Chord("enter"))
    harness.speech.calls.clear()
    return harness


def test_choose_files_cancel_keeps_previous_selection_and_relands():
    harness = _harness(
        [["one.hsreplay", "two.xml"], []]
    )

    harness.press(Chord("enter"))
    assert harness.vertical.options_snapshot()[0][0] == "Choose files, 2 files chosen"
    assert harness.speech.calls == [
        ("Import Replays, Choose files, 2 files chosen", True)
    ]

    before_cancel = list(harness.speech.calls)
    harness.press(Chord("enter"))
    assert harness.vertical.options_snapshot()[0][0] == "Choose files, 2 files chosen"
    assert harness.speech.calls == before_cancel


def test_one_selected_file_uses_singular_title():
    harness = _harness([["one.hsreplay"]])

    harness.press(Chord("enter"))

    assert harness.vertical.options_snapshot()[0][0] == "Choose files, 1 file chosen"


def test_toggle_announces_dynamic_title_and_applies_to_every_file():
    harness = _harness(
        [["one.hsreplay", "two.xml"]], [True, True]
    )
    harness.press(Chord("enter"))
    harness.press(Chord("down"))

    harness.press(Chord("enter"))

    assert harness.vertical.options_snapshot()[0][1] == "Count in stats, on"
    assert harness.speech.calls[-1] == ("Count in stats, on", True)
    harness.press(Chord("down"))
    harness.press(Chord("enter"))
    assert harness.context.imported == [
        ("one.hsreplay", "manual_import", True),
        ("two.xml", "manual_import", True),
    ]


def test_empty_import_is_refused_and_stays_on_form():
    harness = _harness([])
    harness.press(Chord("end"))

    harness.press(Chord("enter"))

    assert harness.context.imported == []
    assert harness.nav.stack == ("Home", "Replays", "Import Replays")
    assert harness.speech.calls[-1] == ("No files chosen", True)


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([True, True], "2 imported"),
        ([False, False], "2 already in Replays"),
        (
            [ReplayImportError("bad"), ReplayImportError("worse")],
            "2 failed",
        ),
        (
            [True, False, ReplayImportError("bad")],
            "1 imported, 1 already in Replays, 1 failed",
        ),
    ],
)
def test_summary_composition_and_continuing_back_to_replays(outcomes, expected):
    files = [f"replay-{index}.xml" for index in range(len(outcomes))]
    harness = _harness([files], outcomes)
    harness.press(Chord("enter"))
    harness.press(Chord("end"))

    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home", "Replays")
    assert harness.speech.calls[-2:] == [
        (expected, True),
        ("Replays, Import replays…, 1 of 1", False),
    ]
    assert harness.menu("Import Replays").options_snapshot()[0][0] == (
        "Choose files, none chosen"
    )


def test_delete_and_space_are_unbound():
    harness = _harness([])

    assert harness.press(Chord("delete")) is False
    assert harness.press(Chord("space")) is False
    assert harness.speech.calls == []
