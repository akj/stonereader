"""Deck Manager view -- deck list with delete and export."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from stonereader.models.deck import DeckSummary
    from stonereader.presenters.deck_manager import DeckManagerPresenter


class _DeckListCtrl(wx.ListCtrl):
    """Virtual ListCtrl displaying saved deck summaries."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
        )
        self.AppendColumn("Deck", width=400)
        self._decks: list[DeckSummary] = []

    def AcceptsFocus(self) -> bool:  # noqa: N802 -- wx override
        return False

    def set_decks(self, decks: list[DeckSummary]) -> None:
        self._decks = decks
        self.SetItemCount(len(decks))
        self.Refresh()

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 -- wx override
        if item >= len(self._decks):
            return ""
        deck = self._decks[item]
        return f"{deck.name} -- {deck.hero_class} -- {deck.format}"


class DeckManagerPanel(wx.Panel):
    """Deck Manager panel showing list of saved decks."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: DeckManagerPresenter,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # MSAA label for deck list
        decks_label = wx.StaticText(self, label="Saved decks:")
        sizer.Add(decks_label, 0, wx.ALL, 4)

        self._list_ctrl = _DeckListCtrl(self)
        sizer.Add(self._list_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

        # Wire presenter callbacks
        presenter.set_on_state_changed(self._on_state_changed)
        presenter.set_on_request_delete_confirm(self._on_delete_confirm)
        presenter.set_on_export(self._on_export)

        # Initial visual state
        self._list_ctrl.set_decks(list(presenter.get_zone_items("decks")))

    def _on_state_changed(
        self, decks: list[DeckSummary], cursor: int
    ) -> None:
        self._list_ctrl.set_decks(decks)
        if decks:
            self._list_ctrl.Select(cursor)

    def _on_delete_confirm(self, deck_name: str) -> bool:
        """Show delete confirmation dialog (D-13)."""
        dialog = wx.MessageDialog(
            self,
            f"Delete '{deck_name}'? This cannot be undone.",
            "Delete Deck",
            wx.YES_NO | wx.ICON_WARNING,
        )
        result = dialog.ShowModal()
        dialog.Destroy()
        return result == wx.ID_YES

    def _on_export(self, deckstring: str) -> None:
        """Copy deckstring to clipboard (D-15)."""
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(deckstring))
            wx.TheClipboard.Close()
