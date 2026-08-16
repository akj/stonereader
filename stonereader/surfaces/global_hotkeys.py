"""Global-hotkey rebinding Surface and ADR-0011 acceptance policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from stonereader.services._hotkeys import HotkeyCommand, HotkeyMap
from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import VerticalMenuEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, MenuOption, SurfaceSpec, WidgetType


class CaptureSink(Protocol):
    def enter_capture_mode(
        self,
        on_chord: Callable[[Chord], None],
        prompt_escape: Callable[[], None],
    ) -> None: ...

    def exit_capture_mode(self) -> None: ...


def build_global_hotkeys(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    sink: CaptureSink,
    hotkeys: HotkeyMap,
) -> ActiveSurface:
    """Build the four-row hotkey menu."""
    engine: VerticalMenuEngine | None = None
    armed: ArmedAction | None = None
    pending_single: Chord | None = None

    def row_title(command: HotkeyCommand) -> str:
        return f"{command.label}, {hotkeys.current_chord(command.command_id).spoken()}"

    def selected() -> HotkeyCommand:
        if engine is None:
            raise RuntimeError("Global hotkeys engine is not active")
        return hotkeys.commands[engine.cursor]

    def finish(command: HotkeyCommand) -> None:
        if engine is None:
            raise RuntimeError("Global hotkeys engine is not active")
        engine.refresh()
        announcer.moved(row_title(command))

    def start_capture(command: HotkeyCommand) -> None:
        nonlocal pending_single
        pending_single = None
        registries = tuple(
            (name, surface.registry) for name, surface in nav.all_surfaces()
        )
        announcer.noop(
            f"Press the new shortcut for {command.label}. Escape cancels."
        )

        def cancel() -> None:
            # Cancel re-lands verbally on the unchanged row (ADR-0011 ruling).
            sink.exit_capture_mode()
            announcer.moved(row_title(command))

        def candidate(chord: Chord) -> None:
            nonlocal pending_single
            if not (chord.ctrl or chord.shift or chord.alt):
                pending_single = None
                sink.exit_capture_mode()
                announcer.noop("A shortcut needs a modifier key")
                return
            current = hotkeys.current_chord(command.command_id)
            if chord == current:
                sink.exit_capture_mode()
                finish(command)
                return
            owner = hotkeys.is_taken(
                chord,
                registries,
            )
            if owner is not None:
                pending_single = None
                announcer.noop(f"{chord.spoken()} is taken by {owner}")
                return
            modifier_count = sum((chord.ctrl, chord.shift, chord.alt))
            if modifier_count == 1 and pending_single != chord:
                pending_single = chord
                announcer.noop(
                    f"{chord.spoken()} is a single-modifier shortcut; other apps, "
                    "including Hearthstone Access, may use it. Press it again to "
                    "bind anyway"
                )
                return
            failure = hotkeys.rebind(command.command_id, chord)
            if failure is not None:
                pending_single = None
                announcer.noop(failure)
                return
            sink.exit_capture_mode()
            finish(command)

        sink.enter_capture_mode(candidate, cancel)

    def reset(command: HotkeyCommand) -> None:
        failure = hotkeys.rebind(command.command_id, command.default_chord)
        if failure is not None:
            announcer.noop(failure)
            return
        finish(command)

    def arm_reset() -> None:
        command = selected()
        if armed is None:
            raise RuntimeError("Global hotkeys reset action is not active")
        armed.press(
            command.command_id,
            f"Press Delete again to reset {command.label} to {command.default_chord.spoken()}",
            lambda: reset(command),
        )

    def reset_now() -> None:
        reset(selected())

    def activate_current() -> None:
        if engine is None:
            raise RuntimeError("Global hotkeys engine is not active")
        if not engine.activate_current():
            announcer.noop("Nothing to do here")

    def options() -> list[MenuOption]:
        return [
            MenuOption(
                command.command_id,
                lambda command=command: row_title(command),
                lambda command=command: start_capture(command),
            )
            for command in hotkeys.commands
        ]

    spec = SurfaceSpec(
        "Global hotkeys",
        WidgetType.VERTICAL_MENU,
        options=options,
        bindings=[
            Binding(
                Chord("delete"),
                Command(
                    "global_hotkeys.reset",
                    "Delete: reset this shortcut, press twice",
                    arm_reset,
                ),
            ),
            Binding(
                Chord("delete", shift=True),
                Command(
                    "global_hotkeys.reset_now",
                    "Shift+Delete: reset this shortcut without asking",
                    reset_now,
                ),
            ),
        ],
        slot_fills={
            Slot.ENTER: Command(
                "global_hotkeys.capture",
                "Enter: record a new shortcut",
                activate_current,
            )
        },
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, VerticalMenuEngine):
        raise TypeError("Global hotkeys requires a vertical-menu engine")
    engine = surface.engine
    armed = ArmedAction(engine, announcer)
    return surface
