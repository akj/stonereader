"""Generic render-only panel for declarative Surfaces (ADR-0010)."""

from __future__ import annotations

import wx

from stonereader.ui.engines import HorizontalListEngine, VerticalMenuEngine


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
        self.SetSizer(self._sizer)
        engine.subscribe(self._render)
        self._render()

    def _render(self) -> None:
        self._sizer.Clear(delete_windows=True)
        if isinstance(self._engine, VerticalMenuEngine):
            titles, cursor = self._engine.options_snapshot()
            for index, title in enumerate(titles):
                self._add_line(title, current=index == cursor)
        else:
            titles, cursor, details = self._engine.items_snapshot()
            for index, title in enumerate(titles):
                self._add_line(title, current=index == cursor)
            for detail in details:
                self._add_line(detail)
        self.Layout()

    def _add_line(self, text: str, *, current: bool = False) -> None:
        row = wx.StaticText(self, label=text)
        row.SetCanFocus(False)
        if current:
            font = row.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            row.SetFont(font)
        self._sizer.Add(row, 0, wx.ALL | wx.EXPAND, 4)
