"""Layered command dispatch and universal slots (ADR-0009, ADR-0010)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import cast

from stonereader.ui.chords import Chord


class Layer(Enum):
    """Registry precedence, from highest to lowest."""

    UNIVERSAL = auto()
    WIDGET_TYPE = auto()
    SURFACE = auto()


@dataclass(frozen=True)
class Command:
    """Executable behavior and the phrase generated help speaks for it."""

    id: str
    help_phrase: str
    handler: Callable[[], None]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Command id must not be empty")
        if not self.help_phrase:
            raise ValueError("Command help phrase must not be empty")


class Slot(Enum):
    """The exhaustive set of universal keys with per-Surface behavior."""

    ENTER = auto()
    GROUP_JUMP = auto()
    SEARCH = auto()
    COARSE_AXIS = auto()
    LISTEN = auto()


SLOT_CHORDS: dict[Slot, tuple[Chord, ...]] = {
    Slot.ENTER: (Chord("enter"),),
    Slot.GROUP_JUMP: (Chord("tab"), Chord("tab", shift=True)),
    Slot.SEARCH: (Chord("f", ctrl=True),),
    Slot.COARSE_AXIS: (Chord("pageup"), Chord("pagedown")),
    Slot.LISTEN: (Chord("l"),),
}

SLOT_DEFAULT_PHRASES: dict[Slot, str] = {
    Slot.ENTER: "Nothing to do here",
    Slot.GROUP_JUMP: "No groups on this screen",
    Slot.SEARCH: "No search on this screen",
    Slot.COARSE_AXIS: "No pages on this screen",
    Slot.LISTEN: "No card focused",
}

_SLOT_BY_CHORD = {
    chord: slot for slot, chords in SLOT_CHORDS.items() for chord in chords
}
_RESERVED_OFFER = Chord("enter", ctrl=True)
_RESERVED_BACK = (Chord("escape"), Chord("backspace"))


class RegistrationError(Exception):
    """A binding would violate a registry invariant."""


@dataclass(frozen=True)
class DispatchResult:
    """The outcome the input sink needs to route a keypress."""

    handled: bool
    announce: str | None = None


class CommandRegistry:
    """One activated Surface's immutable-by-convention command lookup."""

    def __init__(
        self,
        universal_bindings: Mapping[Chord, Command]
        | Iterable[tuple[Chord, Command]] = (),
    ) -> None:
        self._bindings: dict[Layer, dict[Chord, Command]] = {
            layer: {} for layer in Layer
        }
        self._orders: dict[Layer, list[tuple[Chord, Command]]] = {
            layer: [] for layer in Layer
        }
        self._surface_order: list[tuple[Chord, Command]] = []
        self._slot_fills: dict[Slot, Command] = {}
        self._slot_noops: dict[Slot, str] = {}
        items: Iterable[tuple[Chord, Command]]
        if isinstance(universal_bindings, Mapping):
            items = cast(
                Mapping[Chord, Command], universal_bindings
            ).items()
        else:
            items = cast(Iterable[tuple[Chord, Command]], universal_bindings)
        for chord, command in items:
            self.register(Layer.UNIVERSAL, chord, command)

    def register(self, layer: Layer, chord: Chord, command: Command) -> None:
        """Register one binding while enforcing the layer and reserved seams."""
        if chord == _RESERVED_OFFER:
            raise RegistrationError("ctrl+enter is reserved for Offer acceptance")
        if chord in _RESERVED_BACK:
            raise RegistrationError(
                "escape and backspace may only be installed by navigation"
            )
        if chord in _SLOT_BY_CHORD:
            if layer is Layer.SURFACE:
                raise RegistrationError("Surface slot chords require fill_slot")
            if layer is Layer.WIDGET_TYPE:
                raise RegistrationError("Widget-type bindings cannot shadow a slot")
            raise RegistrationError("Slot chords are fixed by the universal layer")

        existing_layer = self._layer_for(chord)
        if existing_layer is not None:
            if _precedence(layer) > _precedence(existing_layer):
                raise RegistrationError(
                    f"{layer.name} cannot shadow {existing_layer.name} for {chord}"
                )
            raise RegistrationError(f"Chord already registered: {chord}")

        self._store(layer, chord, command)

    def register_back(self, handler: Callable[[], None]) -> None:
        """Install the navigation controller's reserved Back command."""
        if any(self._layer_for(chord) is not None for chord in _RESERVED_BACK):
            raise RegistrationError("Back is already registered")
        command = Command("back", "Go back", handler)
        for chord in _RESERVED_BACK:
            self._store(Layer.UNIVERSAL, chord, command)

    def fill_slot(self, slot: Slot, command: Command) -> None:
        """Fill one universal slot with real Surface behavior."""
        self._ensure_slot_unfilled(slot)
        self._slot_fills[slot] = command
        self._surface_order.extend((chord, command) for chord in SLOT_CHORDS[slot])

    def fill_slot_noop(self, slot: Slot, phrase: str) -> None:
        """Override a slot default with a Surface-specific announced no-op."""
        if not phrase:
            raise ValueError("Announced no-op phrase must not be empty")
        self._ensure_slot_unfilled(slot)
        self._slot_noops[slot] = phrase
        command = Command(f"noop.{slot.name.lower()}", phrase, _do_nothing)
        self._surface_order.extend((chord, command) for chord in SLOT_CHORDS[slot])

    def dispatch(self, chord: Chord) -> DispatchResult:
        """Resolve and execute one normalized chord."""
        slot = _SLOT_BY_CHORD.get(chord)
        if slot is not None:
            command = self._slot_fills.get(slot)
            if command is not None:
                command.handler()
                return DispatchResult(handled=True)
            phrase = self._slot_noops.get(slot, SLOT_DEFAULT_PHRASES[slot])
            return DispatchResult(handled=True, announce=phrase)

        for layer in Layer:
            command = self._bindings[layer].get(chord)
            if command is not None:
                command.handler()
                return DispatchResult(handled=True)
        return DispatchResult(handled=False)

    def surface_bindings(self) -> list[tuple[Chord, Command]]:
        """Return Surface bindings and slot fills in registration order."""
        return list(self._surface_order)

    def universal_bindings(self) -> list[tuple[Chord, Command]]:
        """Return explicitly registered universal bindings in order."""
        return list(self._orders[Layer.UNIVERSAL])

    def _ensure_slot_unfilled(self, slot: Slot) -> None:
        if slot in self._slot_fills or slot in self._slot_noops:
            raise RegistrationError(f"Slot already filled: {slot.name}")

    def _layer_for(self, chord: Chord) -> Layer | None:
        return next(
            (layer for layer in Layer if chord in self._bindings[layer]),
            None,
        )

    def _store(self, layer: Layer, chord: Chord, command: Command) -> None:
        self._bindings[layer][chord] = command
        self._orders[layer].append((chord, command))
        if layer is Layer.SURFACE:
            self._surface_order.append((chord, command))


def _precedence(layer: Layer) -> int:
    return tuple(Layer).index(layer)


def _do_nothing() -> None:
    pass
