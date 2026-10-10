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
    """One spoken registry phrase and the command Enter performs from help.

    ``command`` is None when the option cannot run from help: Enter and
    Ctrl+F act only in place, and a ``shared`` phrase (the digits) names
    several commands rather than one.
    """

    phrase: str
    command: Command | None
    shared: bool = False


_NON_EXECUTABLE_CHORDS: frozenset[Chord] = frozenset(
    (*SLOT_CHORDS[Slot.ENTER], *SLOT_CHORDS[Slot.SEARCH])
)


def widget_type_sentence(spec: SurfaceSpec) -> str:
    """Generate the ADR-0009 widget-type sentence for ``spec``.

    Help already names the Surface ("Home help, …"), so the sentence names
    only its type (ADR-0017).
    """
    if spec.widget_type is WidgetType.VERTICAL_MENU:
        return "Menu: Up and Down move between options, Enter acts on the current one."
    # ADR-0009 gives Cards as a worked example, not an item-noun field in the
    # Surface contract. The generic generated form therefore says "items".
    return (
        "Horizontal list: Left and Right move between items, "
        "Up and Down read details."
    )


def screen_bindings(surface: ActiveSurface) -> list[HelpEntry]:
    """Return one entry per help phrase of the Surface's bindings and fills.

    Enter's phrase comes first, then the Surface's ``help_first`` chords in
    their declared order, then every other binding in registration order.
    """
    first = {chord: index for index, chord in enumerate(surface.spec.help_first)}

    def rank(binding: tuple[Chord, Command]) -> tuple[int, int]:
        chord = binding[0]
        if chord in SLOT_CHORDS[Slot.ENTER]:
            return (0, 0)
        if chord in first:
            return (1, first[chord])
        return (2, 0)

    groups: dict[str, list[tuple[Chord, Command]]] = {}
    for chord, command in sorted(surface.registry.surface_bindings(), key=rank):
        # Slot no-ops are registry dispatch detail, not filled commands. They
        # do not belong in the screen-specific binding group.
        if command.id.startswith("noop."):
            continue
        groups.setdefault(command.help_phrase, []).append((chord, command))
    return [_entry(phrase, bindings) for phrase, bindings in groups.items()]


def _entry(phrase: str, bindings: list[tuple[Chord, Command]]) -> HelpEntry:
    if len({command.id for _chord, command in bindings}) > 1:
        return HelpEntry(phrase, None, shared=True)
    if any(chord in _NON_EXECUTABLE_CHORDS for chord, _command in bindings):
        return HelpEntry(phrase, None)
    return HelpEntry(phrase, bindings[0][1])


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
