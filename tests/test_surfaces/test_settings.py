from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from stonereader.services._hotkeys import HOTKEY_COMMANDS, HotkeyMap
from stonereader.services._settings import SettingsStore
from stonereader.surfaces.global_hotkeys import build_global_hotkeys
from stonereader.surfaces.picker import PickerHolder, build_picker
from stonereader.surfaces.settings import build_settings
from stonereader.ui.chords import Chord

from .conftest import Harness, make_harness


class Backend:
    def register(self, modifiers: int, vk: int, callback: Callable[[], None], label: str = "", *, hotkey_id: int | None = None) -> bool:
        del modifiers, vk, callback, label, hotkey_id
        return True

    def unregister(self, hotkey_id: int) -> bool:
        del hotkey_id
        return True


class FakeAudioStatus:
    def __init__(self, status: str) -> None:
        self.status = status


@dataclass
class SettingsContext:
    store: SettingsStore
    hotkeys: HotkeyMap
    update_checks: list[str]


def make_settings(
    tmp_path: Path,
    install: Path | None,
    audio_status: FakeAudioStatus | None = None,
) -> Harness[SettingsContext]:
    store = SettingsStore(tmp_path / "settings.json")
    hotkeys = HotkeyMap(
        Backend(), {command.command_id: lambda: None for command in HOTKEY_COMMANDS}
    )
    hotkeys.apply(store)
    update_checks: list[str] = []
    harness = make_harness(SettingsContext(store, hotkeys, update_checks))
    holder = PickerHolder()
    harness.nav.register(
        "Settings",
        lambda: build_settings(
            harness.announcer,
            [],
            harness.nav,
            store,
            harness.sink,
            holder,
            hotkeys,
            audio_index=audio_status,
            check_for_updates=lambda: update_checks.append("checked"),
            install_detector=lambda _custom: install,
            log_detector=lambda _install: None,
        ),
    )
    harness.nav.register(
        "Picker",
        lambda: build_picker(harness.announcer, [], harness.nav, holder),
    )
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
    harness.nav.jump("Settings")
    return harness


def test_volume_availability_follows_channel_status_not_path_detection(
    tmp_path: Path,
) -> None:
    install = tmp_path / "Hearthstone"
    install.mkdir()
    harness = make_settings(
        tmp_path,
        install,
        FakeAudioStatus("absent"),
    )
    assert harness.vertical.options_snapshot()[0][1] == (
        "Game audio volume, unavailable — no Hearthstone install found"
    )

    harness = make_settings(
        tmp_path / "ready",
        None,
        FakeAudioStatus("ready"),
    )
    select(harness, 1)
    harness.press(Chord("enter"))
    assert harness.nav.stack[-1] == "Picker"


def select(harness: Harness[SettingsContext], index: int) -> None:
    harness.vertical.set_cursor(index)
    harness.sink.set_active(harness.active_surface.registry)


def test_all_nine_dynamic_row_titles_including_unavailable_volume(
    tmp_path: Path,
) -> None:
    harness = make_settings(tmp_path, None)
    harness.context.store.set_narration("everything")
    harness.context.store.set_replay_autoplay(False)
    harness.context.store.set_replay_retention(500)

    assert harness.vertical.options_snapshot()[0] == [
        "Narration, everything",
        "Game audio volume, unavailable — no Hearthstone install found",
        "Replay auto-play, off",
        "Hearthstone install path, auto-detected",
        "Hearthstone log path, auto-detected",
        "Replay retention, last 500",
        "Global hotkeys",
        "Check for updates",
        "Restore all defaults",
    ]


