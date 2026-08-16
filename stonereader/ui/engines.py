"""The two cursor-owning widget-type engines (ADR-0007, ADR-0010)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.registry import Command
from stonereader.ui.surface import MenuOption, SurfaceSpec, WidgetType, ZoneSpec


class VerticalMenuEngine:
    """Interpret a vertical-menu Surface declaration."""

    def __init__(self, spec: SurfaceSpec, announcer: Announcer) -> None:
        if spec.widget_type is not WidgetType.VERTICAL_MENU:
            raise ValueError("VerticalMenuEngine requires a vertical-menu Surface")
        self._spec = spec
        self._announcer = announcer
        self._cursor = 0
        self._subscribers: list[Callable[[], None]] = []

    def subscribe(self, on_change: Callable[[], None]) -> None:
        self._subscribers.append(on_change)

    def options_snapshot(self) -> tuple[list[str], int]:
        """Return rendered option titles and the current cursor."""
        options = self._options()
        return [option.title() for option in options], self._cursor

    @property
    def cursor(self) -> int:
        return self._cursor

    def set_cursor(self, index: int) -> None:
        """Set the cursor without speech, for holder-driven reusable menus."""
        options = self._options()
        target = min(max(index, 0), max(0, len(options) - 1))
        changed = target != self._cursor
        self._cursor = target
        if changed:
            self._notify()

    def refresh(self) -> None:
        """Refresh render subscribers after dynamic titles change."""
        self._options()
        self._notify()

    def widget_type_bindings(self) -> list[tuple[Chord, Command]]:
        return [
            (
                Chord("up"),
                Command("menu.previous", "Up: previous option", self._previous),
            ),
            (
                Chord("down"),
                Command("menu.next", "Down: next option", self._next),
            ),
            (
                Chord("home"),
                Command("menu.first", "Home: first option", self._first),
            ),
            (
                Chord("end"),
                Command("menu.last", "End: last option", self._last),
            ),
            (
                Chord("up", shift=True),
                Command(
                    "menu.reread",
                    "Shift+Up: reread current option",
                    self._reread,
                ),
            ),
        ]

    def on_landing(self, queued: bool = False) -> None:
        options = self._options()
        if not options:
            self._announcer.context_empty(self._spec.name, queued=queued)
            return
        label = (
            self._spec.context_label()
            if self._spec.context_label is not None
            else self._spec.name
        )
        self._announcer.context_entry_menu(
            label,
            options[self._cursor].title(),
            queued=queued,
        )

    def activate_current(self) -> bool:
        """Act on the option, or let the Surface's Enter slot handle it."""
        options = self._options()
        if not options:
            return False
        handler = options[self._cursor].on_enter
        if handler is None:
            return False
        handler()
        self._notify()
        return True

    def _options(self) -> list[MenuOption]:
        provider = self._spec.options
        if provider is None:  # Protected by SurfaceSpec validation.
            return []
        options = provider()
        self._cursor = min(self._cursor, max(0, len(options) - 1))
        return options

    def _previous(self) -> None:
        self._move(-1)

    def _next(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        options = self._options()
        if not options:
            self._announcer.context_empty(self._spec.name)
            return
        target = min(max(self._cursor + delta, 0), len(options) - 1)
        title = options[target].title()
        if target == self._cursor:
            self._announcer.boundary(title)
            return
        self._cursor = target
        self._notify()
        self._announcer.moved(title)

    def _first(self) -> None:
        self._move_to(0)

    def _last(self) -> None:
        options = self._options()
        if not options:
            self._announcer.context_empty(self._spec.name)
            return
        self._move_to(len(options) - 1)

    def _move_to(self, target: int) -> None:
        options = self._options()
        if not options:
            self._announcer.context_empty(self._spec.name)
            return
        changed = target != self._cursor
        self._cursor = target
        if changed:
            self._notify()
        self._announcer.moved(options[self._cursor].title())

    def _reread(self) -> None:
        self.on_landing()

    def _notify(self) -> None:
        for subscriber in tuple(self._subscribers):
            subscriber()


class HorizontalListEngine:
    """Interpret a horizontal-list Surface declaration and its zones."""

    def __init__(self, spec: SurfaceSpec, announcer: Announcer) -> None:
        if spec.widget_type is not WidgetType.HORIZONTAL_LIST:
            raise ValueError("HorizontalListEngine requires a horizontal-list Surface")
        self._spec = spec
        self._announcer = announcer
        self._zones = {zone.zone_id: zone for zone in spec.zones}
        self._active_zone_id = spec.zones[0].zone_id
        self._item_cursors = {zone.zone_id: 0 for zone in spec.zones}
        self._detail_cursors = {zone.zone_id: 0 for zone in spec.zones}
        self._subscribers: list[Callable[[], None]] = []

    def subscribe(self, on_change: Callable[[], None]) -> None:
        self._subscribers.append(on_change)

    def refresh(self) -> None:
        """Notify render subscribers after provider data changes, without speech."""
        self._items()
        self._notify()

    def items_snapshot(self) -> tuple[list[str], int, list[str]]:
        """Return active-zone titles, cursor, and current item details."""
        items = self._items()
        if not items:
            return [], 0, []
        zone = self.current_zone()
        cursor = self._item_cursors[self._active_zone_id]
        return (
            [zone.title(item) for item in items],
            cursor,
            list(zone.detail_lines(items[cursor])),
        )

    def widget_type_bindings(self) -> list[tuple[Chord, Command]]:
        return [
            (
                Chord("left"),
                Command("list.previous", "Left: previous item", self._previous_item),
            ),
            (
                Chord("right"),
                Command("list.next", "Right: next item", self._next_item),
            ),
            (
                Chord("up"),
                Command(
                    "list.detail_previous", "Up: previous detail", self._previous_detail
                ),
            ),
            (
                Chord("down"),
                Command("list.detail_next", "Down: next detail", self._next_detail),
            ),
            (
                Chord("up", shift=True),
                Command("list.reread", "Shift+Up: reread position", self._reread),
            ),
            (
                Chord("down", shift=True),
                Command(
                    "list.read_remaining",
                    "Shift+Down: read remaining details",
                    self._read_remaining,
                ),
            ),
            (
                Chord("home"),
                Command("list.first", "Home: first item", self._first_item),
            ),
            (
                Chord("end"),
                Command("list.last", "End: last item", self._last_item),
            ),
        ]

    def zone_bindings(self) -> list[tuple[Chord, Command]]:
        bindings: list[tuple[Chord, Command]] = []
        for zone in self._spec.zones:
            if zone.jump_chord is None:
                continue
            bindings.append(
                (
                    zone.jump_chord,
                    Command(
                        f"zone.{zone.zone_id}",
                        zone.help_phrase,
                        lambda zone_id=zone.zone_id: self.switch_zone(zone_id),
                    ),
                )
            )
        return bindings

    def on_landing(self, queued: bool = False) -> None:
        self._announce_context(queued=queued, current_line=False)

    def switch_zone(self, zone_id: str) -> None:
        """Switch to a non-empty zone and fire its context-entry utterance."""
        try:
            zone = self._zones[zone_id]
        except KeyError as error:
            raise ValueError(f"Unknown zone id: {zone_id}") from error
        if not zone.items():
            self._announcer.noop(f"No {zone.label} on this screen")
            return
        changed = zone_id != self._active_zone_id
        self._active_zone_id = zone_id
        self._clamp(zone)
        if changed:
            self._notify()
        self.on_landing()

    def jump_to_position(self, n: int) -> None:
        """Move to a one-based item position, clamped to the active zone."""
        items = self._items()
        if not items:
            # ADR-0004: a bound key never dies silently.
            self._announcer.context_empty(self._context_label())
            return
        target = min(max(n - 1, 0), len(items) - 1)
        self._land_on_item(target, items)

    def page(self, delta_items: int) -> None:
        """Move by a caller-defined page size, clamped to the active zone."""
        items = self._items()
        if not items:
            # ADR-0004: PageUp/PageDown fill a universal slot; never silent.
            self._announcer.context_empty(self._context_label())
            return
        target = min(
            max(self._item_cursors[self._active_zone_id] + delta_items, 0),
            len(items) - 1,
        )
        self._land_on_item(target, items)

    def current_item(self) -> Any | None:
        items = self._items()
        if not items:
            return None
        return items[self._item_cursors[self._active_zone_id]]

    def current_zone(self) -> ZoneSpec:
        return self._zones[self._active_zone_id]

    def _previous_item(self) -> None:
        self._move_item(-1)

    def _next_item(self) -> None:
        self._move_item(1)

    def _move_item(self, delta: int) -> None:
        items = self._items()
        if not items:
            self._announcer.context_empty(self._context_label())
            return
        zone_id = self._active_zone_id
        current = self._item_cursors[zone_id]
        target = min(max(current + delta, 0), len(items) - 1)
        title = self.current_zone().title(items[target])
        if target == current:
            # ADR-0007: an item-axis boundary repeats the current Title line.
            detail_changed = self._detail_cursors[zone_id] != 0
            self._detail_cursors[zone_id] = 0
            if detail_changed:
                self._notify()
            self._announcer.boundary(title)
            return
        self._item_cursors[zone_id] = target
        self._detail_cursors[zone_id] = 0
        self._notify()
        self._announcer.moved(title)

    def _previous_detail(self) -> None:
        self._move_detail(-1)

    def _next_detail(self) -> None:
        self._move_detail(1)

    def _move_detail(self, delta: int) -> None:
        lines = self._current_lines()
        if not lines:
            self._announcer.context_empty(self._context_label())
            return
        zone_id = self._active_zone_id
        current = self._detail_cursors[zone_id]
        target = min(max(current + delta, 0), len(lines) - 1)
        if target == current:
            # ADR-0007: detail boundaries repeat the line the cursor rests on.
            self._announcer.boundary(lines[current])
            return
        self._detail_cursors[zone_id] = target
        self._notify()
        self._announcer.moved(lines[target])

    def _reread(self) -> None:
        self._announce_context(queued=False, current_line=True)

    def _read_remaining(self) -> None:
        lines = self._current_lines()
        if not lines:
            self._announcer.context_empty(self._context_label())
            return
        start = self._detail_cursors[self._active_zone_id]
        for index, line in enumerate(lines[start:]):
            self._announcer.moved(line, queued=index > 0)

    def _first_item(self) -> None:
        items = self._items()
        if not items:
            # ADR-0004: Home/End are universal keys; never silent.
            self._announcer.context_empty(self._context_label())
            return
        self._land_on_item(0, items)

    def _last_item(self) -> None:
        items = self._items()
        if not items:
            self._announcer.context_empty(self._context_label())
            return
        self._land_on_item(len(items) - 1, items)

    def _land_on_item(self, target: int, items: list[Any]) -> None:
        zone_id = self._active_zone_id
        changed = (
            target != self._item_cursors[zone_id] or self._detail_cursors[zone_id] != 0
        )
        self._item_cursors[zone_id] = target
        self._detail_cursors[zone_id] = 0
        if changed:
            self._notify()
        self._announcer.moved(self.current_zone().title(items[target]))

    def _announce_context(self, *, queued: bool, current_line: bool) -> None:
        items = self._items()
        label = self._context_label()
        if not items:
            self._announcer.context_empty(label, queued=queued)
            return
        zone_id = self._active_zone_id
        item_index = self._item_cursors[zone_id]
        if current_line:
            title = self._current_lines()[self._detail_cursors[zone_id]]
        else:
            title = self.current_zone().title(items[item_index])
        self._announcer.context_entry(
            label,
            title,
            item_index + 1,
            len(items),
            queued=queued,
        )

    def _context_label(self) -> str:
        if self._spec.context_label is not None:
            return self._spec.context_label()
        if len(self._spec.zones) > 1:
            return self.current_zone().label
        return self._spec.name

    def _items(self) -> list[Any]:
        zone = self.current_zone()
        items = list(zone.items())
        self._clamp(zone, items)
        return items

    def _clamp(self, zone: ZoneSpec, items: list[Any] | None = None) -> None:
        values = list(zone.items()) if items is None else items
        zone_id = zone.zone_id
        if not values:
            self._item_cursors[zone_id] = 0
            self._detail_cursors[zone_id] = 0
            return
        item_cursor = min(self._item_cursors[zone_id], len(values) - 1)
        self._item_cursors[zone_id] = item_cursor
        lines = [
            zone.title(values[item_cursor]),
            *zone.detail_lines(values[item_cursor]),
        ]
        self._detail_cursors[zone_id] = min(
            self._detail_cursors[zone_id],
            len(lines) - 1,
        )

    def _current_lines(self) -> list[str]:
        items = self._items()
        if not items:
            return []
        zone = self.current_zone()
        item = items[self._item_cursors[self._active_zone_id]]
        return [zone.title(item), *zone.detail_lines(item)]

    def _notify(self) -> None:
        for subscriber in tuple(self._subscribers):
            subscriber()
