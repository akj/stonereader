"""The visual window: path heading, scrolled list, and detail pane (ADR-0017)."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
import wx

import stonereader.app as app_module
from stonereader.app import MainWindow
from stonereader.db import get_connection
from stonereader.services._audio_player import AudioPlayer
from stonereader.speech_service import SpeechService
from stonereader.ui import (
    Chord,
    HorizontalListEngine,
    MenuOption,
    SurfaceSpec,
    WidgetType,
    ZoneSpec,
    build_active_surface,
)
from stonereader.views.surface_panel import SurfacePanel

from tests.support import FakeSpeech

CARDS = [f"Card {index}" for index in range(7_898)]


class _SilentBackend:
    def play(self, wav_bytes: bytes) -> None:
        del wav_bytes

    def stop(self) -> None:
        pass


@pytest.fixture
def window(monkeypatch: pytest.MonkeyPatch) -> Iterator[MainWindow]:
    app = wx.App()
    # The real frame, kept away from the User's screen reader and profile.
    monkeypatch.setattr(
        app_module, "SpeechService", lambda: SpeechService(FakeSpeech())
    )
    monkeypatch.setattr(
        app_module, "get_connection", lambda: get_connection(":memory:")
    )
    frame = MainWindow(AudioPlayer(_SilentBackend(), lambda: 100))
    frame.SetClientSize(wx.Size(640, 400))
    register(frame)
    try:
        yield frame
    finally:
        frame.Destroy()
        app.Destroy()


def register(frame: MainWindow) -> None:
    def menu(name: str, display_name: Callable[[], str] | None = None) -> SurfaceSpec:
        return SurfaceSpec(
            name,
            WidgetType.VERTICAL_MENU,
            options=lambda: [
                MenuOption("first", lambda: "First option", lambda: None),
                MenuOption("second", lambda: "Second option", lambda: None),
            ],
            display_name=display_name,
        )

    specs = [
        menu("Home"),
        menu("Decks"),
        menu("Deck detail", lambda: "Odd Hunter"),
        SurfaceSpec(
            "Deck cards",
            WidgetType.HORIZONTAL_LIST,
            zones=[
                ZoneSpec(
                    "cards",
                    "Cards",
                    lambda: CARDS,
                    str,
                    lambda card: [f"{card} costs 1 mana", f"{card} is common"],
                )
            ],
            display_name=lambda: "Odd Hunter cards",
        ),
    ]
    for spec in specs:
        frame.nav.register(
            spec.name,
            lambda spec=spec: build_active_surface(
                spec, frame.announcer, frame.universal_bindings, frame.nav
            ),
        )


def press(frame: MainWindow, key: str) -> None:
    surface = frame._current_surface
    assert surface is not None
    assert surface.registry.dispatch(Chord(key)).handled


def current_panel(frame: MainWindow) -> SurfacePanel:
    panel = frame._current_panel
    assert panel is not None
    return panel


def shown_rows(panel: SurfacePanel) -> list[str]:
    return [row.GetLabelText() for row in panel._list._rows if row.IsShown()]


def highlighted_rows(panel: SurfacePanel) -> list[str]:
    highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
    return [
        row.GetLabelText()
        for row in panel._list._rows
        if row.IsShown() and row.GetBackgroundColour() == highlight
    ]


def shown_details(panel: SurfacePanel) -> list[str]:
    assert panel._details is not None
    return [line.GetLabelText() for line in panel._details._lines if line.IsShown()]


def test_heading_shows_the_stack_path_and_title_the_current_surface(
    window: MainWindow,
) -> None:
    nav = window.nav

    nav.jump("Home")
    assert window._heading.GetLabelText() == "Home"
    nav.jump("Decks")
    nav.drill_down("Deck detail")
    nav.drill_down("Deck cards")
    assert window._heading.GetLabelText() == "Decks › Odd Hunter › Odd Hunter cards"
    assert window.GetTitle() == "Odd Hunter cards — StoneReader"
    nav.back()
    assert window._heading.GetLabelText() == "Decks › Odd Hunter"
    assert window.GetTitle() == "Odd Hunter — StoneReader"
    nav.jump("Home")
    assert window._heading.GetLabelText() == "Home"


def test_current_item_details_sit_beside_the_list(window: MainWindow) -> None:
    window.nav.jump_path(["Home", "Decks", "Deck detail", "Deck cards"])
    panel = current_panel(window)
    assert panel._details is not None

    assert highlighted_rows(panel) == ["Card 0"]
    assert shown_details(panel) == ["Card 0 costs 1 mana", "Card 0 is common"]
    press(window, "right")
    assert highlighted_rows(panel) == ["Card 1"]
    assert shown_details(panel) == ["Card 1 costs 1 mana", "Card 1 is common"]

    list_rect, detail_rect = panel._list.GetRect(), panel._details.GetRect()
    assert detail_rect.GetLeft() > list_rect.GetRight()
    assert detail_rect.GetTop() == list_rect.GetTop()


def test_vertical_menu_has_no_detail_pane(window: MainWindow) -> None:
    window.nav.jump("Decks")
    panel = current_panel(window)

    assert panel._details is None
    assert shown_rows(panel) == ["First option", "Second option"]
    press(window, "down")
    assert highlighted_rows(panel) == ["Second option"]


def test_long_list_scrolls_to_keep_the_current_row_visible(
    window: MainWindow,
) -> None:
    window.nav.jump_path(["Home", "Decks", "Deck detail", "Deck cards"])
    panel = current_panel(window)
    engine = window.nav.peek("Deck cards").engine
    assert isinstance(engine, HorizontalListEngine)

    rows = shown_rows(panel)
    # The pane shows as many rows as its height allows, from the top.
    assert 5 < len(rows) < 50
    assert rows == CARDS[: len(rows)]

    engine.jump_to_position(4_001)
    rows = shown_rows(panel)
    assert highlighted_rows(panel) == ["Card 4000"]
    start = CARDS.index(rows[0])
    assert rows == CARDS[start : start + len(rows)]

    press(window, "end")
    rows = shown_rows(panel)
    assert rows[-1] == "Card 7897"
    assert highlighted_rows(panel) == ["Card 7897"]
    # Moving back inside the shown rows moves the highlight, not the list.
    press(window, "left")
    assert shown_rows(panel) == rows
    assert highlighted_rows(panel) == ["Card 7896"]

    press(window, "home")
    assert shown_rows(panel)[0] == "Card 0"
    assert highlighted_rows(panel) == ["Card 0"]


def test_resizing_changes_how_many_rows_fit(window: MainWindow) -> None:
    window.nav.jump_path(["Home", "Decks", "Deck detail", "Deck cards"])
    panel = current_panel(window)
    press(window, "end")
    tall = shown_rows(panel)

    window.SetClientSize(wx.Size(640, 200))
    short = shown_rows(panel)

    assert len(short) < len(tall)
    assert short[-1] == "Card 7897"
    assert highlighted_rows(panel) == ["Card 7897"]


def test_frame_activation_finds_no_child_to_focus(window: MainWindow) -> None:
    # ADR-0010: the frame-level input sink is the only keyboard entry point.
    # Activating a frame focuses its first child that wx's C++ side reports
    # as able to take focus from the keyboard.
    window.nav.jump("Decks")
    window.nav.jump_path(["Home", "Decks", "Deck detail", "Deck cards"])

    def descendants(parent: wx.Window) -> Iterator[wx.Window]:
        for child in parent.GetChildren():
            yield child
            yield from descendants(child)

    focusable = [
        type(child).__name__
        for child in descendants(window)
        if child.CanAcceptFocusFromKeyboard()
    ]
    assert focusable == []
