"""Card Library category menu view -- ListBox of card categories."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from stonereader.presenters.card_library import CardLibraryPresenter


class CardLibraryPanel(wx.Panel):
    """Card Library category menu panel with ListBox."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: CardLibraryPresenter,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Heading for MSAA -- screen readers read this as context
        heading = wx.StaticText(self, label="Card Library")
        sizer.Add(heading, 0, wx.ALL, 8)

        # Category menu ListBox -- MSAA label via sibling order
        menu_label = wx.StaticText(self, label="Categories:")
        sizer.Add(menu_label, 0, wx.ALL, 4)

        from stonereader.presenters.card_library import CATEGORY_ITEMS

        self._list_box = wx.ListBox(
            self,
            choices=CATEGORY_ITEMS,
            style=wx.LB_SINGLE,
        )
        sizer.Add(self._list_box, 1, wx.EXPAND | wx.ALL, 8)

        self.SetSizer(sizer)

    @property
    def list_box(self) -> wx.ListBox:
        """Focus target for NavigationController."""
        return self._list_box
