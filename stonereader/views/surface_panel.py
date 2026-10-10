"""Generic render-only panel for declarative Surfaces (ADR-0010)."""

from __future__ import annotations

import wx

from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine

# Spacing in device-independent pixels: pane margin, gap between rows, and
# the inset of row text inside the current-row highlight.
_MARGIN = 8
_ROW_GAP = 4
_INSET = 6


class _RenderOnlyPanel(wx.Panel):
    """A panel that never takes keyboard focus (ADR-0010)."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetCanFocus(False)

    def AcceptsFocusFromKeyboard(self) -> bool:  # noqa: N802 -- wx override
        # SetCanFocus is a no-op for panels on Windows, where activating the
        # frame would otherwise hand focus to the first shown panel.
        return False


class SurfacePanel(_RenderOnlyPanel):
    """Render engine snapshots without owning input or speech.

    A horizontal list shows its current item's detail lines in a pane beside
    the list (ADR-0017); a vertical menu has no details. No child takes
    keyboard focus (ADR-0010).
    """

    def __init__(
        self,
        parent: wx.Window,
        engine: VerticalMenuEngine | HorizontalListEngine,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._list = _ListPane(self)
        self._details: _DetailPane | None = None
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self._list, 1, wx.EXPAND)
        if isinstance(engine, HorizontalListEngine):
            self._details = _DetailPane(self)
            sizer.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.EXPAND)
            sizer.Add(self._details, 1, wx.EXPAND)
        self.SetSizer(sizer)
        engine.subscribe(self._render)
        self._render()

    def _render(self) -> None:
        if isinstance(self._engine, HorizontalListEngine):
            titles, cursor, details = self._engine.items_snapshot()
        else:
            titles, cursor = self._engine.options_snapshot()
            details = []
        self.Freeze()
        try:
            self._list.set_rows(titles, cursor)
            if self._details is not None:
                self._details.set_lines(details)
        finally:
            self.Thaw()


class _ListPane(_RenderOnlyPanel):
    """Show the rows that fit, scrolled like a list box around the cursor."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetMinSize(wx.Size(1, 1))
        self._titles: list[str] = []
        self._cursor = 0
        self._top = 0
        self._rows: list[wx.StaticText] = []
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def set_rows(self, titles: list[str], cursor: int) -> None:
        self._titles = titles
        self._cursor = min(max(cursor, 0), max(len(titles) - 1, 0))
        self._place_rows()

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._place_rows()
        event.Skip()

    def _pitch(self) -> int:
        return self.GetCharHeight() + self.FromDIP(_ROW_GAP)

    def _place_rows(self) -> None:
        width, height = self.GetClientSize()
        margin, inset = self.FromDIP(_MARGIN), self.FromDIP(_INSET)
        text_height = self.GetCharHeight()
        pitch = self._pitch()
        capacity = max(1, (height - 2 * margin) // pitch)
        self._top = _scrolled_top(self._top, self._cursor, len(self._titles), capacity)
        visible = self._titles[self._top : self._top + capacity]
        while len(self._rows) < len(visible):
            row = wx.StaticText(self, style=wx.ST_NO_AUTORESIZE | wx.ST_ELLIPSIZE_END)
            self._rows.append(row)
        normal = self.GetFont()
        for index, row in enumerate(self._rows):
            if index >= len(visible):
                row.Hide()
                continue
            current = self._top + index == self._cursor
            row.SetSize(
                margin + inset,
                margin + index * pitch + (pitch - text_height) // 2,
                max(width - 2 * (margin + inset), 1),
                text_height,
            )
            row.SetFont(normal.Bold() if current else normal)
            row.SetBackgroundColour(
                _system(wx.SYS_COLOUR_HIGHLIGHT)
                if current
                else self.GetBackgroundColour()
            )
            row.SetForegroundColour(
                _system(wx.SYS_COLOUR_HIGHLIGHTTEXT)
                if current
                else self.GetForegroundColour()
            )
            row.SetLabelText(visible[index])
            row.Show()
        self.Refresh()

    def _on_paint(self, event: wx.PaintEvent) -> None:
        del event
        dc = wx.PaintDC(self)
        if not self._titles:
            return
        # The highlight band pads the current row's text on every side.
        margin, pitch = self.FromDIP(_MARGIN), self._pitch()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(_system(wx.SYS_COLOUR_HIGHLIGHT)))
        dc.DrawRectangle(
            margin,
            margin + (self._cursor - self._top) * pitch,
            self.GetClientSize().width - 2 * margin,
            pitch,
        )


class _DetailPane(_RenderOnlyPanel):
    """Show the current item's detail lines, wrapped to the pane's width."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.SetMinSize(wx.Size(1, 1))
        self._texts: list[str] = []
        self._lines: list[wx.StaticText] = []
        self._column = wx.BoxSizer(wx.VERTICAL)
        # Line up the first detail line with the first list row's text.
        self._column.AddSpacer(self.FromDIP(_ROW_GAP) // 2)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._column, 1, wx.EXPAND | wx.ALL, self.FromDIP(_MARGIN))
        self.SetSizer(sizer)
        self.Bind(wx.EVT_SIZE, self._on_size)

    def set_lines(self, texts: list[str]) -> None:
        self._texts = texts
        self._wrap_lines()

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._wrap_lines()
        event.Skip()

    def _wrap_lines(self) -> None:
        width = self.GetClientSize().width - 2 * self.FromDIP(_MARGIN)
        while len(self._lines) < len(self._texts):
            line = wx.StaticText(self)
            self._column.Add(line, 0, wx.EXPAND | wx.BOTTOM, self.FromDIP(_ROW_GAP))
            self._lines.append(line)
        for index, line in enumerate(self._lines):
            if index >= len(self._texts):
                line.Hide()
                continue
            line.SetLabelText(self._texts[index])
            if width > 0:
                line.Wrap(width)
            line.Show()
        self.Layout()


def _scrolled_top(top: int, cursor: int, count: int, capacity: int) -> int:
    """Scroll the least distance that keeps the cursor among the shown rows."""
    top = max(min(top, cursor), cursor - capacity + 1)
    return max(0, min(top, count - capacity))


def _system(colour_id: int) -> wx.Colour:
    return wx.SystemSettings.GetColour(colour_id)