def test_choice_volume_toggle_retention_and_drilldown_enter_idioms(
    tmp_path: Path,
) -> None:
    install = tmp_path / "Hearthstone"
    install.mkdir()
    harness = make_settings(tmp_path, install)

    harness.press(Chord("enter"))
    assert harness.nav.stack[-1] == "Picker"
    assert harness.vertical.options_snapshot()[1] == 1
    harness.press(Chord("escape"))

    select(harness, 1)
    harness.press(Chord("enter"))
    assert harness.nav.stack[-1] == "Picker"
    harness.press(Chord("escape"))

    select(harness, 2)
    harness.press(Chord("enter"))
    assert harness.context.store.replay_autoplay is False

    select(harness, 5)
    harness.press(Chord("enter"))
    assert harness.vertical.options_snapshot()[1] == 0
    harness.press(Chord("escape"))

    select(harness, 6)
    harness.press(Chord("enter"))
    assert harness.nav.stack[-1] == "Global hotkeys"

    harness.press(Chord("escape"))
    select(harness, 7)
    harness.press(Chord("enter"))
    assert harness.context.update_checks == ["checked"]


def test_unavailable_volume_explains_and_does_not_open_picker(tmp_path: Path) -> None:
    harness = make_settings(tmp_path, None)
    select(harness, 1)

    harness.press(Chord("enter"))

    assert harness.nav.stack == ("Home", "Settings")
    assert harness.speech.calls[-1] == (
        "Game audio volume, unavailable — no Hearthstone install found",
        True,
    )


def test_path_commit_empty_reset_and_invalid_refusal(tmp_path: Path) -> None:
    harness = make_settings(tmp_path, None)
    select(harness, 3)
    harness.press(Chord("enter"))
    missing = tmp_path / "missing"
    harness.type(str(missing))
    harness.press(Chord("enter"))
    assert harness.context.store.hs_install_path is None
    assert harness.speech.calls[-2:] == [
        ("Path not found, keeping the previous value", True),
        ("Settings, Hearthstone install path, auto-detected", True),
    ]

    existing = tmp_path / "existing"
    existing.mkdir()
    select(harness, 3)
    harness.press(Chord("enter"))
    harness.type(str(existing))
    harness.press(Chord("enter"))
    assert harness.context.store.hs_install_path == existing

    select(harness, 3)
    harness.press(Chord("enter"))
    for _ in str(existing):
        harness.press(Chord("backspace"))
    harness.press(Chord("enter"))
    assert harness.context.store.hs_install_path is None
    assert harness.nav.stack == ("Home", "Settings")


def test_delete_armed_shift_delete_and_restore_all_enter(tmp_path: Path) -> None:
    install = tmp_path / "Hearthstone"
    install.mkdir()
    harness = make_settings(tmp_path, install)
    harness.context.store.set_narration("off")
    select(harness, 0)
    harness.press(Chord("delete"))
    assert harness.context.store.narration == "off"
    harness.press(Chord("delete"))
    assert harness.context.store.narration == "key_moments"
    assert harness.speech.calls[-2:] == [
        ("Press Delete again to reset Narration to key moments", True),
        ("Narration, key moments", True),
    ]

    harness.context.store.set_replay_autoplay(False)
    select(harness, 2)
    harness.press(Chord("delete", shift=True))
    assert harness.context.store.replay_autoplay is True

    harness.context.store.set_narration("off")
    harness.context.hotkeys.rebind("jump_cards", Chord.parse("ctrl+alt+c"))
    select(harness, 8)
    harness.press(Chord("enter"))
    assert harness.context.store.narration == "off"
    harness.press(Chord("enter"))
    assert harness.context.store.narration == "key_moments"
    assert harness.context.hotkeys.current_chord("jump_cards") == Chord.parse("ctrl+shift+c")


def test_ctrl_f_has_pinned_no_search_phrase_and_space_is_unbound(
    tmp_path: Path,
) -> None:
    harness = make_settings(tmp_path, None)
    assert harness.press(Chord("f", ctrl=True)) is True
    assert harness.speech.calls[-1] == ("No search on this screen", True)
    before = list(harness.speech.calls)
    assert harness.press(Chord("space")) is False
    assert harness.speech.calls == before
