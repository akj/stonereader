"""App-wide armed-action behavior (ADR-0004)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from stonereader.ui.announcer import Announcer


class ChangeSource(Protocol):
    """The engine notification seam needed to disarm on movement."""

    def subscribe(self, on_change: Callable[[], None]) -> None: ...


class ArmedAction:
    """Require a repeated press on the same subject before acting."""

    def __init__(self, engine: ChangeSource, announcer: Announcer) -> None:
        self._announcer = announcer
        self._subject_key: str | None = None
        engine.subscribe(self.disarm)

    def press(
        self,
        subject_key: str,
        arm_phrase: str,
        action: Callable[[], None],
    ) -> None:
        """Arm a subject, or act when the already-armed subject is repeated."""
        if self._subject_key == subject_key:
            self.disarm()
            action()
            return
        self._subject_key = subject_key
        self._announcer.noop(arm_phrase)

    def disarm(self) -> None:
        """Silently clear any pending action after state changes."""
        self._subject_key = None
