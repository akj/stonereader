"""Generated help content derived from active Surface declarations."""

from __future__ import annotations

from dataclasses import dataclass

from stonereader.ui._sink_core import BARE_CTRL_HELP_PHRASE
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface
from stonereader.ui.registry import (
    END_JUMP_UNIVERSAL_HELP_PHRASE,
    SLOT_CHORDS,
    SLOT_UNIVERSAL_HELP_PHRASES,
    Command,
    CommandRegistry,
    Slot,
)
from stonereader.ui.surface import SurfaceSpec, WidgetType


@dataclass(frozen=True)
class HelpEntry:
    """One spoken registry phrase and its optional executable command."""

    phrase: str
    command: Command | None


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


def universal_entries(registry: CommandRegistry) -> list[str]:
    """Assemble the complete universal layer in the UI-spec order."""
    bindings = registry.universal_bindings()
    commands_by_chord = dict(bindings)
    included_ids: set[str] = set()

    def registered_phrase(chord: Chord) -> str:
        command = commands_by_chord[chord]
        included_ids.add(command.id)
        return command.help_phrase

    entries = [
        SLOT_UNIVERSAL_HELP_PHRASES[Slot.ENTER],
        registered_phrase(Chord("escape")),
        END_JUMP_UNIVERSAL_HELP_PHRASE,
        SLOT_UNIVERSAL_HELP_PHRASES[Slot.COARSE_AXIS],
        SLOT_UNIVERSAL_HELP_PHRASES[Slot.GROUP_JUMP],
        SLOT_UNIVERSAL_HELP_PHRASES[Slot.SEARCH],
        registered_phrase(Chord("f1")),
        SLOT_UNIVERSAL_HELP_PHRASES[Slot.LISTEN],
        BARE_CTRL_HELP_PHRASE,
    ]
    for _chord, command in bindings:
        if command.id not in included_ids:
            included_ids.add(command.id)
            entries.append(command.help_phrase)
    return entries
