from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from stonereader.services._hotkeys import HOTKEY_COMMANDS, HotkeyMap
from stonereader.services._settings import SettingsStore
from stonereader.surfaces.global_hotkeys import build_global_hotkeys
from stonereader.surfaces.picker import PickerHolder, build_picker
from stonereader.surfaces.settings import build_settings
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import NavigationController

from tests.test_ui.conftest import FakeSpeech


class Backend:
    def register(self, _modifiers: int, _vk: int, _callback: Callable[[], None], _label: str = "", *, hotkey_id: int | None = None) -> bool:
        del hotkey_id
        return True

    def unregister(self, _hotkey_id: int) -> bool:
        return True


def make_settings(tmp_path: Path, install: Path | None):
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    store = SettingsStore(tmp_path / "settings.json")
    hotkeys = HotkeyMap(
        Backend(), {command.command_id: lambda: None for command in HOTKEY_COMMANDS}
    )
    hotkeys.apply(store)
    holder = PickerHolder()
    nav.register(
        "Settings",
        lambda: build_settings(
            announcer,
            [],
            nav,
            store,
            sink,
            holder,
            hotkeys,
            install_detector=lambda _custom: install,
            log_detector=lambda _install: None,
        ),
    )
    nav.register("Picker", lambda: build_picker(announcer, [], nav, holder))
    nav.register(
        "Global hotkeys",
        lambda: build_global_hotkeys(announcer, [], nav, sink, hotkeys),
    )
    nav.jump("Settings")
    return nav, sink, speech, store, hotkeys, nav._surfaces["Settings"]


def select(surface, sink: _SinkCore, index: int) -> None:
    surface.engine.set_cursor(index)
    sink.set_active(surface.registry)


def type_text(sink: _SinkCore, value: str) -> None:
    for character in value:
        sink.handle_chord(
            Chord(
                character.lower(),
                shift=character.isalpha() and character.isupper(),
            )
        )


def test_all_eight_dynamic_row_titles_including_unavailable_volume(
    tmp_path: Path,
) -> None:
    _nav, _sink, _speech, store, _hotkeys, surface = make_settings(tmp_path, None)
    store.set_narration("everything")
    store.set_replay_autoplay(False)
    store.set_replay_retention(500)

    assert surface.engine.options_snapshot()[0] == [
        "Narration, everything",
        "Game audio volume, unavailable — no Hearthstone install found",
        "Replay auto-play, off",
        "Hearthstone install path, auto-detected",
        "Hearthstone log path, auto-detected",
        "Replay retention, last 500",
        "Global hotkeys",
        "Restore all defaults",
    ]


def test_choice_volume_toggle_retention_and_drilldown_enter_idioms(
    tmp_path: Path,
) -> None:
    install = tmp_path / "Hearthstone"
    install.mkdir()
    nav, sink, _speech, store, _hotkeys, surface = make_settings(tmp_path, install)

    sink.handle_chord(Chord("enter"))
    assert nav.stack[-1] == "Picker"
    assert nav._surfaces["Picker"].engine.options_snapshot()[1] == 1
    sink.handle_chord(Chord("escape"))

    select(surface, sink, 1)
    sink.handle_chord(Chord("enter"))
    assert nav.stack[-1] == "Picker"
    sink.handle_chord(Chord("escape"))

    select(surface, sink, 2)
    sink.handle_chord(Chord("enter"))
    assert store.replay_autoplay is False

    select(surface, sink, 5)
    sink.handle_chord(Chord("enter"))
    assert nav._surfaces["Picker"].engine.options_snapshot()[1] == 0
    sink.handle_chord(Chord("escape"))

    select(surface, sink, 6)
    sink.handle_chord(Chord("enter"))
    assert nav.stack[-1] == "Global hotkeys"


def test_unavailable_volume_explains_and_does_not_open_picker(tmp_path: Path) -> None:
    nav, sink, speech, _store, _hotkeys, surface = make_settings(tmp_path, None)
    select(surface, sink, 1)

    sink.handle_chord(Chord("enter"))

    assert nav.stack == ("Home", "Settings")
    assert speech.calls[-1] == (
        "Game audio volume, unavailable — no Hearthstone install found",
        True,
    )


def test_path_commit_empty_reset_and_invalid_refusal(tmp_path: Path) -> None:
    nav, sink, speech, store, _hotkeys, surface = make_settings(tmp_path, None)
    select(surface, sink, 3)
    sink.handle_chord(Chord("enter"))
    missing = tmp_path / "missing"
    type_text(sink, str(missing))
    sink.handle_chord(Chord("enter"))
    assert store.hs_install_path is None
    assert speech.calls[-2:] == [
        ("Path not found, keeping the previous value", True),
        ("Settings, Hearthstone install path, auto-detected", True),
    ]

    existing = tmp_path / "existing"
    existing.mkdir()
    select(surface, sink, 3)
    sink.handle_chord(Chord("enter"))
    type_text(sink, str(existing))
    sink.handle_chord(Chord("enter"))
    assert store.hs_install_path == existing

    select(surface, sink, 3)
    sink.handle_chord(Chord("enter"))
    for _ in str(existing):
        sink.handle_chord(Chord("backspace"))
    sink.handle_chord(Chord("enter"))
    assert store.hs_install_path is None
    assert nav.stack == ("Home", "Settings")


def test_delete_armed_shift_delete_and_restore_all_enter(tmp_path: Path) -> None:
    install = tmp_path / "Hearthstone"
    install.mkdir()
    _nav, sink, speech, store, hotkeys, surface = make_settings(tmp_path, install)
    store.set_narration("off")
    select(surface, sink, 0)
    sink.handle_chord(Chord("delete"))
    assert store.narration == "off"
    sink.handle_chord(Chord("delete"))
    assert store.narration == "key_moments"
    assert speech.calls[-2:] == [
        ("Press Delete again to reset Narration to key moments", True),
        ("Narration, key moments", True),
    ]

    store.set_replay_autoplay(False)
    select(surface, sink, 2)
    sink.handle_chord(Chord("delete", shift=True))
    assert store.replay_autoplay is True

    store.set_narration("off")
    hotkeys.rebind("jump_cards", Chord.parse("ctrl+alt+c"))
    select(surface, sink, 7)
    sink.handle_chord(Chord("enter"))
    assert store.narration == "off"
    sink.handle_chord(Chord("enter"))
    assert store.narration == "key_moments"
    assert hotkeys.current_chord("jump_cards") == Chord.parse("ctrl+shift+c")


def test_ctrl_f_has_pinned_no_search_phrase_and_space_is_unbound(
    tmp_path: Path,
) -> None:
    _nav, sink, speech, _store, _hotkeys, _surface = make_settings(tmp_path, None)
    assert sink.handle_chord(Chord("f", ctrl=True)) is True
    assert speech.calls[-1] == ("No search on this screen", True)
    before = list(speech.calls)
    assert sink.handle_chord(Chord("space")) is False
    assert speech.calls == before
