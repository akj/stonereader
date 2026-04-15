"""Tests for NavigationController."""

from __future__ import annotations

from typing import Callable, Dict

import wx

from stonereader.input_layer import InputLayer

# wx.App must exist before creating any wx objects
_app = wx.App(False)


class _StubPresenter:
    """Minimal presenter for testing navigation."""

    def __init__(self, name: str) -> None:
        self._name = name

    def get_key_map(self) -> Dict[str, Callable[[], None]]:
        return {"enter": lambda: None}


def _make_controller():
    """Create a NavigationController with a fresh frame."""
    from stonereader.app import NavigationController

    frame = wx.Frame(None)
    sizer = wx.BoxSizer(wx.VERTICAL)
    frame.SetSizer(sizer)
    layer = InputLayer(frame)
    nav = NavigationController(frame, sizer, layer)
    return nav, frame, layer


def test_register_panel():
    nav, frame, _ = _make_controller()
    panel = wx.Panel(frame)
    presenter = _StubPresenter("test")
    nav.register_panel("Test", panel, presenter, panel)
    assert "Test" in nav._panels
    assert not panel.IsShown()
    frame.Destroy()


def test_show_panel_makes_visible():
    nav, frame, _ = _make_controller()
    panel = wx.Panel(frame)
    presenter = _StubPresenter("test")
    nav.register_panel("Test", panel, presenter, panel)
    nav.show_panel("Test")
    assert panel.IsShown()
    assert nav.current_panel_name == "Test"
    frame.Destroy()


def test_show_panel_hides_previous():
    nav, frame, _ = _make_controller()
    panel_a = wx.Panel(frame)
    panel_b = wx.Panel(frame)
    nav.register_panel("A", panel_a, _StubPresenter("a"), panel_a)
    nav.register_panel("B", panel_b, _StubPresenter("b"), panel_b)
    nav.show_panel("A")
    nav.show_panel("B")
    assert not panel_a.IsShown()
    assert panel_b.IsShown()
    frame.Destroy()


def test_go_back_pops_stack():
    nav, frame, _ = _make_controller()
    panel_a = wx.Panel(frame)
    panel_b = wx.Panel(frame)
    nav.register_panel("A", panel_a, _StubPresenter("a"), panel_a)
    nav.register_panel("B", panel_b, _StubPresenter("b"), panel_b)
    nav.show_panel("A")
    nav.show_panel("B")
    nav.go_back()
    assert panel_a.IsShown()
    assert not panel_b.IsShown()
    assert nav.current_panel_name == "A"
    frame.Destroy()


def test_go_back_at_root_does_nothing():
    nav, frame, _ = _make_controller()
    panel = wx.Panel(frame)
    nav.register_panel("Home", panel, _StubPresenter("home"), panel)
    nav.show_panel("Home")
    nav.go_back()  # Should not crash
    assert panel.IsShown()
    assert nav.current_panel_name == "Home"
    frame.Destroy()


def test_show_panel_adds_escape_to_non_home():
    nav, frame, layer = _make_controller()
    panel_a = wx.Panel(frame)
    panel_b = wx.Panel(frame)
    nav.register_panel("Home", panel_a, _StubPresenter("home"), panel_a)
    nav.register_panel("Sub", panel_b, _StubPresenter("sub"), panel_b)
    nav.show_panel("Home")
    nav.show_panel("Sub")
    # The active key map should have escape and back
    assert "escape" in layer._current_key_map
    assert "back" in layer._current_key_map
    frame.Destroy()


def test_home_panel_has_no_escape():
    nav, frame, layer = _make_controller()
    panel = wx.Panel(frame)
    nav.register_panel("Home", panel, _StubPresenter("home"), panel)
    nav.show_panel("Home")
    # Home (stack length 1) should NOT have escape/back
    assert "escape" not in layer._current_key_map
    assert "back" not in layer._current_key_map
    frame.Destroy()


def test_current_panel_name_empty_initially():
    nav, frame, _ = _make_controller()
    assert nav.current_panel_name is None
    frame.Destroy()


