"""Replays browser panel view — newest-first replay history (Slice #14).

Passive single-zone panel mirroring views/live_game.py: a virtual
``wx.ListCtrl`` renders one row per stored replay via a module-level format
helper, wired to the presenter's callbacks.

Per CLAUDE.md MVP rule: the view never calls SpeechService and holds NO logic.
All speech + state live in :class:`ReplaysPresenter`; the view re-renders when
the presenter fires its ``set_on_changed`` callback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import wx

from stonereader.presenters.replays import format_replay_row

if TYPE_CHECKING:
    from stonereader.presenters.replays import ReplaysPresenter
    from stonereader.services._replay_store import ReplayMeta


_LIST_STYLE = wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER


class _ReplaysListCtrl(wx.ListCtrl):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=_LIST_STYLE)
        self.AppendColumn("Replay", width=600)
        self._rows: List["ReplayMeta"] = []

    def set_rows(self, rows: List["ReplayMeta"]) -> None:
        self._rows = rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._rows):
            return ""
        return format_replay_row(self._rows[item])


class ReplaysPanel(wx.Panel):
    """Passive replay-history panel.

    Re-renders the virtual ListCtrl whenever the presenter fires its
    ``set_on_changed`` callback (after refresh/delete).
    """

    def __init__(
        self,
        parent: wx.Window,
        presenter: "ReplaysPresenter",
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)
        self._label = wx.StaticText(self, label="Replays:")
        sizer.Add(self._label, 0, wx.ALL, 4)
        self._list = _ReplaysListCtrl(self)
        sizer.Add(self._list, 1, wx.EXPAND | wx.ALL, 4)
        self.SetSizer(sizer)

        presenter.set_on_changed(self._on_changed)
        self._on_changed()

    def _on_changed(self) -> None:
        rows = list(self._presenter.get_zone_items("replays"))
        self._list.set_rows(rows)
        if rows:
            cursor = self._presenter.cursor_for_zone("replays")
            self._list.Select(max(0, min(cursor, len(rows) - 1)))
