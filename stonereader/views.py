import wx
from typing import Optional, Dict, Any, Callable


class MainWindow(wx.Frame):
    """Main application window with menu and navigation"""

    def __init__(self):
        super().__init__(
            None,
            title="StoneReader - Hearthstone Deck and Card Browser",
            size=wx.Size(1200, 800),
        )

        # Initialize panels
        self.card_browser = None
        self.deck_viewer = None
        self.replay_viewer = None

        self._setup_ui()
        self._setup_menus()
        self._setup_statusbar()

    def _setup_ui(self):
        """Set up the main UI layout"""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook for tabs
        self.notebook = wx.Notebook(panel)

        # Add placeholder panels - will be properly initialized later
        self.card_browser = CardBrowserPanel(self.notebook)
        self.deck_viewer = DeckViewPanel(self.notebook)
        self.replay_viewer = ReplayViewerPanel(self.notebook)

        self.notebook.AddPage(self.card_browser, "Card Browser")
        self.notebook.AddPage(self.deck_viewer, "Deck View")
        self.notebook.AddPage(self.replay_viewer, "Replay Viewer")

        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)

    def _setup_menus(self):
        """Set up application menus"""
        menubar = wx.MenuBar()

        # File menu
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Open Deck\tCtrl+O", "Open a deck file")
        file_menu.Append(wx.ID_SAVE, "&Save Deck\tCtrl+S", "Save current deck")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit\tCtrl+Q", "Exit the application")

        menubar.Append(file_menu, "&File")

        # View menu
        view_menu = wx.Menu()
        view_menu.Append(wx.ID_ANY, "&Card Browser\tCtrl+1", "Switch to card browser")
        view_menu.Append(wx.ID_ANY, "&Deck View\tCtrl+2", "Switch to deck view")
        view_menu.Append(wx.ID_ANY, "&Replay Viewer\tCtrl+3", "Switch to replay viewer")

        menubar.Append(view_menu, "&View")

        # Help menu
        help_menu = wx.Menu()
        help_menu.Append(wx.ID_ABOUT, "&About", "About StoneReader")

        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.on_about, id=wx.ID_ABOUT)

    def _setup_statusbar(self):
        """Set up status bar"""
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText("Ready")

    def on_exit(self, event):
        """Handle application exit"""
        self.Close()

    def on_about(self, event):
        """Show about dialog"""
        try:
            import wx.adv

            info = wx.adv.AboutDialogInfo()
            info.SetName("StoneReader")
            info.SetVersion("1.0")
            info.SetDescription("Accessible Hearthstone deck and card browser")
            info.SetWebSite("https://github.com/your-repo/stonereader")
            info.AddDeveloper("Your Name")
            wx.adv.AboutBox(info)
        except ImportError:
            wx.MessageBox(
                "StoneReader v1.0\nAccessible Hearthstone deck and card browser",
                "About",
                wx.OK | wx.ICON_INFORMATION,
            )

    def set_status(self, text: str):
        """Set status bar text"""
        self.statusbar.SetStatusText(text)


