from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import wx

from stonereader.services._hotkeys import HOTKEY_COMMANDS, HotkeyMap, chord_to_win32
from stonereader.services._settings import SettingsStore
from stonereader.ui.chords import Chord
from stonereader.ui.registry import Command, CommandRegistry, Layer


class FakeBackend:
    def __init__(self) -> None:
        self.register_results: list[bool] = []
        self.unregister_results: list[bool] = []
        self.calls: list[tuple[str, int, int, int | None]] = []

    def register(
        self,
        modifiers: int,
        vk: int,
        callback: Callable[[], None],
        label: str = "",
        *,
        hotkey_id: int | None = None,
    ) -> bool:
        del callback, label
        self.calls.append(("register", modifiers, vk, hotkey_id))
        return self.register_results.pop(0) if self.register_results else True

    def unregister(self, hotkey_id: int) -> bool:
        self.calls.append(("unregister", 0, 0, hotkey_id))
        return self.unregister_results.pop(0) if self.unregister_results else True


def make_map(tmp_path: Path) -> tuple[HotkeyMap, FakeBackend, SettingsStore]:
    backend = FakeBackend()
    handlers = {command.command_id: lambda: None for command in HOTKEY_COMMANDS}
    store = SettingsStore(tmp_path / "settings.json")
    hotkeys = HotkeyMap(backend, handlers)
    hotkeys.apply(store)
    backend.calls.clear()
    return hotkeys, backend, store


def test_apply_uses_defaults_and_stored_override(tmp_path: Path) -> None:
    backend = FakeBackend()
    store = SettingsStore(tmp_path / "settings.json")
    store.set_hotkey_chord("jump_cards", "ctrl+alt+c")
    hotkeys = HotkeyMap(
        backend, {command.command_id: lambda: None for command in HOTKEY_COMMANDS}
    )

    hotkeys.apply(store)

    assert hotkeys.current_chord("jump_cards") == Chord.parse("ctrl+alt+c")
    assert len(backend.calls) == 6


def test_rebind_success_persists_and_failure_restores_old_binding(
    tmp_path: Path,
) -> None:
    hotkeys, backend, store = make_map(tmp_path)
    replacement = Chord.parse("ctrl+alt+c")
    assert hotkeys.rebind("jump_cards", replacement) is None
    assert hotkeys.current_chord("jump_cards") == replacement
    assert store.hotkey_chord("jump_cards") == "ctrl+alt+c"

    backend.calls.clear()
    backend.register_results = [False, True]
    failure = hotkeys.rebind("jump_cards", Chord.parse("ctrl+alt+x"))
    assert failure == "Could not register Ctrl Alt X; keeping Ctrl Alt C"
    assert hotkeys.current_chord("jump_cards") == replacement
    assert store.hotkey_chord("jump_cards") == "ctrl+alt+c"
    assert [call[0] for call in backend.calls] == [
        "unregister",
        "register",
        "register",
    ]


def test_is_taken_includes_hotkeys_app_chords_and_instantiated_registries(
    tmp_path: Path,
) -> None:
    hotkeys, _backend, _store = make_map(tmp_path)
    assert hotkeys.is_taken(Chord.parse("ctrl+shift+c")) == "Jump to Cards"
    assert hotkeys.is_taken(Chord("enter", ctrl=True)) == "Accept offer"
    assert hotkeys.is_taken(Chord("f", ctrl=True)) == "Search"
    assert hotkeys.is_taken(Chord("q", ctrl=True)) == "Quit StoneReader"

    registry = CommandRegistry()
    registry.register(
        Layer.SURFACE,
        Chord("d", shift=True),
        Command(
            "live_game.opponent_deck",
            "Shift+D: how many cards are in your opponent's deck",
            lambda: None,
        ),
    )
    assert hotkeys.is_taken(
        Chord("d", shift=True), [("Live Game", registry)]
    ) == (
        "Live Game: Shift+D: how many cards are in your opponent's deck"
    )
    assert hotkeys.is_taken(Chord.parse("ctrl+alt+x")) is None


def test_chord_translation_supports_letters_digits_and_named_keys() -> None:
    assert chord_to_win32(Chord.parse("ctrl+shift+a")) == (
        wx.MOD_CONTROL | wx.MOD_SHIFT,
        ord("A"),
    )
    assert chord_to_win32(Chord.parse("alt+7")) == (wx.MOD_ALT, ord("7"))

    assert chord_to_win32(Chord("f5", ctrl=True)) == (wx.MOD_CONTROL, 0x74)

    try:
        chord_to_win32(Chord("+", ctrl=True))
    except ValueError as error:
        assert str(error) == "This shortcut key cannot be registered"
    else:
        raise AssertionError("untranslatable punctuation must not be registered")
