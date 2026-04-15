"""Main application window and wx.App setup.

Provides NavigationController (panel-swap navigation replacing wx.Notebook),
MainWindow (top-level frame with clipboard auto-detection), and
StoneReaderApp (entry point that wires all presenters and panels).
"""

from __future__ import annotations

import sqlite3

import wx

from stonereader.db import get_connection, init_db
from stonereader.input_layer import InputLayer
from stonereader.speech_service import SpeechService


class NavigationController:
    """Manages panel visibility and navigation stack.

    Replaces wx.Notebook with a panel-swap pattern per D-01. Only one
    panel is visible at a time. Panels are registered by name and shown
    via show_panel(). go_back() pops the stack and returns to the
    previous panel.
    """

    def __init__(
        self,
        frame: wx.Frame,
        sizer: wx.BoxSizer,
        input_layer: InputLayer,
    ) -> None:
        self._frame = frame
        self._sizer = sizer
        self._input_layer = input_layer
        self._panels: dict[str, wx.Panel] = {}
        self._presenters: dict[str, object] = {}
        self._focus_targets: dict[str, wx.Window] = {}
        self._stack: list[str] = []

    def register_panel(
        self,
        name: str,
        panel: wx.Panel,
        presenter: object,
        focus_target: wx.Window,
    ) -> None:
        """Register a panel for navigation. Initially hidden."""
        self._panels[name] = panel
        self._presenters[name] = presenter
        self._focus_targets[name] = focus_target
        self._sizer.Add(panel, 1, wx.EXPAND)
        panel.Hide()

    def show_panel(self, name: str) -> None:
        """Show a panel by name, pushing it onto the navigation stack."""
        if self._stack:
            current = self._stack[-1]
            self._panels[current].Hide()
        self._stack.append(name)
        self._panels[name].Show()
        self._sizer.Layout()
        # Activate key map with escape/back for navigation
        presenter = self._presenters[name]
        get_map = getattr(presenter, "get_key_map", None)
        key_map = dict(get_map()) if get_map else {}
        # Add escape/back to all panels except home (D-02)
        if len(self._stack) > 1:
            key_map["escape"] = self.go_back
            key_map["back"] = self.go_back
        self._input_layer.activate_view(name, key_map)
        wx.CallAfter(self._focus_targets[name].SetFocus)

    def go_back(self) -> None:
        """Pop the current panel and return to the previous one (D-02)."""
        if len(self._stack) <= 1:
            return  # Already at home, nowhere to go
        self._panels[self._stack.pop()].Hide()
        current = self._stack[-1]
        self._panels[current].Show()
        self._sizer.Layout()
        presenter = self._presenters[current]
        get_map = getattr(presenter, "get_key_map", None)
        key_map = dict(get_map()) if get_map else {}
        if len(self._stack) > 1:
            key_map["escape"] = self.go_back
            key_map["back"] = self.go_back
        self._input_layer.activate_view(current, key_map)
        wx.CallAfter(self._focus_targets[current].SetFocus)

    @property
    def current_panel_name(self) -> str | None:
        """Return the name of the currently visible panel."""
        return self._stack[-1] if self._stack else None


