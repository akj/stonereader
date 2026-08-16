from __future__ import annotations

import pytest

from stonereader.ui.chords import Chord
from stonereader.ui.registry import (
    SLOT_CHORDS,
    SLOT_DEFAULT_PHRASES,
    Command,
    CommandRegistry,
    Layer,
    RegistrationError,
    Slot,
)


def command(name: str, calls: list[str] | None = None) -> Command:
    def handler() -> None:
        if calls is not None:
            calls.append(name)

    return Command(name, f"Help for {name}", handler)


def test_command_requires_id_and_help_phrase() -> None:
    with pytest.raises(ValueError):
        Command("", "Help", lambda: None)
    with pytest.raises(ValueError):
        Command("id", "", lambda: None)


def test_lower_layer_cannot_shadow_upper_layer() -> None:
    registry = CommandRegistry([(Chord("f1"), command("help"))])
    with pytest.raises(RegistrationError):
        registry.register(Layer.SURFACE, Chord("f1"), command("other"))


@pytest.mark.parametrize(
    "chord",
    [Chord("enter", ctrl=True), Chord("escape"), Chord("backspace")],
)
def test_reserved_chords_refuse_normal_registration(chord: Chord) -> None:
    registry = CommandRegistry()
    with pytest.raises(RegistrationError):
        registry.register(Layer.UNIVERSAL, chord, command("reserved"))


@pytest.mark.parametrize("slot", list(Slot))
def test_every_slot_defaults_to_an_announced_noop(slot: Slot) -> None:
    registry = CommandRegistry()
    for chord in SLOT_CHORDS[slot]:
        result = registry.dispatch(chord)
        assert result.handled is True
        assert result.announce == SLOT_DEFAULT_PHRASES[slot]


@pytest.mark.parametrize("slot", list(Slot))
def test_every_slot_can_be_filled(slot: Slot) -> None:
    calls: list[str] = []
    registry = CommandRegistry()
    registry.fill_slot(slot, command(slot.name, calls))
    for chord in SLOT_CHORDS[slot]:
        result = registry.dispatch(chord)
        assert result.handled is True
        assert result.announce is None
    assert calls == [slot.name] * len(SLOT_CHORDS[slot])


@pytest.mark.parametrize(
    ("slot", "forward_chord", "reverse_chord"),
    [
        (Slot.GROUP_JUMP, Chord("tab"), Chord("tab", shift=True)),
        (Slot.COARSE_AXIS, Chord("pagedown"), Chord("pageup")),
    ],
)
def test_directional_slots_dispatch_forward_and_reverse_commands(
    slot: Slot,
    forward_chord: Chord,
    reverse_chord: Chord,
) -> None:
    calls: list[str] = []
    registry = CommandRegistry()
    registry.fill_slot(
        slot,
        command("forward", calls),
        command("reverse", calls),
    )

    registry.dispatch(forward_chord)
    registry.dispatch(reverse_chord)

    assert calls == ["forward", "reverse"]


def test_surface_specific_slot_noop_overrides_default() -> None:
    registry = CommandRegistry()
    registry.fill_slot_noop(Slot.LISTEN, "No game audio during a live game")
    assert registry.dispatch(Chord("l")).announce == "No game audio during a live game"


def test_unbound_non_universal_chord_is_silent_and_unhandled() -> None:
    result = CommandRegistry().dispatch(Chord("z"))
    assert result.handled is False
    assert result.announce is None


def test_surface_bindings_preserve_registration_order_including_slots() -> None:
    registry = CommandRegistry()
    first = command("first")
    search = command("search")
    last = command("last")
    registry.register(Layer.SURFACE, Chord("a"), first)
    registry.fill_slot(Slot.SEARCH, search)
    registry.register(Layer.SURFACE, Chord("b"), last)
    assert registry.surface_bindings() == [
        (Chord("a"), first),
        (Chord("f", ctrl=True), search),
        (Chord("b"), last),
    ]


def test_surface_cannot_register_slot_chord_directly() -> None:
    registry = CommandRegistry()
    with pytest.raises(RegistrationError):
        registry.register(Layer.SURFACE, Chord("enter"), command("enter"))


def test_navigation_hook_installs_both_back_chords() -> None:
    calls: list[str] = []
    registry = CommandRegistry()
    registry.register_back(lambda: calls.append("back"))
    assert registry.dispatch(Chord("escape")).handled
    assert registry.dispatch(Chord("backspace")).handled
    assert calls == ["back", "back"]
