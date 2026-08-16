from stonereader.views.surface_panel import SurfacePanel, _WINDOW_RADIUS


def test_render_window_is_bounded_and_keeps_cursor_visible():
    titles = [f"Card {index}" for index in range(7_898)]
    cursor = 4_000

    lines = SurfacePanel._window(object(), titles, cursor)  # type: ignore[arg-type]

    assert len(lines) == _WINDOW_RADIUS * 2 + 1
    assert lines[0] == (f"Card {cursor - _WINDOW_RADIUS}", False)
    assert lines[_WINDOW_RADIUS] == (f"> Card {cursor}", True)
    assert lines[-1] == (f"Card {cursor + _WINDOW_RADIUS}", False)
