"""Live Game panel view — passive 4-zone display for live Hearthstone state.

Layout:
    [ Title StaticText ]                       (matchup + detected deck)
    [ Mana StaticText  ]                       (panel-only mana surfacing)

    [ "Remaining Deck:" label ]
    [ _RemainingDeckListCtrl  ]                (virtual ListCtrl)

    [ "Opponent Hand:" label ]
    [ _OpponentHandListCtrl  ]                 (virtual ListCtrl)

    [ "Opponent Played:" label ]
    [ _OpponentPlayedListCtrl ]                (virtual ListCtrl)

    [ "Cards Drawn:" label ]                   (LIVE-03 per 03-REVIEWS.md HIGH #1)
    [ _CardsDrawnListCtrl    ]                 (virtual ListCtrl)

Per CLAUDE.md MVP rule: views do NOT call SpeechService. All speech goes
through the presenter.

Per 03-REVIEWS.md HIGH #3: the view uses ONLY public presenter accessors
(current_title, cursor_for_zone, current_mana_summary, get_zone_items).
No private-field access (_zone_cursors, _format_title, _current_state).

Per 03-REVIEWS.md MEDIUM 03-06 #1: row-text formatting is centralized in
`stonereader/views/_live_game_format.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import wx

from stonereader.views._live_game_format import (
    format_cards_drawn_row,
    format_opponent_hand_row,
    format_opponent_played_row,
    format_remaining_deck_row,
)

if TYPE_CHECKING:
    from stonereader.models.card import Card
    from stonereader.models.game_state import PlayedCard
    from stonereader.presenters.live_game import (
        LiveGamePresenter,
        OpponentHandRow,
    )


_LIST_STYLE = (
    wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER
)


class _RemainingDeckListCtrl(wx.ListCtrl):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=_LIST_STYLE)
        self.AppendColumn("Card", width=400)
        self._rows: List[Tuple["Card", int]] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_rows(self, rows: List[Tuple["Card", int]]) -> None:
        self._rows = rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._rows):
            return ""
        return format_remaining_deck_row(self._rows[item])


class _OpponentHandListCtrl(wx.ListCtrl):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=_LIST_STYLE)
        self.AppendColumn("Card", width=400)
        self._rows: List["OpponentHandRow"] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_rows(self, rows: List["OpponentHandRow"]) -> None:
        self._rows = rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._rows):
            return ""
        return format_opponent_hand_row(self._rows[item])


class _OpponentPlayedListCtrl(wx.ListCtrl):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=_LIST_STYLE)
        self.AppendColumn("Card", width=400)
        self._rows: List["PlayedCard"] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_rows(self, rows: List["PlayedCard"]) -> None:
        self._rows = rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._rows):
            return ""
        return format_opponent_played_row(self._rows[item])


class _CardsDrawnListCtrl(wx.ListCtrl):
    """LIVE-03 zone (per 03-REVIEWS.md HIGH #1)."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=_LIST_STYLE)
        self.AppendColumn("Card", width=400)
        self._rows: List["PlayedCard"] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_rows(self, rows: List["PlayedCard"]) -> None:
        self._rows = rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._rows):
            return ""
        return format_cards_drawn_row(self._rows[item])