class CardBrowserPanel(wx.Panel):
    """Accessible card browsing interface"""

    def __init__(self, parent):
        super().__init__(parent)

        # Presenter will be set later
        self.presenter = None

        # Event callbacks
        self.on_card_selected: Optional[Callable] = None
        self.on_card_activated: Optional[Callable] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the card browser interface"""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Search section
        search_box = wx.StaticBox(self, label="Search")
        search_sizer = wx.StaticBoxSizer(search_box, wx.VERTICAL)

        # Search input
        search_panel = wx.Panel(self)
        search_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        search_label = wx.StaticText(search_panel, label="Search cards:")
        self.search_ctrl = wx.TextCtrl(search_panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetToolTip("Enter card name or text to search")

        search_panel_sizer.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        search_panel_sizer.Add(self.search_ctrl, 1, wx.EXPAND)
        search_panel.SetSizer(search_panel_sizer)

        # Filter controls
        filter_panel = wx.Panel(self)
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Class filter
        class_label = wx.StaticText(filter_panel, label="Class:")
        self.class_choice = wx.Choice(
            filter_panel,
            choices=[
                "All",
                "Demon Hunter",
                "Druid",
                "Hunter",
                "Mage",
                "Paladin",
                "Priest",
                "Rogue",
                "Shaman",
                "Warlock",
                "Warrior",
                "Neutral",
            ],
        )
        self.class_choice.SetSelection(0)

        # Type filter
        type_label = wx.StaticText(filter_panel, label="Type:")
        self.type_choice = wx.Choice(
            filter_panel,
            choices=["All", "Minion", "Spell", "Weapon", "Hero", "Location"],
        )
        self.type_choice.SetSelection(0)

        # Cost filter
        cost_label = wx.StaticText(filter_panel, label="Cost:")
        self.cost_choice = wx.Choice(
            filter_panel,
            choices=["All", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10+"],
        )
        self.cost_choice.SetSelection(0)

        filter_sizer.Add(class_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        filter_sizer.Add(self.class_choice, 0, wx.RIGHT, 10)
        filter_sizer.Add(type_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        filter_sizer.Add(self.type_choice, 0, wx.RIGHT, 10)
        filter_sizer.Add(cost_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        filter_sizer.Add(self.cost_choice, 0, wx.RIGHT, 10)

        filter_panel.SetSizer(filter_sizer)

        search_sizer.Add(search_panel, 0, wx.EXPAND | wx.ALL, 5)
        search_sizer.Add(filter_panel, 0, wx.EXPAND | wx.ALL, 5)

        # Results section
        results_box = wx.StaticBox(self, label="Results")
        results_sizer = wx.StaticBoxSizer(results_box, wx.VERTICAL)

        # Results list
        self.results_list = AccessibleListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL
        )
        self.results_list.AppendColumn("Name", width=200)
        self.results_list.AppendColumn("Cost", width=60)
        self.results_list.AppendColumn("Type", width=80)
        self.results_list.AppendColumn("Class", width=80)
        self.results_list.AppendColumn("Stats", width=80)
        self.results_list.AppendColumn("Text", width=300)

        results_sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 5)

        # Card details section
        details_box = wx.StaticBox(self, label="Card Details")
        details_sizer = wx.StaticBoxSizer(details_box, wx.VERTICAL)

        self.card_details = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP
        )
        self.card_details.SetMinSize(wx.Size(400, 120))

        details_sizer.Add(self.card_details, 1, wx.EXPAND | wx.ALL, 5)

        # Main layout
        sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(results_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(details_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)

        # Bind events
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search_text_changed)
        self.class_choice.Bind(wx.EVT_CHOICE, self.on_filter_changed)
        self.type_choice.Bind(wx.EVT_CHOICE, self.on_filter_changed)
        self.cost_choice.Bind(wx.EVT_CHOICE, self.on_filter_changed)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_card_list_selected)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_card_list_activated)

    def set_presenter(self, presenter):
        """Set the presenter for this view"""
        self.presenter = presenter

    def on_search(self, event):
        """Handle search button or enter key"""
        self.perform_search()

    def on_search_text_changed(self, event):
        """Handle search text changes (delayed search)"""
        # Could implement delayed search here if needed
        pass

    def on_filter_changed(self, event):
        """Handle filter changes"""
        self.perform_search()

    def perform_search(self):
        """Perform the actual search"""
        if not self.presenter:
            return

        query = self.search_ctrl.GetValue().strip()
        filters = self._get_current_filters()

        try:
            cards = self.presenter.search_cards(query, filters)
            self.update_results(cards)
        except Exception as e:
            wx.MessageBox(f"Search error: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _get_current_filters(self) -> Dict[str, Any]:
        """Get current filter settings"""
        filters = {}

        # Class filter
        class_sel = self.class_choice.GetSelection()
        if class_sel > 0:
            class_name = self.class_choice.GetStringSelection().upper()
            if class_name != "ALL":
                filters["card_class"] = class_name

        # Type filter
        type_sel = self.type_choice.GetSelection()
        if type_sel > 0:
            type_name = self.type_choice.GetStringSelection().upper()
            if type_name != "ALL":
                filters["card_type"] = type_name

        # Cost filter
        cost_sel = self.cost_choice.GetSelection()
        if cost_sel > 0:
            cost_text = self.cost_choice.GetStringSelection()
            if cost_text != "All":
                if cost_text == "10+":
                    filters["min_cost"] = 10
                else:
                    filters["cost"] = int(cost_text)

        return filters

    def update_results(self, cards):
        """Update the results list with found cards"""
        self.results_list.DeleteAllItems()

        for i, card in enumerate(cards):
            index = self.results_list.InsertItem(i, card.name)
            self.results_list.SetItem(index, 1, str(card.cost))
            self.results_list.SetItem(index, 2, card.card_type.title())
            self.results_list.SetItem(index, 3, card.card_class.title())

            # Stats column
            stats = []
            if card.attack is not None:
                stats.append(f"{card.attack}")
            if card.health is not None:
                stats.append(f"{card.health}")
            if card.durability is not None:
                stats.append(f"{card.durability}")
            stats_text = "/".join(stats) if stats else "-"
            self.results_list.SetItem(index, 4, stats_text)

            # Text column (truncated)
            text = card.text[:50] + "..." if len(card.text) > 50 else card.text
            self.results_list.SetItem(index, 5, text)

            # Store card object for later retrieval
            self.results_list.SetItemData(index, i)

        # Store cards for access
        self.current_cards = cards

        # Update status
        parent = self.GetParent()
        while parent and not hasattr(parent, "set_status"):
            parent = parent.GetParent()
        if parent:
            parent.set_status(f"Found {len(cards)} cards")

    def on_card_list_selected(self, event):
        """Handle card selection in results list"""
        selected = event.GetIndex()
        if selected >= 0 and hasattr(self, "current_cards"):
            card_index = self.results_list.GetItemData(selected)
            if card_index < len(self.current_cards):
                card = self.current_cards[card_index]
                self.show_card_details(card)

                if self.on_card_selected:
                    self.on_card_selected(card)

    def on_card_list_activated(self, event):
        """Handle card activation (double-click or enter)"""
        selected = event.GetIndex()
        if selected >= 0 and hasattr(self, "current_cards"):
            card_index = self.results_list.GetItemData(selected)
            if card_index < len(self.current_cards):
                card = self.current_cards[card_index]

                if self.on_card_activated:
                    self.on_card_activated(card)

    def show_card_details(self, card):
        """Show detailed card information"""
        if not self.presenter:
            return

        details = self.presenter.format_for_speech(card, "full")
        self.card_details.SetValue(details)

    def focus_search(self):
        """Set focus to search box"""
        self.search_ctrl.SetFocus()

    def get_selected_card(self):
        """Get currently selected card"""
        selected = self.results_list.GetFirstSelected()
        if selected >= 0 and hasattr(self, "current_cards"):
            card_index = self.results_list.GetItemData(selected)
            if card_index < len(self.current_cards):
                return self.current_cards[card_index]
        return None


class DeckViewPanel(wx.Panel):
    """Deck viewing and editing interface"""

    def __init__(self, parent):
        super().__init__(parent)

        # Presenter will be set later
        self.presenter = None
        self.current_deck = None

        # Event callbacks
        self.on_deck_imported: Optional[Callable] = None
        self.on_deck_exported: Optional[Callable] = None
        self.on_card_selected: Optional[Callable] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the deck view interface"""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Import/Export section
        import_box = wx.StaticBox(self, label="Import/Export")
        import_sizer = wx.StaticBoxSizer(import_box, wx.VERTICAL)

        # Deckstring import
        import_panel = wx.Panel(self)
        import_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        import_label = wx.StaticText(import_panel, label="Deckstring:")
        self.deckstring_ctrl = wx.TextCtrl(import_panel, style=wx.TE_PROCESS_ENTER)
        self.deckstring_ctrl.SetToolTip("Paste a Hearthstone deckstring here")

        self.import_btn = wx.Button(import_panel, label="Import")
        self.export_btn = wx.Button(import_panel, label="Export")
        self.export_btn.Enable(False)

        import_panel_sizer.Add(import_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        import_panel_sizer.Add(self.deckstring_ctrl, 1, wx.EXPAND | wx.RIGHT, 5)
        import_panel_sizer.Add(self.import_btn, 0, wx.RIGHT, 5)
        import_panel_sizer.Add(self.export_btn, 0)
        import_panel.SetSizer(import_panel_sizer)

        # Deck name
        name_panel = wx.Panel(self)
        name_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        name_label = wx.StaticText(name_panel, label="Deck Name:")
        self.deck_name_ctrl = wx.TextCtrl(name_panel)
        self.deck_name_ctrl.SetToolTip("Enter a name for this deck")

        name_panel_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        name_panel_sizer.Add(self.deck_name_ctrl, 1, wx.EXPAND)
        name_panel.SetSizer(name_panel_sizer)

        import_sizer.Add(import_panel, 0, wx.EXPAND | wx.ALL, 5)
        import_sizer.Add(name_panel, 0, wx.EXPAND | wx.ALL, 5)

        # Deck information section
        info_box = wx.StaticBox(self, label="Deck Information")
        info_sizer = wx.StaticBoxSizer(info_box, wx.HORIZONTAL)

        # Deck stats
        stats_panel = wx.Panel(self)
        stats_sizer = wx.BoxSizer(wx.VERTICAL)

        self.class_label = wx.StaticText(stats_panel, label="Class: -")
        self.format_label = wx.StaticText(stats_panel, label="Format: -")
        self.total_cards_label = wx.StaticText(stats_panel, label="Total Cards: -")
        self.avg_cost_label = wx.StaticText(stats_panel, label="Average Cost: -")
        self.dust_cost_label = wx.StaticText(stats_panel, label="Dust Cost: -")

        stats_sizer.Add(self.class_label, 0, wx.ALL, 2)
        stats_sizer.Add(self.format_label, 0, wx.ALL, 2)
        stats_sizer.Add(self.total_cards_label, 0, wx.ALL, 2)
        stats_sizer.Add(self.avg_cost_label, 0, wx.ALL, 2)
        stats_sizer.Add(self.dust_cost_label, 0, wx.ALL, 2)
        stats_panel.SetSizer(stats_sizer)

        # Mana curve
        curve_panel = wx.Panel(self)
        curve_sizer = wx.BoxSizer(wx.VERTICAL)

        curve_label = wx.StaticText(curve_panel, label="Mana Curve:")
        self.curve_text = wx.TextCtrl(
            curve_panel, style=wx.TE_MULTILINE | wx.TE_READONLY
        )
        self.curve_text.SetMinSize(wx.Size(200, 150))

        curve_sizer.Add(curve_label, 0, wx.ALL, 2)
        curve_sizer.Add(self.curve_text, 1, wx.EXPAND | wx.ALL, 2)
        curve_panel.SetSizer(curve_sizer)

        info_sizer.Add(stats_panel, 0, wx.EXPAND | wx.ALL, 5)
        info_sizer.Add(curve_panel, 1, wx.EXPAND | wx.ALL, 5)

        # Deck list section
        deck_box = wx.StaticBox(self, label="Deck List")
        deck_sizer = wx.StaticBoxSizer(deck_box, wx.VERTICAL)

        # Deck list control
        self.deck_list = AccessibleListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.deck_list.AppendColumn("Count", width=50)
        self.deck_list.AppendColumn("Name", width=200)
        self.deck_list.AppendColumn("Cost", width=50)
        self.deck_list.AppendColumn("Type", width=80)
        self.deck_list.AppendColumn("Stats", width=80)
        self.deck_list.AppendColumn("Text", width=300)

        deck_sizer.Add(self.deck_list, 1, wx.EXPAND | wx.ALL, 5)

        # Card details section
        details_box = wx.StaticBox(self, label="Card Details")
        details_sizer = wx.StaticBoxSizer(details_box, wx.VERTICAL)

        self.card_details = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP
        )
        self.card_details.SetMinSize(wx.Size(400, 100))

        details_sizer.Add(self.card_details, 1, wx.EXPAND | wx.ALL, 5)

        # Main layout
        sizer.Add(import_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(info_sizer, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(deck_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(details_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)

        # Bind events
        self.import_btn.Bind(wx.EVT_BUTTON, self.on_import_deck)
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export_deck)
        self.deckstring_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_import_deck)
        self.deck_name_ctrl.Bind(wx.EVT_TEXT, self.on_deck_name_changed)
        self.deck_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_deck_card_selected)

    def set_presenter(self, presenter):
        """Set the presenter for this view"""
        self.presenter = presenter

    def on_import_deck(self, event):
        """Handle deck import"""
        if not self.presenter:
            return

        deckstring = self.deckstring_ctrl.GetValue().strip()
        if not deckstring:
            wx.MessageBox(
                "Please enter a deckstring to import", "Error", wx.OK | wx.ICON_ERROR
            )
            return

        deck_name = self.deck_name_ctrl.GetValue().strip() or "Imported Deck"

        try:
            deck = self.presenter.import_deck_string(deckstring, deck_name)
            self.set_deck(deck)

            if self.on_deck_imported:
                self.on_deck_imported(deck)

            # Update status
            parent = self.GetParent()
            while parent and not hasattr(parent, "set_status"):
                parent = parent.GetParent()
            if parent:
                parent.set_status(f"Imported deck: {deck.name}")

        except Exception as e:
            wx.MessageBox(
                f"Failed to import deck: {str(e)}", "Error", wx.OK | wx.ICON_ERROR
            )

    def on_export_deck(self, event):
        """Handle deck export"""
        if not self.presenter or not self.current_deck:
            return

        try:
            deckstring = self.presenter.export_deck_string(self.current_deck)

            # Copy to clipboard
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(deckstring))
                wx.TheClipboard.Close()

                wx.MessageBox(
                    "Deckstring copied to clipboard",
                    "Export Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )

                if self.on_deck_exported:
                    self.on_deck_exported(self.current_deck, deckstring)

        except Exception as e:
            wx.MessageBox(
                f"Failed to export deck: {str(e)}", "Error", wx.OK | wx.ICON_ERROR
            )

    def on_deck_name_changed(self, event):
        """Handle deck name change"""
        if self.current_deck:
            # Note: Deck is immutable, so we'd need to create a new one
            # For now, just update the display
            pass

    def on_deck_card_selected(self, event):
        """Handle card selection in deck list"""
        selected = event.GetIndex()
        if selected >= 0 and self.current_deck:
            card_index = self.deck_list.GetItemData(selected)
            if card_index < len(self.current_deck.cards):
                card, count = self.current_deck.cards[card_index]
                self.show_card_details(card)

                if self.on_card_selected:
                    self.on_card_selected(card)

    def set_deck(self, deck):
        """Set the current deck and update the display"""
        self.current_deck = deck
        self.deck_name_ctrl.SetValue(deck.name)
        self.export_btn.Enable(True)

        self._update_deck_info()
        self._update_deck_list()
        self._update_mana_curve()

    def _update_deck_info(self):
        """Update deck information display"""
        if not self.current_deck:
            return

        deck = self.current_deck

        self.class_label.SetLabel(f"Class: {deck.hero_class.title()}")
        self.format_label.SetLabel(f"Format: {deck.format}")
        self.total_cards_label.SetLabel(f"Total Cards: {deck.total_cards()}")
        self.avg_cost_label.SetLabel(f"Average Cost: {deck.average_cost():.1f}")
        self.dust_cost_label.SetLabel(f"Dust Cost: {deck.total_dust_cost}")

    def _update_deck_list(self):
        """Update the deck list display"""
        if not self.current_deck:
            return

        self.deck_list.DeleteAllItems()

        # Sort cards by cost, then by name
        sorted_cards = sorted(
            self.current_deck.cards, key=lambda x: (x[0].cost, x[0].name)
        )

        for i, (card, count) in enumerate(sorted_cards):
            index = self.deck_list.InsertItem(i, str(count))
            self.deck_list.SetItem(index, 1, card.name)
            self.deck_list.SetItem(index, 2, str(card.cost))
            self.deck_list.SetItem(index, 3, card.card_type.title())

            # Stats column
            stats = []
            if card.attack is not None:
                stats.append(f"{card.attack}")
            if card.health is not None:
                stats.append(f"{card.health}")
            if card.durability is not None:
                stats.append(f"{card.durability}")
            stats_text = "/".join(stats) if stats else "-"
            self.deck_list.SetItem(index, 4, stats_text)

            # Text column (truncated)
            text = card.text[:40] + "..." if len(card.text) > 40 else card.text
            self.deck_list.SetItem(index, 5, text)

            # Store card index for later retrieval
            original_index = self.current_deck.cards.index((card, count))
            self.deck_list.SetItemData(index, original_index)

    def _update_mana_curve(self):
        """Update the mana curve display"""
        if not self.current_deck:
            return

        # Calculate mana curve
        curve = {}
        for card, count in self.current_deck.cards:
            cost = min(card.cost, 10)  # Cap at 10+
            curve[cost] = curve.get(cost, 0) + count

        # Generate text representation
        curve_text = []
        for cost in range(11):
            count = curve.get(cost, 0)
            cost_label = f"{cost}+" if cost == 10 else str(cost)
            bar = "█" * count
            curve_text.append(f"{cost_label:2}: {count:2} {bar}")

        self.curve_text.SetValue("\n".join(curve_text))

    def show_card_details(self, card):
        """Show detailed card information"""
        if not self.presenter:
            return

        details = card.to_speech_text("detailed")
        self.card_details.SetValue(details)

    def clear_deck(self):
        """Clear the current deck"""
        self.current_deck = None
        self.deck_name_ctrl.SetValue("")
        self.deckstring_ctrl.SetValue("")
        self.export_btn.Enable(False)

        # Clear displays
        self.class_label.SetLabel("Class: -")
        self.format_label.SetLabel("Format: -")
        self.total_cards_label.SetLabel("Total Cards: -")
        self.avg_cost_label.SetLabel("Average Cost: -")
        self.dust_cost_label.SetLabel("Dust Cost: -")

        self.deck_list.DeleteAllItems()
        self.curve_text.SetValue("")
        self.card_details.SetValue("")

    def get_current_deck(self):
        """Get the current deck"""
        return self.current_deck

    def focus_import(self):
        """Set focus to deckstring input"""
        self.deckstring_ctrl.SetFocus()


class ReplayViewerPanel(wx.Panel):
    """Game replay viewer with zone navigation"""

    def __init__(self, parent):
        super().__init__(parent)
        # Implements zone-based keyboard navigation
        # b: player board, g: opponent board, etc.
        pass


class AccessibleListCtrl(wx.ListCtrl):
    """Custom list control with enhanced screen reader support"""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Bind navigation keys
        self.Bind(wx.EVT_KEY_DOWN, self.on_navigation_key)

    def on_navigation_key(self, event):
        """Handle arrow keys for line-by-line reading"""
        key_code = event.GetKeyCode()

        if key_code in [wx.WXK_UP, wx.WXK_DOWN, wx.WXK_HOME, wx.WXK_END]:
            # Let the default handler process the navigation
            event.Skip()

            # After navigation, announce the current item
            wx.CallAfter(self._announce_current_item)
        else:
            event.Skip()

    def _announce_current_item(self):
        """Announce the current item for screen readers"""
        selected = self.GetFirstSelected()
        if selected >= 0:
            # Get all column text for the selected item
            item_text = []
            for col in range(self.GetColumnCount()):
                text = self.GetItemText(selected, col)
                if text.strip():
                    header = self.GetColumn(col).GetText()
                    item_text.append(f"{header}: {text}")

            # Create announcement text
            announcement = ", ".join(item_text)

            # Use accessibility API to announce (this would need platform-specific implementation)
            # For now, we'll just set the tooltip as a simple fallback
            self.SetToolTip(announcement)

    def GetItemTextForSpeech(self, item):
        """Get formatted text for screen reader announcement"""
        if item < 0 or item >= self.GetItemCount():
            return ""

        # Get all column text
        item_text = []
        for col in range(self.GetColumnCount()):
            text = self.GetItemText(item, col)
            if text.strip():
                header = self.GetColumn(col).GetText()
                item_text.append(f"{header}: {text}")

        return ", ".join(item_text)
