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
        # Transient panels (e.g. Import Deck) are shown on demand but never
        # pushed onto _stack so go_back skips them on the way home (D-02).
        self._transient_panels: set[str] = set()
        # Name of the panel currently visible (transient or stacked); the
        # source of truth for current_panel_name. _stack[-1] only reflects
        # the most recent non-transient panel.
        self._current_visible: str | None = None

    def register_panel(
        self,
        name: str,
        panel: wx.Panel,
        presenter: object,
        focus_target: wx.Window,
        *,
        transient: bool = False,
    ) -> None:
        """Register a panel for navigation. Initially hidden.

        A *transient* panel is shown on demand (e.g. Import Deck) but is not
        pushed onto the navigation history -- go_back skips it on the way home,
        so users never land on it via back-navigation. This matches the mental
        model of a one-shot operation rather than a peer destination (D-02).
        """
        self._panels[name] = panel
        self._presenters[name] = presenter
        self._focus_targets[name] = focus_target
        self._sizer.Add(panel, 1, wx.EXPAND)
        panel.Hide()
        if transient:
            self._transient_panels.add(name)

    def show_panel(self, name: str) -> None:
        """Show a panel by name.

        For non-transient panels: pushes onto the navigation stack so go_back
        can return here. For transient panels (e.g. Import Deck): does NOT
        push onto the stack so go_back skips this panel on the way home.
        """
        # Hide whatever is currently visible (transient or stacked)
        if self._current_visible is not None:
            self._panels[self._current_visible].Hide()

        # Show the new panel
        self._panels[name].Show()
        self._current_visible = name

        # Update navigation history. Transient panels are NEVER pushed.
        if name not in self._transient_panels:
            self._stack.append(name)

        self._sizer.Layout()

        # Activate key map. Add escape/back if there is anywhere to go back
        # to: a non-transient parent exists in _stack OR this panel is
        # transient (transient panels always need an escape route, even from
        # Home, so the user can dismiss them without committing to the op).
        presenter = self._presenters[name]
        get_map = getattr(presenter, "get_key_map", None)
        key_map = dict(get_map()) if get_map else {}
        if name in self._transient_panels or len(self._stack) > 1:
            key_map["escape"] = self.go_back
            key_map["back"] = self.go_back
        self._input_layer.activate_view(name, key_map)
        wx.CallAfter(self._focus_targets[name].SetFocus)

    def go_back(self) -> None:
        """Pop the current panel and return to the previous one (D-02).

        If the currently visible panel is transient: hide it and re-show the
        top of _stack (the most recent non-transient panel). Transients never
        appear in _stack, so the user is taken back to the panel they were on
        before opening the transient -- bypassing it on subsequent
        back-navigation.

        If the currently visible panel is non-transient: pop _stack and
        re-show the new top, exactly as before.

        No-op if there is nowhere to go back to (only Home, no transient).
        """
        if self._current_visible is None:
            return

        if self._current_visible in self._transient_panels:
            # Hide transient and return to the top of _stack (last
            # non-transient panel).
            self._panels[self._current_visible].Hide()
            if not self._stack:
                # No non-transient ancestry; nothing to restore. Defensive --
                # should not occur because OnInit always shows Home before
                # any transient.
                self._current_visible = None
                return
            target = self._stack[-1]
        else:
            # Non-transient: pop ourselves off _stack, restore the new top.
            if len(self._stack) <= 1:
                return  # Already at home (only one non-transient on stack)
            self._panels[self._current_visible].Hide()
            self._stack.pop()
            target = self._stack[-1]

        self._panels[target].Show()
        self._current_visible = target
        self._sizer.Layout()

        presenter = self._presenters[target]
        get_map = getattr(presenter, "get_key_map", None)
        key_map = dict(get_map()) if get_map else {}
        if target in self._transient_panels or len(self._stack) > 1:
            key_map["escape"] = self.go_back
            key_map["back"] = self.go_back
        self._input_layer.activate_view(target, key_map)
        wx.CallAfter(self._focus_targets[target].SetFocus)

    def replace_panel(
        self,
        name: str,
        panel: wx.Panel,
        presenter: object,
        focus_target: wx.Window,
        *,
        transient: bool = False,
    ) -> None:
        """Replace an existing panel, destroying the old one.

        If *name* is not yet registered, behaves like register_panel().
        Cleans up the old panel's sizer entry, removes stale stack entries,
        and updates the transient registry.
        """
        if name in self._panels:
            old_panel = self._panels[name]
            self._sizer.Detach(old_panel)
            old_panel.Destroy()
            self._stack = [n for n in self._stack if n != name]
            del self._panels[name]
            del self._presenters[name]
            del self._focus_targets[name]
            self._transient_panels.discard(name)
            if self._current_visible == name:
                self._current_visible = None
        self.register_panel(name, panel, presenter, focus_target, transient=transient)

    def get_presenter(self, name: str) -> object | None:
        """Return the presenter for a named panel, or None."""
        return self._presenters.get(name)

    @property
    def current_panel_name(self) -> str | None:
        """Return the name of the currently visible panel (transient or stacked)."""
        return self._current_visible

    def restore_focus(self) -> None:
        """Restore keyboard focus to the currently visible panel's focus target.

        Used by modal callsites (e.g. clipboard auto-import dialog) to ensure
        focus does not get lost in the destroyed dialog's parent chain after
        the user dismisses it. No-op if no panel is currently visible.

        Uses wx.CallAfter to schedule SetFocus after the current event loop
        iteration completes (Pitfall 4 -- see RESEARCH.md).
        """
        if self._current_visible is None:
            return
        target = self._focus_targets.get(self._current_visible)
        if target is None:
            return
        wx.CallAfter(target.SetFocus)


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
        self._find_id = wx.NewIdRef()
        accel_entries = [
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("Q"), wx.ID_EXIT),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("F"), self._find_id),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
        self.Bind(wx.EVT_MENU, self._on_quit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._on_find, id=self._find_id)
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

    def _on_find(self, event: wx.CommandEvent) -> None:
        """Handle Ctrl+F -- delegate to current panel's presenter if it supports search."""
        current = self._nav.current_panel_name
        if current is not None:
            presenter = self._nav.get_presenter(current)
            open_search = getattr(presenter, "open_search", None)
            if open_search is not None:
                open_search()

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
                    # Override the default focus target (deckstring_ctrl): after
                    # pre-filling, the next user action is to enter a name.
                    wx.CallAfter(import_panel.name_ctrl.SetFocus)
            # Don't clear clipboard -- _last_clipboard_deckstring prevents re-prompt
        else:
            # No path: explicitly restore focus to the active panel so screen
            # readers don't silently lose their place after dialog dismissal
            # (UAT Gap 3, D-06).
            self._nav.restore_focus()

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

        # --- Card Library (category menu) ---
        from stonereader.presenters.card_library import CardLibraryPresenter
        from stonereader.views.card_library import CardLibraryPanel

        library_presenter = CardLibraryPresenter(speech)
        library_panel = CardLibraryPanel(self._frame, library_presenter)
        nav.register_panel(
            "Card Library", library_panel, library_presenter, library_panel.list_box
        )

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
            "Import Deck",
            import_panel,
            import_presenter,
            import_panel.deckstring_ctrl,
            transient=True,
        )

        # --- Wire callbacks ---

        # Home screen selection -> show panel
        home_presenter.set_on_select(lambda name: nav.show_panel(name))

        # Card Library category selection -> create and show card browser
        def _on_category_select(category_name: str) -> None:
            from stonereader.presenters.card_browser import CardBrowserPresenter
            from stonereader.presenters.card_library import CATEGORY_TO_FILTER
            from stonereader.views.card_browser import CardBrowserPanel

            card_class_filter = CATEGORY_TO_FILTER.get(category_name)

            browser_presenter = CardBrowserPresenter(
                speech, card_db, category_name, card_class_filter
            )
            browser_panel = CardBrowserPanel(self._frame, browser_presenter)
            nav.replace_panel(
                "Card Browser", browser_panel, browser_presenter, browser_panel
            )
            nav.show_panel("Card Browser")
            browser_presenter.announce_entry()

        library_presenter.set_on_select(_on_category_select)

        # Deck Manager -> open deck contents
        def _on_open_deck(deck: object) -> None:
            from stonereader.presenters.deck_contents import DeckContentsPresenter
            from stonereader.views.deck_contents import DeckContentsPanel

            contents_presenter = DeckContentsPresenter(speech, deck)  # type: ignore[arg-type]
            contents_panel = DeckContentsPanel(self._frame, contents_presenter)
            nav.replace_panel(
                "Deck Contents", contents_panel, contents_presenter, contents_panel
            )
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
