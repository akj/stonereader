from __future__ import annotations

from stonereader.ui.announcer import Announcer

from .conftest import FakeSpeech


def test_every_template_and_lane() -> None:
    speech = FakeSpeech()
    announcer = Announcer(speech)

    announcer.context_entry("Cards", "Fireball", 1, 12)
    announcer.context_entry_menu("Home", "Cards")
    announcer.context_empty("Replays")
    announcer.moved("Fireball")
    announcer.boundary("Fireball")
    announcer.confirmation("Fireball copied")
    announcer.offer("Deck code on clipboard — press Control Enter to import")
    announcer.query("Your deck", "23 cards")
    announcer.noop("No search on this screen")
    announcer.narrate("Opponent played Fireball")
    announcer.context_entry("Cards", "Frostbolt", 2, 12, queued=True)
    announcer.context_empty("Cards", queued=True)
    announcer.moved("queued detail", queued=True)

    assert speech.calls == [
        ("Cards, Fireball, 1 of 12", True),
        ("Home, Cards", True),
        ("Replays: empty", True),
        ("Fireball", True),
        ("Fireball", True),
        ("Fireball copied", True),
        ("Deck code on clipboard — press Control Enter to import", True),
        ("Your deck, 23 cards", True),
        ("No search on this screen", True),
        ("Opponent played Fireball", False),
        ("Cards, Frostbolt, 2 of 12", False),
        ("Cards: empty", False),
        ("queued detail", False),
    ]
