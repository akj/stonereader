from __future__ import annotations

from collections.abc import Callable

from stonereader.ui.announcer import Announcer
from stonereader.ui.arming import ArmedAction

from tests.support import FakeSpeech


class FakeEngine:
    def __init__(self) -> None:
        self._subscribers: list[Callable[[], None]] = []

    def subscribe(self, on_change: Callable[[], None]) -> None:
        self._subscribers.append(on_change)

    def change(self) -> None:
        for subscriber in self._subscribers:
            subscriber()


def test_arms_rearms_disarms_on_change_and_acts_on_matching_repeat() -> None:
    speech = FakeSpeech()
    engine = FakeEngine()
    armed = ArmedAction(engine, Announcer(speech))
    actions: list[str] = []

    armed.press("one", "Press again for one", lambda: actions.append("one"))
    armed.press("two", "Press again for two", lambda: actions.append("two"))
    engine.change()
    armed.press("two", "Press again for two", lambda: actions.append("two"))
    armed.press("two", "Press again for two", lambda: actions.append("two"))
    armed.press("two", "Press again for two", lambda: actions.append("two-again"))

    assert actions == ["two"]
    assert speech.calls == [
        ("Press again for one", True),
        ("Press again for two", True),
        ("Press again for two", True),
        ("Press again for two", True),
    ]
