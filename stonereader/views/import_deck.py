"""Import Deck view -- deckstring and name fields with import button."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import wx

from stonereader.views.base import make_labeled_text_ctrl

if TYPE_CHECKING:
    from stonereader.input_layer import InputLayer
    from stonereader.presenters.import_deck import ImportDeckPresenter


class ImportDeckPanel(wx.Panel):
    """Import Deck panel with deckstring/name fields and buttons."""

    def __init__(
        self,
        parent: wx.Window,
        presenter: ImportDeckPresenter,
        input_layer: InputLayer,
        on_back: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, style=wx.WANTS_CHARS)
        self._presenter = presenter
        self._on_back = on_back

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Deckstring field -- MSAA label via make_labeled_text_ctrl
        self._deckstring_ctrl = make_labeled_text_ctrl(
            self,
            sizer,
            "Deck code:",
            input_layer,
            style=wx.TE_PROCESS_ENTER,
        )
        self._deckstring_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_submit)

        # Name field -- MSAA label via make_labeled_text_ctrl
        self._name_ctrl = make_labeled_text_ctrl(
            self,
            sizer,
            "Deck name:",
            input_layer,
            style=wx.TE_PROCESS_ENTER,
        )
        self._name_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_submit)

        # Import Deck button
        self._import_btn = wx.Button(self, label="Import Deck")
        sizer.Add(self._import_btn, 0, wx.ALL, 8)
        self._import_btn.Bind(wx.EVT_BUTTON, self._on_submit)

        # Back to Home button
        self._back_btn = wx.Button(self, label="Back to Home")
        sizer.Add(self._back_btn, 0, wx.ALL, 8)
        self._back_btn.Bind(wx.EVT_BUTTON, self._on_back_click)

        self.SetSizer(sizer)

        # Wire presenter error callback
        presenter.set_on_show_error(self._on_show_error)

    @property
    def deckstring_ctrl(self) -> wx.TextCtrl:
        """Focus target and deckstring input."""
        return self._deckstring_ctrl

    @property
    def name_ctrl(self) -> wx.TextCtrl:
        """Name input field."""
        return self._name_ctrl

    def pre_fill_deckstring(self, deckstring: str) -> None:
        """Pre-fill deckstring field (for clipboard auto-detect D-06)."""
        self._deckstring_ctrl.SetValue(deckstring)

    def _on_submit(self, event: wx.CommandEvent) -> None:
        deckstring = self._deckstring_ctrl.GetValue()
        name = self._name_ctrl.GetValue()
        success = self._presenter.validate_and_import(deckstring, name)
        if success:
            # Clear fields for next import
            self._deckstring_ctrl.SetValue("")
            self._name_ctrl.SetValue("")

    def _on_back_click(self, event: wx.CommandEvent) -> None:
        if self._on_back is not None:
            self._on_back()

    def _on_show_error(self, message: str, title: str) -> None:
        """Show error via wx.MessageBox (D-07)."""
        wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR)
