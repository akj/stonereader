from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionRow:
    action_id: str
    label: str