class MainWindow(wx.Frame):
    """Top-level window with panel-swap navigation."""

    def __init__(self) -> None:
        super().__init__(None, title="StoneReader", size=wx.Size(800, 600))

        self._speech = SpeechService()
        self._input_layer = InputLayer(self)

        # Database
        self._db_conn = get_connection()
        init_db(self._db_conn)

        # Status bar -- readable via NVDA+End / JAWS Insert+B
        self.CreateStatusBar()
        self.SetStatusText("StoneReader ready")

        # Main sizer -- NavigationController manages children
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)

        # Navigation controller replaces wx.Notebook (D-01)
        self._nav = NavigationController(self, self._sizer, self._input_layer)

        # Clipboard auto-detection state (D-06, Pitfall 5)
        self._last_clipboard_deckstring: str | None = None
        self._suppress_clipboard_check = True  # Suppress during initial launch

        # Accelerator table for standard shortcuts
        accel_entries = [
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("Q"), wx.ID_EXIT),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self._on_quit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)

    @property
    def speech(self) -> SpeechService:
        return self._speech

    @property
    def input_layer(self) -> InputLayer:
        return self._input_layer

    @property
    def db_conn(self) -> sqlite3.Connection:
        return self._db_conn

    @property
    def nav(self) -> NavigationController:
        return self._nav

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        """Check clipboard for deckstring when app gains focus (D-06)."""
        event.Skip()
        if not event.GetActive():
            return
        if self._suppress_clipboard_check:
            self._suppress_clipboard_check = False
            return
        self._check_clipboard_for_deckstring()

    def _check_clipboard_for_deckstring(self) -> None:
        """Check clipboard for valid deckstring and offer import (D-06)."""
        if not wx.TheClipboard.Open():
            return
        try:
            data = wx.TextDataObject()
            if not wx.TheClipboard.GetData(data):
                return
            text = data.GetText().strip()
            if not text:
                return
            # Skip if same as last checked (Pitfall 5)
            if text == self._last_clipboard_deckstring:
                return
            self._last_clipboard_deckstring = text
            # Try parsing as deckstring
            try:
                from hearthstone.deckstrings import parse_deckstring

                parse_deckstring(text)
            except (ValueError, TypeError):
                return
        finally:
            wx.TheClipboard.Close()

        # Valid deckstring found -- offer import
        dialog = wx.MessageDialog(
            self,
            "A deck code was found on your clipboard. Import it?",
            "Deck Found on Clipboard",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        result = dialog.ShowModal()
        dialog.Destroy()
        if result == wx.ID_YES:
            self._nav.show_panel("Import Deck")
            # Pre-fill deckstring and focus name field
            import_panel = self._nav._panels.get("Import Deck")
            if import_panel is not None:
                from stonereader.views.import_deck import ImportDeckPanel

                if isinstance(import_panel, ImportDeckPanel):
                    import_panel.pre_fill_deckstring(text)
                    wx.CallAfter(import_panel.name_ctrl.SetFocus)
            # Clear clipboard after successful detection
            if wx.TheClipboard.Open():
                wx.TheClipboard.Clear()
                wx.TheClipboard.Close()

    def _on_quit(self, event: wx.CommandEvent) -> None:
        self.Close()

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._db_conn.close()
        self.Destroy()


class StoneReaderApp(wx.App):
    """Application entry point."""

    def OnInit(self) -> bool:  # noqa: N802 -- wx override
        self._frame = MainWindow()
        nav = self._frame.nav
        speech = self._frame.speech
        input_layer = self._frame.input_layer
        db_conn = self._frame.db_conn

        # Load card database
        from stonereader.models.card import CardDatabase

        card_db = CardDatabase.load()

        # --- Home Screen ---
        from stonereader.presenters.home import HomePresenter
        from stonereader.views.home import HomePanel

        home_presenter = HomePresenter(speech)
        home_panel = HomePanel(self._frame, home_presenter)
        nav.register_panel("Home", home_panel, home_presenter, home_panel.list_box)

        # --- Card Library ---
        from stonereader.presenters.card_browser import CardBrowserPresenter
        from stonereader.views.card_browser import CardBrowserPanel

        card_presenter = CardBrowserPresenter(speech, card_db)
        card_panel = CardBrowserPanel(self._frame, card_presenter, input_layer)
        nav.register_panel("Card Library", card_panel, card_presenter, card_panel)

        # --- Deck Manager ---
        from stonereader.presenters.deck_manager import DeckManagerPresenter
        from stonereader.views.deck_manager import DeckManagerPanel

        deck_presenter = DeckManagerPresenter(speech, db_conn, card_db)
        deck_panel = DeckManagerPanel(self._frame, deck_presenter)
        nav.register_panel("Deck Manager", deck_panel, deck_presenter, deck_panel)

        # --- Import Deck ---
        from stonereader.presenters.import_deck import ImportDeckPresenter
        from stonereader.views.import_deck import ImportDeckPanel

        import_presenter = ImportDeckPresenter(speech, db_conn, card_db)
        import_panel = ImportDeckPanel(
            self._frame,
            import_presenter,
            input_layer,
            on_back=nav.go_back,
        )
        nav.register_panel(
            "Import Deck", import_panel, import_presenter, import_panel.deckstring_ctrl
        )

        # --- Wire callbacks ---

        # Home screen selection -> show panel
        home_presenter.set_on_select(lambda name: nav.show_panel(name))

        # Deck Manager -> open deck contents
        def _on_open_deck(deck: object) -> None:
            from stonereader.presenters.deck_contents import DeckContentsPresenter
            from stonereader.views.deck_contents import DeckContentsPanel

            # Create fresh presenter and panel for this specific deck
            contents_presenter = DeckContentsPresenter(speech, deck)  # type: ignore[arg-type]
            contents_panel = DeckContentsPanel(self._frame, contents_presenter)

            # Re-register the deck contents panel (destroy old if exists)
            if "Deck Contents" in nav._panels:
                old_panel = nav._panels["Deck Contents"]
                nav._sizer.Detach(old_panel)
                old_panel.Destroy()
                # Remove stale stack entries to prevent ghost navigation
                nav._stack = [n for n in nav._stack if n != "Deck Contents"]
            nav.register_panel(
                "Deck Contents", contents_panel, contents_presenter, contents_panel
            )

            # Show it and announce deck header
            nav.show_panel("Deck Contents")
            contents_presenter.announce_deck_header()

        deck_presenter.set_on_open_deck(_on_open_deck)

        # Import success -> navigate to Deck Manager and reload
        def _on_import_success() -> None:
            deck_presenter.load_decks()
            nav.show_panel("Deck Manager")
            deck_presenter.announce_entry()

        import_presenter.set_on_import_success(_on_import_success)

        # Show home screen on launch
        nav.show_panel("Home")

        self._frame.Show()
        return True
