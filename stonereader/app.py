"""Main application window and wx.App setup."""

from __future__ import annotations

import wx

from stonereader.db import get_connection, init_db
from stonereader.input_layer import InputLayer
from stonereader.speech_service import SpeechService


class MainWindow(wx.Frame):
    """Top-level window with Notebook tabs, status bar, and accelerator table."""

    def __init__(self) -> None:
        super().__init__(None, title="StoneReader", size=wx.Size(800, 600))

        self._speech = SpeechService()
        self._input_layer = InputLayer(self)

        # Database
        self._db_conn = get_connection()
        init_db(self._db_conn)

        # Status bar — readable via NVDA+End / JAWS Insert+B
        self.CreateStatusBar()
        self.SetStatusText("StoneReader ready")

        # Notebook (tabs added by feature slices)
        self._notebook = wx.Notebook(self)
        self._notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)

        # Track presenters and focus targets per tab
        self._tab_presenters: list = []
        self._tab_focus_targets: list[wx.Window] = []
        self._tab_names: list[str] = []

        # Main sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

        # Accelerator table for standard shortcuts
        accel_entries = [
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("Q"), wx.ID_EXIT),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self._on_quit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    @property
    def speech(self) -> SpeechService:
        return self._speech

    @property
    def input_layer(self) -> InputLayer:
        return self._input_layer

    @property
    def notebook(self) -> wx.Notebook:
        return self._notebook

    def add_tab(
        self,
        panel: wx.Panel,
        name: str,
        presenter: object,
        focus_target: wx.Window,
    ) -> None:
        """Register a feature tab."""
        self._notebook.AddPage(panel, name)
        self._tab_presenters.append(presenter)
        self._tab_focus_targets.append(focus_target)
        self._tab_names.append(name)

    def _on_page_changed(self, event: wx.BookCtrlEvent) -> None:
        page = event.GetSelection()
        if 0 <= page < len(self._tab_presenters):
            presenter = self._tab_presenters[page]
            key_map = presenter.get_key_map() if hasattr(presenter, "get_key_map") else {}
            self._input_layer.activate_view(self._tab_names[page], key_map)
            target = self._tab_focus_targets[page]
            wx.CallAfter(target.SetFocus)
        event.Skip()

    def _on_quit(self, event: wx.CommandEvent) -> None:
        self.Close()

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._db_conn.close()
        self.Destroy()


class StoneReaderApp(wx.App):
    """Application entry point."""

    def OnInit(self) -> bool:
        self._frame = MainWindow()
        self._frame.Show()
        return True