class LiveGamePanel(wx.Panel):
    """Passive 4-zone live game panel.

    The panel is fully passive: never calls SpeechService; presenter owns
    all speech. Re-rendering is triggered by `set_on_state_changed` and
    `set_on_title_changed` callbacks from the presenter.

    Uses ONLY public presenter accessors (per 03-REVIEWS.md HIGH #3):
        presenter.current_title()
        presenter.cursor_for_zone(name)
        presenter.current_mana_summary()
        presenter.get_zone_items(name)
    """

    def __init__(
        self,
        parent: wx.Window,
        presenter: "LiveGamePresenter",
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Title bar.
        self._title = wx.StaticText(self, label="No game in progress")
        sizer.Add(self._title, 0, wx.ALL | wx.EXPAND, 4)

        # Mana summary (panel-only per Open Q2 / LIVE-07).
        self._mana = wx.StaticText(self, label="")
        sizer.Add(self._mana, 0, wx.ALL | wx.EXPAND, 4)

        # Remaining Deck zone.
        self._remaining_label = wx.StaticText(self, label="Remaining Deck:")
        sizer.Add(self._remaining_label, 0, wx.ALL, 4)
        self._remaining_ctrl = _RemainingDeckListCtrl(self)
        sizer.Add(self._remaining_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        # Opponent Hand zone.
        self._opp_hand_label = wx.StaticText(self, label="Opponent Hand:")
        sizer.Add(self._opp_hand_label, 0, wx.ALL, 4)
        self._opp_hand_ctrl = _OpponentHandListCtrl(self)
        sizer.Add(self._opp_hand_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        # Opponent Played zone.
        self._opp_played_label = wx.StaticText(self, label="Opponent Played:")
        sizer.Add(self._opp_played_label, 0, wx.ALL, 4)
        self._opp_played_ctrl = _OpponentPlayedListCtrl(self)
        sizer.Add(self._opp_played_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        # Cards Drawn zone (LIVE-03 per 03-REVIEWS.md HIGH #1).
        self._cards_drawn_label = wx.StaticText(self, label="Cards Drawn:")
        sizer.Add(self._cards_drawn_label, 0, wx.ALL, 4)
        self._cards_drawn_ctrl = _CardsDrawnListCtrl(self)
        sizer.Add(self._cards_drawn_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

        # Wire presenter callbacks.
        presenter.set_on_state_changed(self._on_state_changed)
        presenter.set_on_title_changed(self._on_title_changed)

        # Initial render — uses PUBLIC accessor `current_title()`.
        self._on_state_changed()
        self._on_title_changed(presenter.current_title())

    def _on_state_changed(self) -> None:
        """Re-fetch zone items + cursor positions; re-render each ListCtrl.

        Uses ONLY public accessors (per 03-REVIEWS.md HIGH #3).
        """
        remaining = list(self._presenter.get_zone_items("remaining_deck"))
        opp_hand = list(self._presenter.get_zone_items("opponent_hand"))
        opp_played = list(self._presenter.get_zone_items("opponent_played"))
        cards_drawn = list(self._presenter.get_zone_items("cards_drawn"))
        self._remaining_ctrl.set_rows(remaining)
        self._opp_hand_ctrl.set_rows(opp_hand)
        self._opp_played_ctrl.set_rows(opp_played)
        self._cards_drawn_ctrl.set_rows(cards_drawn)
        # Cursor preservation (Pitfall 3) via PUBLIC accessor.
        if remaining:
            self._remaining_ctrl.Select(
                max(
                    0,
                    min(
                        self._presenter.cursor_for_zone("remaining_deck"),
                        len(remaining) - 1,
                    ),
                )
            )
        if opp_hand:
            self._opp_hand_ctrl.Select(
                max(
                    0,
                    min(
                        self._presenter.cursor_for_zone("opponent_hand"),
                        len(opp_hand) - 1,
                    ),
                )
            )
        if opp_played:
            self._opp_played_ctrl.Select(
                max(
                    0,
                    min(
                        self._presenter.cursor_for_zone("opponent_played"),
                        len(opp_played) - 1,
                    ),
                )
            )
        if cards_drawn:
            self._cards_drawn_ctrl.Select(
                max(
                    0,
                    min(
                        self._presenter.cursor_for_zone("cards_drawn"),
                        len(cards_drawn) - 1,
                    ),
                )
            )
        # Mana surfacing (LIVE-07).
        self._mana.SetLabel(self._presenter.current_mana_summary())

    def _on_title_changed(self, text: str) -> None:
        self._title.SetLabel(text)
