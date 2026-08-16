"""Immediate-apply Settings Surface (ADR-0011)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from stonereader.services._hotkeys import HotkeyMap
from stonereader.services._hs_install import detect_install
from stonereader.services._log_path import discover_power_log_path
from stonereader.services._settings import (
    DEFAULT_GAME_AUDIO_VOLUME,
    DEFAULT_NARRATION,
    DEFAULT_REPLAY_AUTOPLAY,
    DEFAULT_REPLAY_RETENTION,
    SettingsStore,
)
from stonereader.surfaces.picker import PickerHolder, PickerRequest
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, MenuOption, SurfaceSpec, WidgetType
from stonereader.ui.text_mode import TextSession


class SettingsSink(Protocol):
    def enter_text_mode(self, session: TextSession) -> None: ...

    def exit_text_mode(self) -> None: ...


_NO_INSTALL = "unavailable — no Hearthstone install found"
_ROW_IDS = (
    "narration",
    "game_audio_volume",
    "replay_autoplay",
    "hs_install_path",
    "hs_log_path",
    "replay_retention",
    "global_hotkeys",
    "restore_all",
)


def build_settings(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    store: SettingsStore,
    sink: SettingsSink,
    picker: PickerHolder,
    hotkeys: HotkeyMap,
    *,
    install_detector: Callable[[Path | None], Path | None] = detect_install,
    log_detector: Callable[[Path | None], Path | None] = discover_power_log_path,
) -> ActiveSurface:
    """Build the eight-row, autosaving settings menu."""
    engine: VerticalMenuEngine | None = None
    delete_armed: ArmedAction | None = None
    enter_armed: ArmedAction | None = None

    def effective_install() -> Path | None:
        return install_detector(store.hs_install_path)

    def effective_log() -> Path | None:
        if store.hs_log_path is not None and store.hs_log_path.exists():
            return store.hs_log_path
        return log_detector(effective_install())

    def narration_title() -> str:
        return f"Narration, {store.narration.replace('_', ' ')}"

    def volume_title() -> str:
        install = effective_install()
        value = str(store.game_audio_volume) if install is not None else _NO_INSTALL
        return f"Game audio volume, {value}"

    def autoplay_title() -> str:
        return f"Replay auto-play, {'on' if store.replay_autoplay else 'off'}"

    def install_title() -> str:
        value = "custom" if store.hs_install_path is not None else "auto-detected"
        return f"Hearthstone install path, {value}"

    def log_title() -> str:
        value = "custom" if store.hs_log_path is not None else "auto-detected"
        return f"Hearthstone log path, {value}"

    def retention_title() -> str:
        value = (
            "unlimited"
            if store.replay_retention is None
            else f"last {store.replay_retention}"
        )
        return f"Replay retention, {value}"

    def changed(title: Callable[[], str]) -> None:
        if engine is None:
            raise RuntimeError("Settings engine is not active")
        engine.refresh()
        announcer.moved(title())

    def open_picker(request: PickerRequest) -> None:
        picker.set(request)
        nav.drill_down("Picker")

    def edit_narration() -> None:
        open_picker(
            PickerRequest(
                "Narration",
                [("off", "off"), ("key moments", "key_moments"), ("everything", "everything")],
                store.narration,
                lambda raw: _set_and_refresh(store.set_narration, raw),
            )
        )

    def edit_volume() -> None:
        if effective_install() is None:
            announcer.noop(volume_title())
            return
        open_picker(
            PickerRequest(
                "Game audio volume",
                [(str(value), value) for value in range(0, 101, 10)],
                store.game_audio_volume,
                lambda raw: _set_and_refresh(store.set_game_audio_volume, raw),
            )
        )

    def toggle_autoplay() -> None:
        store.set_replay_autoplay(not store.replay_autoplay)
        changed(autoplay_title)

    def edit_path(
        label: str,
        current: Callable[[], Path | None],
        setter: Callable[[Path | None], None],
    ) -> None:
        initial_path = current()

        def commit(value: str) -> None:
            candidate_text = value.strip()
            if candidate_text and not Path(candidate_text).exists():
                sink.exit_text_mode()
                announcer.noop("Path not found, keeping the previous value")
                reland()
                return
            setter(Path(candidate_text) if candidate_text else None)
            sink.exit_text_mode()
            reland()

        def abandon() -> None:
            sink.exit_text_mode()
            reland()

        sink.enter_text_mode(
            TextSession(
                label,
                str(initial_path) if initial_path is not None else "",
                announcer,
                commit,
                abandon,
            )
        )

    def reland() -> None:
        if engine is None:
            raise RuntimeError("Settings engine is not active")
        engine.refresh()
        engine.on_landing()

    def edit_retention() -> None:
        open_picker(
            PickerRequest(
                "Replay retention",
                [
                    ("unlimited", None),
                    ("last 100", 100),
                    ("last 500", 500),
                    ("last 1000", 1000),
                ],
                store.replay_retention,
                lambda raw: _set_and_refresh(store.set_replay_retention, raw),
            )
        )

    def _set_and_refresh[T](setter: Callable[[T], None], value: T) -> None:
        setter(value)
        if engine is not None:
            engine.refresh()

    def restore_hotkeys() -> None:
        for failure in hotkeys.restore_defaults():
            announcer.noop(failure)

    def restore_all() -> None:
        store.set_narration(DEFAULT_NARRATION)
        store.set_game_audio_volume(DEFAULT_GAME_AUDIO_VOLUME)
        store.set_replay_autoplay(DEFAULT_REPLAY_AUTOPLAY)
        store.set_hs_install_path(None)
        store.set_hs_log_path(None)
        store.set_replay_retention(DEFAULT_REPLAY_RETENTION)
        restore_hotkeys()
        changed(lambda: "Restore all defaults")

    def options() -> list[MenuOption]:
        # Full custom paths stay reachable by Enter in Text mode; this vertical
        # menu intentionally keeps the row titles short (ADR-0011 ruling).
        return [
            MenuOption("narration", narration_title, edit_narration),
            MenuOption("game_audio_volume", volume_title, edit_volume),
            MenuOption("replay_autoplay", autoplay_title, toggle_autoplay),
            MenuOption(
                "hs_install_path",
                install_title,
                lambda: edit_path(
                    "Hearthstone install path",
                    effective_install,
                    store.set_hs_install_path,
                ),
            ),
            MenuOption(
                "hs_log_path",
                log_title,
                lambda: edit_path(
                    "Hearthstone log path", effective_log, store.set_hs_log_path
                ),
            ),
            MenuOption("replay_retention", retention_title, edit_retention),
            MenuOption("global_hotkeys", lambda: "Global hotkeys", lambda: nav.drill_down("Global hotkeys")),
            MenuOption("restore_all", lambda: "Restore all defaults", None),
        ]

    def current_row() -> str:
        if engine is None:
            raise RuntimeError("Settings engine is not active")
        return _ROW_IDS[engine.cursor]

    def activate_current() -> None:
        if engine is None or enter_armed is None:
            raise RuntimeError("Settings actions are not active")
        if current_row() == "restore_all":
            enter_armed.press(
                "enter:restore_all",
                "Press Enter again to restore all defaults",
                restore_all,
            )
            return
        if not engine.activate_current():
            announcer.noop("Nothing to do here")

    def reset_current() -> None:
        row = current_row()
        actions: dict[str, tuple[str, str, Callable[[], None], Callable[[], str]]] = {
            "narration": ("Narration", "key moments", lambda: store.set_narration(DEFAULT_NARRATION), narration_title),
            "game_audio_volume": ("Game audio volume", "80", lambda: store.set_game_audio_volume(DEFAULT_GAME_AUDIO_VOLUME), volume_title),
            "replay_autoplay": ("Replay auto-play", "on", lambda: store.set_replay_autoplay(DEFAULT_REPLAY_AUTOPLAY), autoplay_title),
            "hs_install_path": ("Hearthstone install path", "auto-detected", lambda: store.set_hs_install_path(None), install_title),
            "hs_log_path": ("Hearthstone log path", "auto-detected", lambda: store.set_hs_log_path(None), log_title),
            "replay_retention": ("Replay retention", "unlimited", lambda: store.set_replay_retention(DEFAULT_REPLAY_RETENTION), retention_title),
            "global_hotkeys": ("Global hotkeys", "defaults", restore_hotkeys, lambda: "Global hotkeys"),
            "restore_all": ("Restore all defaults", "defaults", restore_all, lambda: "Restore all defaults"),
        }
        label, default, action, title = actions[row]

        def finish() -> None:
            action()
            if row != "restore_all":
                changed(title)

        if delete_armed is None:
            raise RuntimeError("Settings delete action is not active")
        delete_armed.press(
            f"delete:{row}",
            (
                "Press Delete again to restore all defaults"
                if row == "restore_all"
                else f"Press Delete again to reset {label} to {default}"
            ),
            finish,
        )

    def reset_current_now() -> None:
        row = current_row()
        if row == "restore_all":
            restore_all()
            return
        # Reuse the reset table while bypassing ArmedAction's pending state.
        if delete_armed is None:
            raise RuntimeError("Settings delete action is not active")
        delete_armed.disarm()
        resetters: dict[str, tuple[Callable[[], None], Callable[[], str]]] = {
            "narration": (lambda: store.set_narration(DEFAULT_NARRATION), narration_title),
            "game_audio_volume": (lambda: store.set_game_audio_volume(DEFAULT_GAME_AUDIO_VOLUME), volume_title),
            "replay_autoplay": (lambda: store.set_replay_autoplay(DEFAULT_REPLAY_AUTOPLAY), autoplay_title),
            "hs_install_path": (lambda: store.set_hs_install_path(None), install_title),
            "hs_log_path": (lambda: store.set_hs_log_path(None), log_title),
            "replay_retention": (lambda: store.set_replay_retention(DEFAULT_REPLAY_RETENTION), retention_title),
            "global_hotkeys": (restore_hotkeys, lambda: "Global hotkeys"),
        }
        action, title = resetters[row]
        action()
        changed(title)

    spec = SurfaceSpec(
        "Settings",
        WidgetType.VERTICAL_MENU,
        options=options,
        bindings=[
            Binding(Chord("delete"), Command("settings.reset", "Delete: reset this setting, press twice", reset_current)),
            Binding(Chord("delete", shift=True), Command("settings.reset_now", "Shift+Delete: reset this setting without asking", reset_current_now)),
        ],
        slot_fills={
            Slot.ENTER: Command(
                "settings.change",
                "Enter: change this setting",
                activate_current,
            )
        },
        slot_noops={Slot.SEARCH: "No search on this screen"},
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Settings requires a vertical-menu engine")
    engine = surface.engine
    delete_armed = ArmedAction(engine, announcer)
    enter_armed = ArmedAction(engine, announcer)
    return surface
