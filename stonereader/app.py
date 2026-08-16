"""Main application window and wx.App setup.

Provides the frame-level declarative Surface shell and the application entry
point that wires long-lived services into it.
"""

from __future__ import annotations

import binascii
import logging
import sqlite3
from collections.abc import Callable

import wx
from hearthstone.deckstrings import parse_deckstring

from stonereader.db import get_connection, init_db
from stonereader.speech_service import SpeechService
from stonereader.surfaces._deck_data import CurrentDeck, DeckData
from stonereader.surfaces.deck_detail import build_deck_detail
from stonereader.surfaces.decks import build_decks
from stonereader.surfaces.home import build_home
from stonereader.surfaces.import_deck import ImportDeckField, build_import_deck
from stonereader.ui import (
    ActiveSurface,
    Announcer,
    Chord,
    Command,
    HorizontalListEngine,
    InputSink,
    NavigationController,
    VerticalMenuEngine,
)
from stonereader.views.surface_panel import SurfacePanel


class MainWindow(wx.Frame):
    """Top-level frame hosting the single input sink and active Surface."""

    def __init__(self) -> None:
        super().__init__(
            None,
            title="Home — StoneReader",
            size=wx.Size(800, 600),
        )

        self._speech = SpeechService()
        self._announcer = Announcer(self._speech)

        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self._sizer)
        self._panels: dict[str, SurfacePanel] = {}
        self._current_panel: SurfacePanel | None = None

        self._sink = InputSink(self, self._announcer, stop_audio=lambda: None)
        self._nav = NavigationController(
            set_title=self.SetTitle,
            announcer=self._announcer,
            stop_audio=lambda: None,
            activate=self._activate_surface,
        )
        self._universal_bindings = [
            (
                Chord("f1"),
                Command(
                    "app.help",
                    "F1: help for this screen",
                    self._announce_help_placeholder,
                ),
            ),
            (
                Chord("q", ctrl=True),
                Command(
                    "app.quit",
                    "Ctrl+Q: quit StoneReader",
                    self._quit,
                ),
            ),
        ]

        self._db_conn = get_connection()
        init_db(self._db_conn)

        self._clipboard_offer_accept: Callable[[str], None] | None = None
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    @property
    def speech(self) -> SpeechService:
        return self._speech

    @property
    def announcer(self) -> Announcer:
        return self._announcer

    @property
    def db_conn(self) -> sqlite3.Connection:
        return self._db_conn

    @property
    def nav(self) -> NavigationController:
        return self._nav

    @property
    def universal_bindings(self) -> list[tuple[Chord, Command]]:
        return self._universal_bindings

    def _activate_surface(self, surface: ActiveSurface) -> None:
        self._sink.set_active(surface.registry)
        panel = self._panels.get(surface.spec.name)
        if panel is None:
            engine = surface.engine
            if not isinstance(engine, (VerticalMenuEngine, HorizontalListEngine)):
                raise TypeError("SurfacePanel requires a supported Surface engine")
            panel = SurfacePanel(self, engine)
            panel.Hide()
            self._panels[surface.spec.name] = panel
            self._sizer.Add(panel, 1, wx.EXPAND)

        if self._current_panel is not None and self._current_panel is not panel:
            self._current_panel.Hide()
        panel.Show()
        self._current_panel = panel
        self._sizer.Layout()

    def _announce_help_placeholder(self) -> None:
        self._announcer.noop("Help is not yet migrated")

    def configure_clipboard_offer(
        self,
        on_accept: Callable[[str], None],
    ) -> None:
        """Install the Offer route and suppress the startup clipboard value."""
        self._clipboard_offer_accept = on_accept
        initial = _read_clipboard_text()
        if initial is not None:
            self._sink.mark_offer_subject_seen(initial)

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        accept = self._clipboard_offer_accept
        if event.GetActive() and accept is not None:
            text = _read_clipboard_text()
            if text is not None and _is_deckstring(text):
                armed = self._sink.arm_offer(
                    text,
                    lambda text=text: accept(text),
                )
                if armed:
                    self._announcer.offer(
                        "Deck code on clipboard — press Control Enter to import"
                    )
        event.Skip()

    def _quit(self) -> None:
        self.Close()

    def _on_close(self, event: wx.CloseEvent) -> None:
        # Cleanup order (Runtime State Inventory, plan 03-06):
        #   hotkeys.clear_all() -> live_presenter.cleanup()
        #   -> tracker.stop() -> db_conn.close() -> Destroy()
        # Every step is isolated so a failure cannot prevent later cleanup.
        log = logging.getLogger(__name__)
        hotkeys = getattr(self, "_hotkeys", None)
        if hotkeys is not None:
            try:
                hotkeys.clear_all()
            except Exception:
                log.exception("hotkeys.clear_all() failed; continuing cleanup")
        live_presenter = getattr(self, "_live_presenter", None)
        if live_presenter is not None:
            try:
                live_presenter.cleanup()
            except Exception:
                log.exception("live_presenter.cleanup() failed; continuing cleanup")
        tracker = getattr(self, "_tracker", None)
        if tracker is not None:
            try:
                tracker.stop()
            except Exception:
                log.exception("tracker.stop() failed; continuing cleanup")
        db_conn = getattr(self, "_db_conn", None)
        if db_conn is not None:
            try:
                db_conn.close()
            except Exception:
                log.exception("db_conn.close() failed; continuing cleanup")
        self.Destroy()


