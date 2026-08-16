from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from stonereader.services._hotkeys import HOTKEY_COMMANDS, HotkeyMap
from stonereader.services._settings import SettingsStore
from stonereader.surfaces.global_hotkeys import build_global_hotkeys
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import NavigationController

from tests.test_ui.conftest import FakeSpeech


class Backend:
    def __init__(self) -> None:
        self.register_results: list[bool] = []

    def register(self, _modifiers: int, _vk: int, _callback: Callable[[], None], _label: str = "", *, hotkey_id: int | None = None) -> bool:
        del hotkey_id
        return self.register_results.pop(0) if self.register_results else True

    def unregister(self, _hotkey_id: int) -> bool:
        return True


def harness(tmp_path: Path):
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    backend = Backend()
    store = SettingsStore(tmp_path / "settings.json")
    hotkeys = HotkeyMap(
        backend, {command.command_id: lambda: None for command in HOTKEY_COMMANDS}
    )
    hotkeys.apply(store)
    nav.register(
        "Global hotkeys",
        lambda: build_global_hotkeys(announcer, [], nav, sink, hotkeys),
    )
    nav.jump("Global hotkeys")
    return sink, speech, hotkeys, backend, nav._surfaces["Global hotkeys"]


def test_rows_are_live_and_two_modifier_chord_binds_directly(tmp_path: Path) -> None:
    sink, speech, hotkeys, _backend, surface = harness(tmp_path)
    assert surface.engine.options_snapshot()[0][0] == (
        "Jump to Live Game, Control Shift L"
    )

    sink.handle_chord(Chord("enter"))
    assert sink.capture_mode_active is True
    sink.handle_chord(Chord.parse("ctrl+alt+x"))
    assert sink.capture_mode_active is False
    assert hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+alt+x")
    assert speech.calls[-1] == ("Jump to Live Game, Control Alt X", True)


def test_bare_refusal_single_modifier_confirm_and_different_restart(
    tmp_path: Path,
) -> None:
    sink, speech, hotkeys, _backend, _surface = harness(tmp_path)
    sink.handle_chord(Chord("enter"))
    sink.handle_chord(Chord("x"))
    assert speech.calls[-1] == ("A shortcut needs a modifier key", True)

    sink.handle_chord(Chord("x", shift=True))
    assert speech.calls[-1][0].startswith(
        "Shift X is a single-modifier shortcut;"
    )
    sink.handle_chord(Chord("y", ctrl=True))
    assert speech.calls[-1][0].startswith(
        "Control Y is a single-modifier shortcut;"
    )
    sink.handle_chord(Chord("y", ctrl=True))
    assert sink.capture_mode_active is False
    assert hotkeys.current_chord("jump_live_game") == Chord("y", ctrl=True)


def test_taken_commands_and_accept_offer_are_refused_and_capture_stays(
    tmp_path: Path,
) -> None:
    sink, speech, _hotkeys, _backend, _surface = harness(tmp_path)
    sink.handle_chord(Chord("enter"))
    sink.handle_chord(Chord.parse("ctrl+shift+c"))
    assert speech.calls[-1] == (
        "Control Shift C is taken by Jump to Cards",
        True,
    )
    assert sink.capture_mode_active is True

    sink.handle_chord(Chord("enter", ctrl=True))
    assert speech.calls[-1] == ("Control Enter is taken by Accept offer", True)
    assert sink.capture_mode_active is True


def test_current_chord_is_noop_success_and_escape_relands(tmp_path: Path) -> None:
    sink, speech, _hotkeys, _backend, _surface = harness(tmp_path)
    sink.handle_chord(Chord("enter"))
    sink.handle_chord(Chord.parse("ctrl+shift+l"))
    assert sink.capture_mode_active is False
    assert speech.calls[-1] == ("Jump to Live Game, Control Shift L", True)

    sink.handle_chord(Chord("enter"))
    sink.handle_chord(Chord("escape"))
    assert sink.capture_mode_active is False
    assert speech.calls[-1] == ("Jump to Live Game, Control Shift L", True)


def test_os_failure_keeps_previous_binding_and_capture_active(tmp_path: Path) -> None:
    sink, speech, hotkeys, backend, _surface = harness(tmp_path)
    sink.handle_chord(Chord("enter"))
    backend.register_results = [False, True]
    sink.handle_chord(Chord.parse("ctrl+alt+x"))

    assert hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+shift+l")
    assert sink.capture_mode_active is True
    assert speech.calls[-1] == (
        "Could not register Control Alt X; keeping Control Shift L",
        True,
    )


def test_delete_arms_and_shift_delete_resets_current_row(tmp_path: Path) -> None:
    sink, speech, hotkeys, _backend, _surface = harness(tmp_path)
    hotkeys.rebind("jump_live_game", Chord.parse("ctrl+alt+x"))
    sink.handle_chord(Chord("delete"))
    assert hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+alt+x")
    sink.handle_chord(Chord("delete"))
    assert hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+shift+l")
    assert speech.calls[-2:] == [
        (
            "Press Delete again to reset Jump to Live Game to Control Shift L",
            True,
        ),
        ("Jump to Live Game, Control Shift L", True),
    ]

    hotkeys.rebind("jump_live_game", Chord.parse("ctrl+alt+x"))
    sink.handle_chord(Chord("delete", shift=True))
    assert hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+shift+l")
