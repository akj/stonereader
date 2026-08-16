from __future__ import annotations

from stonereader.services._audio_index import CardClip
from stonereader.surfaces.sounds_menu import SoundsMenuHolder, build_sounds_menu
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.navigation import NavigationController

from tests.test_ui.conftest import FakeSpeech


class FakeIndex:
    status = "ready"
    reason = ""

    def clips_for_card(self, card_id: str) -> list[CardClip]:
        assert card_id == "CARD_1"
        return [CardClip("Play", "play-key"), CardClip("Death", "death-key")]

    def decode(self, clip_key: str) -> bytes:
        return f"wav:{clip_key}".encode()


class FakePlayer:
    def __init__(self) -> None:
        self.played: list[bytes] = []

    def play(self, wav_bytes: bytes) -> None:
        self.played.append(wav_bytes)


def test_sounds_menu_lists_without_focus_play_and_enter_plays() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    holder = SoundsMenuHolder()
    holder.set("CARD_1", "Test Card")
    player = FakePlayer()
    nav.register(
        "Sounds menu",
        lambda: build_sounds_menu(
            announcer,
            [],
            nav,
            holder,
            FakeIndex(),
            player,
        ),
    )

    nav.jump("Sounds menu")
    surface = nav.peek("Sounds menu")
    assert surface.spec.display_name is not None
    assert surface.spec.display_name() == "Test Card sounds"
    assert surface.engine.options_snapshot()[0] == ["Play", "Death"]
    assert player.played == []

    sink.handle_chord(Chord("down"))
    assert player.played == []
    sink.handle_chord(Chord("enter"))
    assert player.played == [b"wav:death-key"]