class StoneReaderApp(wx.App):
    """Application entry point."""

    def OnInit(self) -> bool:  # noqa: N802 -- wx override
        self._frame = MainWindow()
        nav = self._frame.nav
        speech = self._frame.speech
        announcer = self._frame.announcer
        db_conn = self._frame.db_conn

        # Load card database even while its Surface is staged as a placeholder.
        from stonereader.models.card import CardDatabase

        card_db = CardDatabase.load()

        current_deck = CurrentDeck()
        deck_data = DeckData(db_conn, card_db)
        import_field = ImportDeckField()

        # --- Game Tracker (Phase 2) ---
        # Logging is bootstrapped exactly once in __main__.py. This per-launch
        # log.config bootstrap remains separate and silent unless it changed.
        from stonereader.services import GameTracker
        from stonereader.services._log_config import ensure_log_config

        try:
            log_config_changed = ensure_log_config()
            if log_config_changed:
                speech.speak("Hearthstone logging enabled.")
        except Exception:
            logging.getLogger(__name__).exception(
                "ensure_log_config failed; continuing"
            )

        self._tracker = GameTracker(card_db=card_db)
        self._frame._tracker = self._tracker  # type: ignore[attr-defined]

        # --- Replay persistence (PRD #7) ---
        from stonereader.services._build_info import current_build
        from stonereader.services._replay_recorder import ReplayRecorder
        from stonereader.services._replay_store import ReplayStore, default_replay_dir

        replay_store = ReplayStore(db_conn, default_replay_dir())
        self._recorder = ReplayRecorder(replay_store, build_provider=current_build)
        self._tracker.subscribe(self._recorder.on_state)
        self._tracker.add_raw_subscriber(
            self._recorder.on_lines,
            self._recorder.on_reset,
        )

        names = ("Live Game", "Cards", "Replays", "Settings")
        targets: dict[str, Callable[[], None]] = {
            name: lambda name=name: announcer.noop(f"{name}: not yet migrated")
            for name in names
        }
        targets["Decks"] = lambda: nav.jump("Decks")

        def home_factory() -> ActiveSurface:
            return build_home(
                announcer,
                self._frame.universal_bindings,
                nav,
                targets,
            )

        def decks_factory() -> ActiveSurface:
            return build_decks(
                announcer,
                self._frame.universal_bindings,
                nav,
                db_conn,
                deck_data,
                current_deck,
                self._frame._sink,
                _copy_to_clipboard,
            )

        def deck_detail_factory() -> ActiveSurface:
            return build_deck_detail(
                announcer,
                self._frame.universal_bindings,
                nav,
                deck_data,
                current_deck,
            )

        def import_deck_factory() -> ActiveSurface:
            return build_import_deck(
                announcer,
                self._frame.universal_bindings,
                nav,
                db_conn,
                card_db,
                self._frame._sink,
                import_field,
            )

        nav.register("Home", home_factory)
        nav.register("Decks", decks_factory)
        nav.register("Deck detail", deck_detail_factory)
        nav.register("Import Deck", import_deck_factory)

        def accept_clipboard_deck(text: str) -> None:
            import_field.set(text)
            nav.jump_path(["Home", "Decks", "Import Deck"])

        self._frame.configure_clipboard_offer(accept_clipboard_deck)
        nav.jump("Home")

        self._frame.Show()

        # Start after Show() so wx.Timer cannot fire before the visible frame's
        # message loop is ready.
        try:
            self._tracker.start(parent=self._frame)
        except Exception:
            logging.getLogger(__name__).exception(
                "tracker.start() failed; tracker disabled"
            )

        return True


def _read_clipboard_text() -> str | None:
    if not wx.TheClipboard.Open():
        return None
    try:
        data = wx.TextDataObject()
        if not wx.TheClipboard.GetData(data):
            return None
        # Deck codes are copied with stray whitespace often enough that the
        # subject and the parse must both see the trimmed string.
        return data.GetText().strip()
    finally:
        wx.TheClipboard.Close()


def _copy_to_clipboard(text: str) -> None:
    if not wx.TheClipboard.Open():
        raise RuntimeError("Could not open the clipboard")
    try:
        if not wx.TheClipboard.SetData(wx.TextDataObject(text)):
            raise RuntimeError("Could not write to the clipboard")
        wx.TheClipboard.Flush()
    finally:
        wx.TheClipboard.Close()


def _is_deckstring(text: str) -> bool:
    try:
        parse_deckstring(text)
    except (binascii.Error, EOFError, TypeError, UnicodeError, ValueError):
        return False
    return True
