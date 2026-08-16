"""Generic render-only panel for declarative Surfaces (ADR-0010)."""

from __future__ import annotations

import wx

from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine

_WINDOW_RADIUS = 50


class SurfacePanel(wx.Panel):
    """Render engine snapshots without owning input or speech."""

    def __init__(
        self,
        parent: wx.Window,
        engine: VerticalMenuEngine | HorizontalListEngine,
    ) -> None:
        super().__init__(parent)
        self.SetCanFocus(False)
        self._engine = engine
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self._rows: list[wx.StaticText] = []
        self.SetSizer(self._sizer)
        engine.subscribe(self._render)
        self._render()

    def _render(self) -> None:
        self.Freeze()
        try:
            if isinstance(self._engine, VerticalMenuEngine):
                titles, cursor = self._engine.options_snapshot()
                lines = self._window(titles, cursor)
            else:
                titles, cursor, details = self._engine.items_snapshot()
                lines = self._window(titles, cursor)
                lines.extend((detail, False) for detail in details)
            self._set_lines(lines)
            self.Layout()
        finally:
            self.Thaw()

    def _window(self, titles: list[str], cursor: int) -> list[tuple[str, bool]]:
        if not titles:
            return []
        cursor = min(max(cursor, 0), len(titles) - 1)
        start = max(0, cursor - _WINDOW_RADIUS)
        stop = min(len(titles), cursor + _WINDOW_RADIUS + 1)
        return [
            (f"> {title}" if index == cursor else title, index == cursor)
            for index, title in enumerate(titles[start:stop], start=start)
        ]

    def _set_lines(self, lines: list[tuple[str, bool]]) -> None:
        while len(self._rows) < len(lines):
            row = wx.StaticText(self)
            row.SetCanFocus(False)
            self._sizer.Add(row, 0, wx.ALL | wx.EXPAND, 4)
            self._rows.append(row)
        for row, (text, current) in zip(self._rows, lines, strict=False):
            row.SetLabel(text)
            font = row.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD if current else wx.FONTWEIGHT_NORMAL)
            row.SetFont(font)
            row.Show()
        for row in self._rows[len(lines) :]:
            row.Hide()
