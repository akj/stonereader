from __future__ import annotations

import pytest

from stonereader.ui.chords import Chord, chord_from_key


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        ("ctrl+shift+l", "ctrl+shift+l"),
        ("ALT+CTRL+F1", "ctrl+alt+f1"),
        ("PageDown", "pagedown"),
        ("shift++", "shift++"),
    ],
)
def test_parse_and_string_round_trip(source: str, canonical: str) -> None:
    chord = Chord.parse(source)
    assert str(chord) == canonical
    assert Chord.parse(str(chord)) == chord


@pytest.mark.parametrize("source", ["wat", "ctrl+wat", "ctrl+ctrl+a", "ctrl+"])
def test_invalid_chords_raise(source: str) -> None:
    with pytest.raises(ValueError):
        Chord.parse(source)


@pytest.mark.parametrize(
    ("chord", "spoken"),
    [
        (Chord("l", ctrl=True, shift=True), "Control Shift L"),
        (Chord("enter", ctrl=True), "Control Enter"),
        (Chord("pagedown"), "Page Down"),
        (Chord("pageup"), "Page Up"),
        (Chord("f1"), "F1"),
    ],
)
def test_spoken_forms(chord: Chord, spoken: str) -> None:
    assert chord.spoken() == spoken


@pytest.mark.parametrize("number", range(1, 13))
def test_f_keys_normalize(number: int) -> None:
    assert chord_from_key(
        339 + number, ctrl=False, shift=False, alt=False
    ) == Chord(f"f{number}")


def test_named_and_modified_keys_normalize() -> None:
    assert chord_from_key(370, ctrl=False, shift=False, alt=False) == Chord("enter")
    assert chord_from_key(127, ctrl=False, shift=True, alt=False) == Chord(
        "delete", shift=True
    )
    assert chord_from_key(ord("F"), ctrl=True, shift=False, alt=False) == Chord(
        "f", ctrl=True
    )


def test_letters_digits_and_printable_symbols_normalize() -> None:
    assert chord_from_key(ord("A"), ctrl=False, shift=False, alt=False) == Chord("a")
    assert chord_from_key(ord("7"), ctrl=False, shift=False, alt=False) == Chord("7")
    assert chord_from_key(ord("+"), ctrl=False, shift=True, alt=False) == Chord(
        "+", shift=True
    )


@pytest.mark.parametrize("keycode", [306, 307, 308, 9999])
def test_modifiers_and_unknown_codes_return_none(keycode: int) -> None:
    assert chord_from_key(keycode, ctrl=False, shift=False, alt=False) is None