def test_activate_view_called_on_show():
    """Verify InputLayer gets the correct key map on panel show."""
    nav, frame, layer = _make_controller()
    panel = wx.Panel(frame)

    class MapPresenter:
        def get_key_map(self):
            return {"x": lambda: None}

    nav.register_panel("Test", panel, MapPresenter(), panel)
    nav.show_panel("Test")
    # The key map should include "x" from the presenter
    assert "x" in layer._current_key_map
    frame.Destroy()


def test_go_back_restores_previous_key_map():
    """Verify going back restores the previous panel's key map."""
    nav, frame, layer = _make_controller()
    panel_a = wx.Panel(frame)
    panel_b = wx.Panel(frame)

    class PresenterA:
        def get_key_map(self):
            return {"a": lambda: None}

    class PresenterB:
        def get_key_map(self):
            return {"b": lambda: None}

    nav.register_panel("Home", panel_a, PresenterA(), panel_a)
    nav.register_panel("Sub", panel_b, PresenterB(), panel_b)
    nav.show_panel("Home")
    nav.show_panel("Sub")
    assert "b" in layer._current_key_map
    nav.go_back()
    assert "a" in layer._current_key_map
    assert "b" not in layer._current_key_map
    frame.Destroy()


def test_deep_navigation_stack():
    """Verify 3-level deep navigation works correctly."""
    nav, frame, _ = _make_controller()
    panel_a = wx.Panel(frame)
    panel_b = wx.Panel(frame)
    panel_c = wx.Panel(frame)
    nav.register_panel("Home", panel_a, _StubPresenter("a"), panel_a)
    nav.register_panel("Level1", panel_b, _StubPresenter("b"), panel_b)
    nav.register_panel("Level2", panel_c, _StubPresenter("c"), panel_c)
    nav.show_panel("Home")
    nav.show_panel("Level1")
    nav.show_panel("Level2")
    assert nav.current_panel_name == "Level2"
    assert panel_c.IsShown()
    nav.go_back()
    assert nav.current_panel_name == "Level1"
    assert panel_b.IsShown()
    nav.go_back()
    assert nav.current_panel_name == "Home"
    assert panel_a.IsShown()
    frame.Destroy()


def test_replace_panel_destroys_old():
    nav, frame, _ = _make_controller()
    panel_old = wx.Panel(frame)
    panel_new = wx.Panel(frame)
    presenter_old = _StubPresenter("old")
    presenter_new = _StubPresenter("new")
    nav.register_panel("Slot", panel_old, presenter_old, panel_old)
    nav.replace_panel("Slot", panel_new, presenter_new, panel_new)
    assert nav._panels["Slot"] is panel_new
    assert nav._presenters["Slot"] is presenter_new
    frame.Destroy()


def test_replace_panel_cleans_stack():
    nav, frame, _ = _make_controller()
    panel_home = wx.Panel(frame)
    panel_old = wx.Panel(frame)
    panel_new = wx.Panel(frame)
    nav.register_panel("Home", panel_home, _StubPresenter("home"), panel_home)
    nav.register_panel("Sub", panel_old, _StubPresenter("old"), panel_old)
    nav.show_panel("Home")
    nav.show_panel("Sub")
    assert "Sub" in nav._stack
    nav.replace_panel("Sub", panel_new, _StubPresenter("new"), panel_new)
    assert "Sub" not in nav._stack
    frame.Destroy()


def test_replace_panel_unregistered_name():
    """replace_panel on a new name behaves like register_panel."""
    nav, frame, _ = _make_controller()
    panel = wx.Panel(frame)
    presenter = _StubPresenter("fresh")
    nav.replace_panel("Fresh", panel, presenter, panel)
    assert "Fresh" in nav._panels
    assert not panel.IsShown()
    frame.Destroy()


def test_get_presenter_returns_registered():
    nav, frame, _ = _make_controller()
    panel = wx.Panel(frame)
    presenter = _StubPresenter("test")
    nav.register_panel("Test", panel, presenter, panel)
    assert nav.get_presenter("Test") is presenter
    frame.Destroy()


def test_get_presenter_returns_none_for_unknown():
    nav, frame, _ = _make_controller()
    assert nav.get_presenter("Unknown") is None
    frame.Destroy()
