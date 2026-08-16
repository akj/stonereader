"""Mutable registry for StoneReader's six system-wide hotkeys."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

import wx

from stonereader.services._settings import SettingsStore
from stonereader.ui.chords import Chord


@dataclass(frozen=True)
class HotkeyCommand:
    command_id: str
    label: str
    default_chord: Chord


HOTKEY_COMMANDS = (
    HotkeyCommand("jump_live_game", "Jump to Live Game", Chord.parse("ctrl+shift+l")),
    HotkeyCommand(
        "jump_live_game_opponent_hand",
        "Jump to Live Game (opponent hand)",
        Chord.parse("ctrl+shift+o"),
    ),
    HotkeyCommand("jump_cards", "Jump to Cards", Chord.parse("ctrl+shift+c")),
    HotkeyCommand("jump_replays", "Jump to Replays", Chord.parse("ctrl+shift+r")),
    HotkeyCommand(
        "speak_deck_counts", "Speak deck counts", Chord.parse("ctrl+shift+d")
    ),
    HotkeyCommand(
        "speak_opponent_hand_count",
        "Speak opponent hand count",
        Chord.parse("ctrl+shift+h"),
    ),
)

_COMMAND_BY_ID = {command.command_id: command for command in HOTKEY_COMMANDS}
_ACCEPT_OFFER = Chord("enter", ctrl=True)
_ID_BASE = 2000


class HotkeyBackend(Protocol):
    def register(
        self,
        modifiers: int,
        vk: int,
        callback: Callable[[], None],
        label: str = "",
        *,
        hotkey_id: int | None = None,
    ) -> bool: ...

    def unregister(self, hotkey_id: int) -> bool: ...


class HotkeyMap:
    """Own command metadata, live bindings, OS registration, and persistence."""

    def __init__(
        self,
        backend: HotkeyBackend,
        handlers: Mapping[str, Callable[[], None]],
    ) -> None:
        missing = [
            command.command_id
            for command in HOTKEY_COMMANDS
            if command.command_id not in handlers
        ]
        if missing:
            raise ValueError(f"Missing hotkey handler: {missing[0]}")
        self._backend = backend
        self._handlers = dict(handlers)
        self._current = {
            command.command_id: command.default_chord for command in HOTKEY_COMMANDS
        }
        self._ids = {
            command.command_id: _ID_BASE + index
            for index, command in enumerate(HOTKEY_COMMANDS)
        }
        self._store: SettingsStore | None = None

    @property
    def commands(self) -> tuple[HotkeyCommand, ...]:
        return HOTKEY_COMMANDS

    def apply(self, store: SettingsStore) -> None:
        """Read stored overrides and register all six commands."""
        self._store = store
        for command in HOTKEY_COMMANDS:
            override = store.hotkey_chord(command.command_id)
            try:
                chord = Chord.parse(override) if override is not None else command.default_chord
                modifiers, vk = chord_to_win32(chord)
            except ValueError:
                chord = command.default_chord
                modifiers, vk = chord_to_win32(chord)
            self._current[command.command_id] = chord
            self._backend.register(
                modifiers,
                vk,
                self._handlers[command.command_id],
                command.label,
                hotkey_id=self._ids[command.command_id],
            )

    def current_chord(self, command_id: str) -> Chord:
        self._command(command_id)
        return self._current[command_id]

    def is_taken(self, chord: Chord) -> str | None:
        if chord == _ACCEPT_OFFER:
            return "Accept offer"
        for command in HOTKEY_COMMANDS:
            if self._current[command.command_id] == chord:
                return command.label
        return None

    def rebind(self, command_id: str, chord: Chord) -> str | None:
        """Replace one binding transactionally, restoring the old one on refusal."""
        command = self._command(command_id)
        store = self._require_store()
        previous = self._current[command_id]
        if chord == previous:
            if chord == command.default_chord:
                store.set_hotkey_chord(command_id, None)
            return None
        try:
            modifiers, vk = chord_to_win32(chord)
        except ValueError as error:
            return str(error)
        hotkey_id = self._ids[command_id]
        if not self._backend.unregister(hotkey_id):
            return f"Could not unregister {previous.spoken()}; keeping it"
        if not self._backend.register(
            modifiers,
            vk,
            self._handlers[command_id],
            command.label,
            hotkey_id=hotkey_id,
        ):
            old_modifiers, old_vk = chord_to_win32(previous)
            self._backend.register(
                old_modifiers,
                old_vk,
                self._handlers[command_id],
                command.label,
                hotkey_id=hotkey_id,
            )
            return f"Could not register {chord.spoken()}; keeping {previous.spoken()}"
        self._current[command_id] = chord
        store.set_hotkey_chord(
            command_id,
            None if chord == command.default_chord else str(chord),
        )
        return None

    def restore_defaults(self) -> list[str]:
        failures: list[str] = []
        for command in HOTKEY_COMMANDS:
            failure = self.rebind(command.command_id, command.default_chord)
            if failure is not None:
                failures.append(failure)
        return failures

    def _command(self, command_id: str) -> HotkeyCommand:
        try:
            return _COMMAND_BY_ID[command_id]
        except KeyError as error:
            raise KeyError(f"Unknown hotkey command: {command_id}") from error

    def _require_store(self) -> SettingsStore:
        if self._store is None:
            raise RuntimeError("HotkeyMap.apply() must be called before rebinding")
        return self._store


def chord_to_win32(chord: Chord) -> tuple[int, int]:
    """Translate the supported letter/digit Chords into wx/Win32 values."""
    if len(chord.key) != 1 or not chord.key.isalnum():
        raise ValueError("Only letter and number shortcuts can be registered")
    modifiers = 0
    if chord.ctrl:
        modifiers |= wx.MOD_CONTROL
    if chord.shift:
        modifiers |= wx.MOD_SHIFT
    if chord.alt:
        modifiers |= wx.MOD_ALT
    return modifiers, ord(chord.key.upper())
