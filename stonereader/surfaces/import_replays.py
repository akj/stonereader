"""Import Replays form Surface."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from stonereader.services._replay_store import ReplayImportError
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType


class ImportResult(Protocol):
    @property
    def created(self) -> bool: ...


class ReplayImporter(Protocol):
    def import_file(
        self,
        src_path: Path,
        *,
        source: str,
        in_stats: bool,
    ) -> ImportResult: ...


def build_import_replays(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    store: ReplayImporter,
    choose_files: Callable[[], list[str]],
) -> ActiveSurface:
    """Build the persistent three-option batch import form."""
    engine: VerticalMenuEngine | None = None
    chosen: list[str] = []
    count_in_stats = False

    def chosen_title() -> str:
        if not chosen:
            return "Choose files, none chosen"
        noun = "file" if len(chosen) == 1 else "files"
        return f"Choose files, {len(chosen)} {noun} chosen"

    def stats_title() -> str:
        return f"Count in stats, {'on' if count_in_stats else 'off'}"

    def choose() -> None:
        picked = choose_files()
        if not picked:
            return
        chosen[:] = picked
        if engine is None:
            raise RuntimeError("Import Replays engine is not active")
        engine.on_landing()

    def toggle_stats() -> None:
        nonlocal count_in_stats
        count_in_stats = not count_in_stats
        announcer.moved(stats_title())

    def import_chosen() -> None:
        if not chosen:
            announcer.noop("No files chosen")
            return
        created = 0
        duplicates = 0
        failed = 0
        for path in chosen:
            try:
                result = store.import_file(
                    Path(path),
                    source="manual_import",
                    in_stats=count_in_stats,
                )
            except ReplayImportError:
                failed += 1
            else:
                if result.created:
                    created += 1
                else:
                    duplicates += 1
        chosen.clear()
        announcer.import_replays_result(created, duplicates, failed)
        nav.back(continues=True)

    options = [
        MenuOption("choose_files", chosen_title, choose),
        MenuOption("count_in_stats", stats_title, toggle_stats),
        MenuOption("import", lambda: "Import", import_chosen),
    ]

    def activate_current() -> None:
        if engine is None:
            raise RuntimeError("Import Replays engine is not active")
        if not engine.activate_current():
            announcer.noop("Nothing to do here")

    spec = SurfaceSpec(
        "Import Replays",
        WidgetType.VERTICAL_MENU,
        options=lambda: options,
        slot_fills={
            Slot.ENTER: Command(
                "import_replays.activate",
                "Enter: edit this field, or run this action",
                activate_current,
            )
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Import Replays requires a vertical-menu engine")
    engine = surface.engine
    return surface
