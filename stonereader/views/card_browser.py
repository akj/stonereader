"""Card Library view — search TextCtrl and visual-only ListCtrl companion."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

from stonereader.views.base import make_labeled_text_ctrl

if TYPE_CHECKING:
    from stonereader.input_layer import InputLayer
    from stonereader.models.card import Card
    from stonereader.presenters.card_browser import CardBrowserPresenter


class _CardListCtrl(wx.ListCtrl):
    """Virtual ListCtrl displaying card results as a visual companion.

    Never focused — NVDA will not announce selection changes.
    """

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self.AppendColumn("Card", width=400)
        self._cards: list[Card] = []

    def set_cards(self, cards: list[Card]) -> None:
        self._cards = cards
        self.SetItemCount(len(cards))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:
        if item >= len(self._cards):
            return ""
        card = self._cards[item]
        return f"{card.name} — {card.cost} mana — {card.card_type}"


class CardBrowserPanel(wx.Panel):
    """Card Library tab panel."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: CardBrowserPresenter,
        input_layer: InputLayer,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Search TextCtrl — label placed immediately before for MSAA
        self._search_ctrl = make_labeled_text_ctrl(
            self, sizer, "Search cards:", input_layer, style=wx.TE_PROCESS_ENTER
        )
        self._search_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_search)

        # Visual companion ListCtrl — label for MSAA, never focused by user
        results_label = wx.StaticText(self, label="Card results:")
        sizer.Add(results_label, 0, wx.ALL, 4)
        self._list_ctrl = _CardListCtrl(self)
        sizer.Add(self._list_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

        # Wire view callback
        presenter.set_on_state_changed(self._on_state_changed)

        # Context menu
        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

        # Initial visual state
        self._list_ctrl.set_cards(list(presenter.get_zone_items("results")))

    @property
    def search_ctrl(self) -> wx.TextCtrl:
        return self._search_ctrl

    def _on_search(self, event: wx.CommandEvent) -> None:
        query = self._search_ctrl.GetValue()
        self._presenter.search(query)
        self.SetFocus()
        frame = self.GetTopLevelParent()
        count = len(self._presenter.get_zone_items("results"))
        if count:
            frame.SetStatusText(f"{count} results")
        else:
            frame.SetStatusText("No results")

    def _on_state_changed(self, results: list[Card], cursor: int) -> None:
        self._list_ctrl.set_cards(results)
        if results:
            self._list_ctrl.Select(cursor)

    def _on_context_menu(self, event: wx.ContextMenuEvent) -> None:
        menu = wx.Menu()
        copy_id = wx.NewIdRef()
        menu.Append(copy_id, "Copy card name")
        self.Bind(wx.EVT_MENU, self._on_copy_card_name, id=copy_id)
        self.PopupMenu(menu)
        menu.Destroy()

    def _on_copy_card_name(self, event: wx.CommandEvent) -> None:
        name = self._presenter.copy_current_card_name()
        if name is not None and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(name))
            wx.TheClipboard.Close()
