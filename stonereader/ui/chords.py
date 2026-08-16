"""Normalized keyboard chords at the input seam (ADR-0004, ADR-0011)."""

from __future__ import annotations

from dataclasses import dataclass


_NAMED_KEYS = {
    "enter",
    "escape",
    "backspace",
    "home",
    "end",
    "pageup",
    "pagedown",
    "tab",
    "delete",
    "space",
    "up",
    "down",
    "left",
    "right",
}
_CANONICAL_KEYS = (
    set("abcdefghijklmnopqrstuvwxyz0123456789")
    | _NAMED_KEYS
    | {f"f{number}" for number in range(1, 13)}
)
_MODIFIERS = ("ctrl", "shift", "alt")

_SPOKEN_KEYS = {
    "enter": "Enter",
    "escape": "Escape",
    "backspace": "Backspace",
    "home": "Home",
    "end": "End",
    "pageup": "Page Up",
    "pagedown": "Page Down",
    "tab": "Tab",
    "delete": "Delete",
    "space": "Space",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}

# wx key constants are literals so chord normalization remains headless.
_WXK_NAMES = {
    8: "backspace",  # wx.WXK_BACK
    9: "tab",  # wx.WXK_TAB
    13: "enter",  # wx.WXK_RETURN
    27: "escape",  # wx.WXK_ESCAPE
    32: "space",  # wx.WXK_SPACE
    127: "delete",  # wx.WXK_DELETE
    312: "end",  # wx.WXK_END
    313: "home",  # wx.WXK_HOME
    314: "left",  # wx.WXK_LEFT
    315: "up",  # wx.WXK_UP
    316: "right",  # wx.WXK_RIGHT
    317: "down",  # wx.WXK_DOWN
    340: "f1",  # wx.WXK_F1
    341: "f2",  # wx.WXK_F2
    342: "f3",  # wx.WXK_F3
    343: "f4",  # wx.WXK_F4
    344: "f5",  # wx.WXK_F5
    345: "f6",  # wx.WXK_F6
    346: "f7",  # wx.WXK_F7
    347: "f8",  # wx.WXK_F8
    348: "f9",  # wx.WXK_F9
    349: "f10",  # wx.WXK_F10
    350: "f11",  # wx.WXK_F11
    351: "f12",  # wx.WXK_F12
    366: "pageup",  # wx.WXK_PAGEUP
    367: "pagedown",  # wx.WXK_PAGEDOWN
    370: "enter",  # wx.WXK_NUMPAD_ENTER
}
_WXK_MODIFIERS = {
    306,  # wx.WXK_SHIFT
    307,  # wx.WXK_ALT
    308,  # wx.WXK_CONTROL
}


@dataclass(frozen=True)
class Chord:
    """A canonical key plus its modifier state."""

    key: str
    ctrl: bool = False
    shift: bool = False
    alt: bool = False

    def __post_init__(self) -> None:
        key = self.key.lower()
        # Printable punctuation is also admitted for Text mode. Navigation's
        # public chord vocabulary remains the named canonical set above.
        if key not in _CANONICAL_KEYS and not _is_printable_key(key):
            raise ValueError(f"Invalid key name: {self.key!r}")
        object.__setattr__(self, "key", key)

    @classmethod
    def parse(cls, text: str) -> Chord:
        """Parse a case-insensitive chord string into canonical form."""
        if text == "+" or text.endswith("++"):
            modifier_text = text[:-1]
            if modifier_text.endswith("+"):
                modifier_text = modifier_text[:-1]
            modifiers = (
                [part.strip().lower() for part in modifier_text.split("+")]
                if modifier_text
                else []
            )
            if any(part not in _MODIFIERS for part in modifiers):
                raise ValueError(f"Invalid chord: {text!r}")
            if len(set(modifiers)) != len(modifiers):
                raise ValueError(f"Duplicate modifier in chord: {text!r}")
            return cls(
                "+",
                ctrl="ctrl" in modifiers,
                shift="shift" in modifiers,
                alt="alt" in modifiers,
            )
        parts = [part.strip().lower() for part in text.split("+")]
        if not parts or any(not part for part in parts):
            raise ValueError(f"Invalid chord: {text!r}")
        key = parts[-1]
        modifiers = parts[:-1]
        if any(part not in _MODIFIERS for part in modifiers):
            raise ValueError(f"Invalid chord: {text!r}")
        if len(set(modifiers)) != len(modifiers):
            raise ValueError(f"Duplicate modifier in chord: {text!r}")
        return cls(
            key,
            ctrl="ctrl" in modifiers,
            shift="shift" in modifiers,
            alt="alt" in modifiers,
        )

    def __str__(self) -> str:
        """Return the canonical ``ctrl+shift+alt+key`` spelling."""
        parts = [
            name
            for name, enabled in (
                ("ctrl", self.ctrl),
                ("shift", self.shift),
                ("alt", self.alt),
            )
            if enabled
        ]
        return "+".join([*parts, self.key])

    def spoken(self) -> str:
        """Return the chord as the word sequence used by spoken help."""
        parts = [
            name
            for name, enabled in (
                ("Control", self.ctrl),
                ("Shift", self.shift),
                ("Alt", self.alt),
            )
            if enabled
        ]
        if len(self.key) == 1 and self.key.isalpha():
            spoken_key = self.key.upper()
        elif self.key.startswith("f") and self.key[1:].isdigit():
            spoken_key = self.key.upper()
        else:
            spoken_key = _SPOKEN_KEYS.get(self.key, self.key)
        return " ".join([*parts, spoken_key])


def _is_printable_key(key: str) -> bool:
    return len(key) == 1 and 33 <= ord(key) <= 126


def chord_from_key(
    keycode: int,
    *,
    ctrl: bool,
    shift: bool,
    alt: bool,
) -> Chord | None:
    """Normalize a wx keycode integer without importing wx."""
    if keycode in _WXK_MODIFIERS:
        return None
    key = _WXK_NAMES.get(keycode)
    if key is None and 33 <= keycode <= 126:
        key = chr(keycode).lower()
    if key is None:
        return None
    return Chord(key, ctrl=ctrl, shift=shift, alt=alt)
