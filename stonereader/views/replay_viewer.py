"""Replay viewer panel — passive turn-first display for a replayed game.

Slice #15 (the capstone). Mirrors views/live_game.py: a fully passive
wx.Panel that NEVER calls SpeechService and holds ZERO logic. All state
interpretation, navigation, and speech live in ReplayViewerPresenter.

Layout:
    [ Turn StaticText ]                        (current turn header)

    [ "Events:" label ]
    [ _EventsListCtrl ]                         (current turn's GameEvents)

    [ "Your Board:" label ]
    [ _ZoneListCtrl (your board) ]

    [ "Opponent Board:" label ]
    [ _ZoneListCtrl (opponent board) ]

The panel re-renders via the presenter's set_on_state_changed callback. It
reads ONLY public presenter accessors (get_zone_items, current_turn_number).
Per CLAUDE.md: views are thin; all keymap dispatch is wired by the app/input
layer against presenter.get_key_map().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

import wx

if TYPE_CHECKING:
    from stonereader.presenters.replay_viewer import ReplayViewerPresenter


_LIST_STYLE = wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER


class _ZoneListCtrl(wx.ListCtrl):
    """A virtual single-column list for one replay zone."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=_LIST_STYLE)
        self.AppendColumn("Item", width=400)
        self._rows: List[str] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_rows(self, rows: List[str]) -> None:
        self._rows = rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._rows):
            return ""
        return self._rows[item]


def _row_text(item: Any) -> str:
    """Best-effort display text for a zone item. No presenter logic here."""
    if item is None:
        return "Hidden card"
    name = getattr(item, "name", None)
    if name:
        return str(name)
    return str(item)


class ReplayViewerPanel(wx.Panel):
    """Passive replay viewer panel. Owns no logic; presenter owns all speech."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: "ReplayViewerPresenter",
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        self._turn = wx.StaticText(self, label="Turn 1")
        sizer.Add(self._turn, 0, wx.ALL | wx.EXPAND, 4)

        self._events_label = wx.StaticText(self, label="Events:")
        sizer.Add(self._events_label, 0, wx.ALL, 4)
        self._events_ctrl = _ZoneListCtrl(self)
        sizer.Add(self._events_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self._your_board_label = wx.StaticText(self, label="Your Board:")
        sizer.Add(self._your_board_label, 0, wx.ALL, 4)
        self._your_board_ctrl = _ZoneListCtrl(self)
        sizer.Add(self._your_board_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self._opp_board_label = wx.StaticText(self, label="Opponent Board:")
        sizer.Add(self._opp_board_label, 0, wx.ALL, 4)
        self._opp_board_ctrl = _ZoneListCtrl(self)
        sizer.Add(self._opp_board_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

        presenter.set_on_state_changed(self._on_state_changed)
        self._on_state_changed()

    def _on_state_changed(self) -> None:
        self._turn.SetLabel(f"Turn {self._presenter.current_turn_number()}")
        self._events_ctrl.set_rows(
            [_row_text(i) for i in self._presenter.get_zone_items("events")]
        )
        self._your_board_ctrl.set_rows(
            [_row_text(i) for i in self._presenter.get_zone_items("your_board")]
        )
        self._opp_board_ctrl.set_rows(
            [_row_text(i) for i in self._presenter.get_zone_items("opponent_board")]
        )
