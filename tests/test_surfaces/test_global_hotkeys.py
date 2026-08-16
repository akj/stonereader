from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from stonereader.services._hotkeys import HOTKEY_COMMANDS, HotkeyMap
from stonereader.services._settings import SettingsStore
from stonereader.surfaces.global_hotkeys import build_global_hotkeys
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import ActiveSurface
from stonereader.ui.registry import Command
from stonereader.ui.surface import Binding, SurfaceSpec, WidgetType

from .conftest import Harness, make_harness


class Backend:
    def __init__(self) -> None:
        self.register_results: list[bool] = []

    def register(self, modifiers: int, vk: int, callback: Callable[[], None], label: str = "", *, hotkey_id: int | None = None) -> bool:
        del modifiers, vk, callback, label, hotkey_id
        return self.register_results.pop(0) if self.register_results else True

    def unregister(self, hotkey_id: int) -> bool:
        del hotkey_id
        return True


@dataclass
class HotkeyContext:
    hotkeys: HotkeyMap
    backend: Backend


def hotkey_harness(tmp_path: Path) -> Harness[HotkeyContext]:
    backend = Backend()
    store = SettingsStore(tmp_path / "settings.json")
    hotkeys = HotkeyMap(
        backend, {command.command_id: lambda: None for command in HOTKEY_COMMANDS}
    )
    hotkeys.apply(store)
    harness = make_harness(HotkeyContext(hotkeys, backend))
    harness.nav.register(
        "Global hotkeys",
        lambda: build_global_hotkeys(
            harness.announcer,
            [],
            harness.nav,
            harness.sink,
            hotkeys,
        ),
    )
    harness.nav.jump("Global hotkeys")
    return harness


def test_rows_are_live_and_two_modifier_chord_binds_directly(tmp_path: Path) -> None:
    harness = hotkey_harness(tmp_path)
    assert harness.vertical.options_snapshot()[0][0] == (
        "Jump to Live Game, Ctrl Shift L"
    )

    harness.press(Chord("enter"))
    assert harness.sink.capture_mode_active is True
    harness.press(Chord.parse("ctrl+alt+x"))
    assert harness.sink.capture_mode_active is False
    assert harness.context.hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+alt+x")
    assert harness.speech.calls[-1] == ("Jump to Live Game, Ctrl Alt X", True)


def test_bare_refusal_single_modifier_confirm_and_different_restart(
    tmp_path: Path,
) -> None:
    harness = hotkey_harness(tmp_path)
    harness.press(Chord("enter"))
    harness.press(Chord("x"))
    assert harness.speech.calls[-1] == ("A shortcut needs a modifier key", True)
    assert harness.sink.capture_mode_active is False

    harness.press(Chord("enter"))
    harness.press(Chord("x", shift=True))
    assert harness.speech.calls[-1][0].startswith(
        "Shift X is a single-modifier shortcut;"
    )
    harness.press(Chord("f5", ctrl=True))
    assert harness.speech.calls[-1][0].startswith(
        "Ctrl F5 is a single-modifier shortcut;"
    )
    harness.press(Chord("f5", ctrl=True))
    assert harness.sink.capture_mode_active is False
    assert harness.context.hotkeys.current_chord("jump_live_game") == Chord("f5", ctrl=True)


def test_taken_commands_and_accept_offer_are_refused_and_capture_stays(
    tmp_path: Path,
) -> None:
    harness = hotkey_harness(tmp_path)
    harness.press(Chord("enter"))
    harness.press(Chord.parse("ctrl+shift+c"))
    assert harness.speech.calls[-1] == (
        "Ctrl Shift C is taken by Jump to Cards",
        True,
    )
    assert harness.sink.capture_mode_active is True

    harness.press(Chord("delete", shift=True))
    assert harness.speech.calls[-1] == (
        "Shift Delete is taken by Global hotkeys: "
        "Shift+Delete: reset this shortcut without asking",
        True,
    )
    assert harness.sink.capture_mode_active is True

    harness.press(Chord("enter", ctrl=True))
    assert harness.speech.calls[-1] == ("Control Enter is taken by Accept offer", True)
    assert harness.sink.capture_mode_active is True


def test_chord_owned_by_never_visited_surface_is_refused(tmp_path: Path) -> None:
    harness = hotkey_harness(tmp_path)
    builds: list[str] = []

    def live_game_factory() -> ActiveSurface:
        builds.append("Live Game")
        return build_active_surface(
            SurfaceSpec(
                "Live Game",
                WidgetType.VERTICAL_MENU,
                options=lambda: [],
                bindings=[
                    Binding(
                        Chord("d", shift=True),
                        Command(
                            "live.query_opponent_deck",
                            "Shift+D: how many cards are in your opponent's deck",
                            lambda: None,
                        ),
                    )
                ],
            ),
            harness.announcer,
            [],
            harness.nav,
        )

    harness.nav.register("Live Game", live_game_factory)
    assert builds == []

    harness.press(Chord("enter"))
    harness.press(Chord("d", shift=True))

    assert builds == ["Live Game"]
    assert harness.speech.calls[-1] == (
        "Shift D is taken by Live Game: "
        "Shift+D: how many cards are in your opponent's deck",
        True,
    )
    assert harness.sink.capture_mode_active is True


def test_current_chord_is_noop_success_and_escape_relands(tmp_path: Path) -> None:
    harness = hotkey_harness(tmp_path)
    harness.press(Chord("enter"))
    harness.press(Chord.parse("ctrl+shift+l"))
    assert harness.sink.capture_mode_active is False
    assert harness.speech.calls[-1] == ("Jump to Live Game, Ctrl Shift L", True)

    harness.press(Chord("enter"))
    harness.press(Chord("escape"))
    assert harness.sink.capture_mode_active is False
    assert harness.speech.calls[-1] == ("Jump to Live Game, Ctrl Shift L", True)


def test_os_failure_keeps_previous_binding_and_capture_active(tmp_path: Path) -> None:
    harness = hotkey_harness(tmp_path)
    harness.press(Chord("enter"))
    harness.context.backend.register_results = [False, True]
    harness.press(Chord.parse("ctrl+alt+x"))

    assert harness.context.hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+shift+l")
    assert harness.sink.capture_mode_active is True
    assert harness.speech.calls[-1] == (
        "Could not register Ctrl Alt X; keeping Ctrl Shift L",
        True,
    )


def test_delete_arms_and_shift_delete_resets_current_row(tmp_path: Path) -> None:
    harness = hotkey_harness(tmp_path)
    harness.context.hotkeys.rebind("jump_live_game", Chord.parse("ctrl+alt+x"))
    harness.press(Chord("delete"))
    assert harness.context.hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+alt+x")
    harness.press(Chord("delete"))
    assert harness.context.hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+shift+l")
    assert harness.speech.calls[-2:] == [
        (
            "Press Delete again to reset Jump to Live Game to Ctrl Shift L",
            True,
        ),
        ("Jump to Live Game, Ctrl Shift L", True),
    ]

    harness.context.hotkeys.rebind("jump_live_game", Chord.parse("ctrl+alt+x"))
    harness.press(Chord("delete", shift=True))
    assert harness.context.hotkeys.current_chord("jump_live_game") == Chord.parse("ctrl+shift+l")
