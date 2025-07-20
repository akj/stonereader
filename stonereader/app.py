#!/usr/bin/env python3
"""
StoneReader - Accessible Hearthstone Deck and Card Browser
Main application entry point
"""

import wx
import wx.lib.newevent
from typing import Optional

from .models import CardDatabase
from .presenters import CardBrowserPresenter, DeckManagerPresenter
from .views import MainWindow


class StoneReaderApp(wx.App):
    """Main application class"""

    def __init__(self):
        super().__init__(False)
        self.card_db: Optional[CardDatabase] = None
        self.main_window: Optional[MainWindow] = None
        self.card_browser_presenter: Optional[CardBrowserPresenter] = None

    def OnInit(self):
        """Initialize the application"""
        try:
            # Show splash screen or loading dialog
            loading_dlg = wx.ProgressDialog(
                "Loading StoneReader",
                "Loading card database...",
                maximum=100,
                style=wx.PD_AUTO_HIDE | wx.PD_APP_MODAL,
            )

            # Load card database
            loading_dlg.Update(50, "Loading card database...")
            self.card_db = CardDatabase.load()

            # Create main window
            loading_dlg.Update(75, "Setting up interface...")
            self.main_window = MainWindow()

            # Initialize presenters
            self.card_browser_presenter = CardBrowserPresenter(self.card_db)
            deck_manager_presenter = DeckManagerPresenter(self.card_db)

            # Hook up presenters to views
            if self.main_window.card_browser:
                self.main_window.card_browser.set_presenter(self.card_browser_presenter)
            if self.main_window.deck_viewer:
                self.main_window.deck_viewer.set_presenter(deck_manager_presenter)

            # Set up event handlers
            self._setup_event_handlers()

            loading_dlg.Update(100, "Ready!")
            loading_dlg.Destroy()

            # Show main window
            self.main_window.Show()
            self.main_window.set_status(
                f"Ready - {self.card_db.total_collectible_cards()} cards loaded"
            )

            return True

        except Exception as e:
            import traceback

            error_msg = f"Failed to initialize StoneReader: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            print(error_msg)
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_ERROR)
            return False

    def _setup_event_handlers(self):
        """Set up cross-panel event handlers"""
        # When a card is selected in the browser, we could add it to a deck
        if self.main_window and self.main_window.card_browser:
            self.main_window.card_browser.on_card_selected = self._on_card_selected
            self.main_window.card_browser.on_card_activated = self._on_card_activated

        # When a deck is imported, we could switch to the deck view
        if self.main_window and self.main_window.deck_viewer:
            self.main_window.deck_viewer.on_deck_imported = self._on_deck_imported
            self.main_window.deck_viewer.on_deck_exported = self._on_deck_exported

    def _on_card_selected(self, card):
        """Handle card selection in browser"""
        # Could update status bar with card info
        if self.main_window:
            self.main_window.set_status(f"Selected: {card.name}")

    def _on_card_activated(self, card):
        """Handle card activation (double-click) in browser"""
        # Could show detailed card info in a dialog
        if self.card_browser_presenter:
            info = self.card_browser_presenter.format_card_details(card)
        else:
            info = f"{card.name}, {card.cost} mana {card.card_type.lower()}"
        wx.MessageBox(info, f"Card Details: {card.name}", wx.OK | wx.ICON_INFORMATION)

    def _on_deck_imported(self, deck):
        """Handle deck import"""
        # Could switch to deck view tab
        if self.main_window:
            self.main_window.notebook.SetSelection(1)  # Switch to deck view
            self.main_window.set_status(f"Imported deck: {deck.name}")

    def _on_deck_exported(self, deck, deckstring):
        """Handle deck export"""
        if self.main_window:
            self.main_window.set_status(f"Exported deck: {deck.name}")

    def GetCardDatabase(self):
        """Get the card database"""
        return self.card_db

    def GetMainWindow(self):
        """Get the main window"""
        return self.main_window


def main():
    """Main entry point"""
    app = StoneReaderApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
