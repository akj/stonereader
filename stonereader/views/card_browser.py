"""Card Browser view -- card list with search dialog for a category."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from stonereader.models.card import Card
    from stonereader.presenters.card_browser import CardBrowserPresenter


class _CardListCtrl(wx.ListCtrl):
    """Virtual ListCtrl displaying card results.

    Visible to NVDA object navigation but kept out of Tab order via
    AcceptsFocus() so keyboard navigation stays on the presenter key map.
    """

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self.AppendColumn("Card", width=400)
        self._cards: list[Card] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_cards(self, cards: list[Card]) -> None:
        self._cards = cards
        self.SetItemCount(len(cards))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._cards):
            return ""
        card = self._cards[item]
        return f"{card.name} -- {card.cost} mana -- {card.card_type}"


class CardBrowserPanel(wx.Panel):
    """Card Browser panel showing filtered card list with search."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: CardBrowserPresenter,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # MSAA label for card list
        results_label = wx.StaticText(self, label="Cards:")
        sizer.Add(results_label, 0, wx.ALL, 4)
        self._list_ctrl = _CardListCtrl(self)
        sizer.Add(self._list_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

        # Wire presenter callbacks
        presenter.set_on_state_changed(self._on_state_changed)
        presenter.set_on_status_changed(self._on_status_changed)
        presenter.set_on_request_search(self._on_request_search)

        # Context menu
        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

        # Initial visual state
        self._list_ctrl.set_cards(list(presenter.get_zone_items("results")))

    def _on_state_changed(self, results: list[Card], cursor: int) -> None:
        self._list_ctrl.set_cards(results)
        if results:
            self._list_ctrl.Select(cursor)

    def _on_status_changed(self, text: str) -> None:
        frame = self.GetTopLevelParent()
        if isinstance(frame, wx.Frame):
            frame.SetStatusText(text)

    def _on_request_search(self) -> str | None:
        """Show a search dialog and return the query, or None if cancelled."""
        dialog = wx.TextEntryDialog(
            self,
            "Search cards by name or text:",
            "Find Cards",
        )
        result = dialog.ShowModal()
        query = dialog.GetValue()
        dialog.Destroy()
        if result == wx.ID_OK:
            return query
        return None

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
