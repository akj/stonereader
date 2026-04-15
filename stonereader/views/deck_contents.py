"""Deck contents view -- card list for a selected deck."""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import wx

if TYPE_CHECKING:
    from stonereader.models.card import Card
    from stonereader.presenters.deck_contents import DeckContentsPresenter


class _DeckCardListCtrl(wx.ListCtrl):
    """Virtual ListCtrl displaying deck card entries."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self.AppendColumn("Card", width=400)
        self._cards: list[Tuple[Card, int]] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_cards(self, cards: list[Tuple[Card, int]]) -> None:
        self._cards = cards
        self.SetItemCount(len(cards))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._cards):
            return ""
        card, count = self._cards[item]
        return f"{card.name} x{count} -- {card.cost} mana -- {card.card_type}"


class DeckContentsPanel(wx.Panel):
    """Deck contents panel showing card list for a single deck."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: DeckContentsPresenter,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # MSAA label for card list
        cards_label = wx.StaticText(self, label="Cards:")
        sizer.Add(cards_label, 0, wx.ALL, 4)

        self._list_ctrl = _DeckCardListCtrl(self)
        sizer.Add(self._list_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

        # Wire presenter callback
        presenter.set_on_state_changed(self._on_state_changed)

        # Initial visual state
        self._list_ctrl.set_cards(list(presenter.get_zone_items("cards")))

    def _on_state_changed(
        self, cards: list[Tuple[Card, int]], cursor: int
    ) -> None:
        self._list_ctrl.set_cards(cards)
        if cards:
            self._list_ctrl.Select(cursor)
