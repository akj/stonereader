import wx

from stonereader.input_layer import InputLayer, _key_spec_from_event

# wx.App must exist before creating any wx objects
_app = wx.App(False)


def _make_key_event(keycode: int, shift: bool = False, ctrl: bool = False, alt: bool = False) -> wx.KeyEvent:
    """Create a wx.KeyEvent with the given keycode and modifiers."""
    event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    event.SetKeyCode(keycode)
    event.shiftDown = shift
    event.controlDown = ctrl
    event.altDown = alt
    return event


def test_key_spec_arrow_keys():
    assert _key_spec_from_event(_make_key_event(wx.WXK_LEFT)) == "left"
    assert _key_spec_from_event(_make_key_event(wx.WXK_RIGHT)) == "right"
    assert _key_spec_from_event(_make_key_event(wx.WXK_UP)) == "up"
    assert _key_spec_from_event(_make_key_event(wx.WXK_DOWN)) == "down"


def test_key_spec_letter_keys():
    assert _key_spec_from_event(_make_key_event(ord("B"))) == "b"
    assert _key_spec_from_event(_make_key_event(ord("H"))) == "h"


def test_key_spec_shift_letter():
    assert _key_spec_from_event(_make_key_event(ord("T"), shift=True)) == "shift+t"


def test_key_spec_shift_arrow_not_prefixed():
    assert _key_spec_from_event(_make_key_event(wx.WXK_UP, shift=True)) == "up"


def test_key_spec_enter():
    assert _key_spec_from_event(_make_key_event(wx.WXK_RETURN)) == "enter"
    assert _key_spec_from_event(_make_key_event(wx.WXK_NUMPAD_ENTER)) == "enter"


def test_key_spec_escape():
    assert _key_spec_from_event(_make_key_event(wx.WXK_ESCAPE)) == "escape"


def test_key_spec_unmapped_returns_empty():
    assert _key_spec_from_event(_make_key_event(wx.WXK_F1)) == ""


def test_input_layer_calls_mapped_callback():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"b": lambda: called.append("b")})
    event = _make_key_event(ord("B"))
    layer._on_char_hook(event)
    assert called == ["b"]
    frame.Destroy()


def test_input_layer_text_mode_skips_callbacks():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"b": lambda: called.append("b")})
    layer.enter_text_mode()
    event = _make_key_event(ord("B"))
    layer._on_char_hook(event)
    assert called == []
    frame.Destroy()


def test_input_layer_ctrl_always_passes_through():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"c": lambda: called.append("c")})
    event = _make_key_event(ord("C"), ctrl=True)
    layer._on_char_hook(event)
    assert called == []
    frame.Destroy()


def test_input_layer_alt_always_passes_through():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"f": lambda: called.append("f")})
    event = _make_key_event(ord("F"), alt=True)
    layer._on_char_hook(event)
    assert called == []
    frame.Destroy()


def test_activate_view_replaces_key_map():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("v1", {"b": lambda: called.append("v1")})
    layer.activate_view("v2", {"b": lambda: called.append("v2")})
    event = _make_key_event(ord("B"))
    layer._on_char_hook(event)
    assert called == ["v2"]
    frame.Destroy()


def test_activate_view_exits_text_mode():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    layer.enter_text_mode()
    assert layer._text_mode is True
    layer.activate_view("v1", {})
    assert layer._text_mode is False
    frame.Destroy()


def test_key_spec_delete():
    event = _make_key_event(wx.WXK_DELETE)
    assert _key_spec_from_event(event) == "delete"


def test_input_layer_delete_key_dispatches():
    frame = wx.Frame(None)
    layer = InputLayer(frame)
    called = []
    layer.activate_view("test", {"delete": lambda: called.append("delete")})
    event = _make_key_event(wx.WXK_DELETE)
    layer._on_char_hook(event)
    assert called == ["delete"]
    frame.Destroy()
