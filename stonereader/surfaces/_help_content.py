"""Generated help content derived from active Surface declarations."""

from __future__ import annotations

from dataclasses import dataclass

from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface
from stonereader.ui.registry import SLOT_CHORDS, Command, Slot
from stonereader.ui.surface import SurfaceSpec, WidgetType


@dataclass(frozen=True)
class HelpEntry:
    """One spoken registry phrase and its optional executable command."""

    phrase: str
    command: Command | None


UNIVERSAL_HELP_ENTRIES = (
    "Enter: act on the current item",
    "Escape or Backspace: go back",
    "Home and End: jump to the ends",
    "Page Up and Page Down: pages or turns where the screen has them",
    "Tab and Shift+Tab: jump between groups where the screen has them",
    "Ctrl+F: search where the screen has it",
    "F1: help for this screen",
    "L: listen to a card's sounds",
    "Ctrl: stop game audio",
    "Ctrl+Q: quit StoneReader",
)

_NON_EXECUTABLE_CHORDS: frozenset[Chord] = frozenset(
    (*SLOT_CHORDS[Slot.ENTER], *SLOT_CHORDS[Slot.SEARCH])
)


def widget_type_sentence(spec: SurfaceSpec) -> str:
    """Generate the ADR-0009 widget-type sentence for ``spec``."""
    if spec.widget_type is WidgetType.VERTICAL_MENU:
        return (
            f"{spec.name} is a menu: Up and Down move between options, "
            "Enter acts on the current one."
        )
    # ADR-0009 gives Cards as a worked example, not an item-noun field in the
    # Surface contract. The generic generated form therefore says "items".
    return (
        f"{spec.name} is a horizontal list: Left and Right move between "
        "items, Up and Down read details."
    )


def screen_bindings(surface: ActiveSurface) -> list[HelpEntry]:
    """Return deduplicated Surface bindings and real slot fills in order."""
    entries: list[HelpEntry] = []
    seen_ids: set[str] = set()
    for chord, command in surface.registry.surface_bindings():
        if command.id in seen_ids:
            continue
        seen_ids.add(command.id)
        # Slot no-ops are registry dispatch detail, not filled commands. They
        # do not belong in the screen-specific binding group.
        if command.id.startswith("noop."):
            continue
        entries.append(
            HelpEntry(
                command.help_phrase,
                None if chord in _NON_EXECUTABLE_CHORDS else command,
            )
        )
    return entries


def universal_entries() -> list[str]:
    """Return the fixed app-wide key layer in its specified order."""
    return list(UNIVERSAL_HELP_ENTRIES)
