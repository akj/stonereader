from __future__ import annotations

from stonereader.services._audio_index import CardClip
from stonereader.surfaces.sounds_menu import SoundsMenuHolder, build_sounds_menu
from stonereader.ui.chords import Chord

from .conftest import make_harness


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
    holder = SoundsMenuHolder()
    holder.set("CARD_1", "Test Card")
    player = FakePlayer()
    harness = make_harness((holder, player))
    harness.nav.register(
        "Sounds menu",
        lambda: build_sounds_menu(
            harness.announcer,
            [],
            harness.nav,
            holder,
            FakeIndex(),
            player,
        ),
    )

    harness.nav.jump("Sounds menu")
    surface = harness.nav.peek("Sounds menu")
    assert surface.spec.display_name is not None
    assert surface.spec.display_name() == "Test Card sounds"
    assert harness.vertical.options_snapshot()[0] == ["Play", "Death"]
    assert player.played == []

    harness.press(Chord("down"))
    assert player.played == []
    harness.press(Chord("enter"))
    assert player.played == [b"wav:death-key"]
