"""Typed, autosaving application settings (ADR-0011)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


DEFAULT_NARRATION = "key_moments"
DEFAULT_GAME_AUDIO_VOLUME = 80
DEFAULT_REPLAY_AUTOPLAY = True
DEFAULT_REPLAY_RETENTION: int | None = None

_NARRATION_VALUES = frozenset({"off", "key_moments", "everything"})
_RETENTION_VALUES = frozenset({None, 100, 500, 1000})
_KNOWN_KEYS = frozenset(
    {
        "narration",
        "game_audio_volume",
        "replay_autoplay",
        "hs_install_path",
        "hs_log_path",
        "replay_retention",
        "hotkeys",
    }
)


class SettingsStore:
    """Load typed settings and persist every mutation immediately."""

    def __init__(
        self,
        path: Path = Path.home() / ".stonereader" / "settings.json",
    ) -> None:
        self._path = path
        self._unknown: dict[str, Any] = {}
        self._subscribers: list[Callable[[], None]] = []
        self._narration = DEFAULT_NARRATION
        self._game_audio_volume = DEFAULT_GAME_AUDIO_VOLUME
        self._replay_autoplay = DEFAULT_REPLAY_AUTOPLAY
        self._hs_install_path: Path | None = None
        self._hs_log_path: Path | None = None
        self._replay_retention = DEFAULT_REPLAY_RETENTION
        self._hotkeys: dict[str, str] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def narration(self) -> str:
        return self._narration

    @property
    def game_audio_volume(self) -> int:
        return self._game_audio_volume

    @property
    def replay_autoplay(self) -> bool:
        return self._replay_autoplay

    @property
    def hs_install_path(self) -> Path | None:
        return self._hs_install_path

    @property
    def hs_log_path(self) -> Path | None:
        return self._hs_log_path

    @property
    def replay_retention(self) -> int | None:
        return self._replay_retention

    def hotkey_chord(self, command_id: str) -> str | None:
        """Return a command override; missing means its declared default."""
        return self._hotkeys.get(command_id)

    @property
    def hotkey_overrides(self) -> dict[str, str]:
        return dict(self._hotkeys)

    def subscribe(self, on_change: Callable[[], None]) -> None:
        if on_change not in self._subscribers:
            self._subscribers.append(on_change)

    def set_narration(self, value: str) -> None:
        if value not in _NARRATION_VALUES:
            raise ValueError(f"Unknown narration preset: {value}")
        self._narration = value
        self._save_and_notify()

    def set_game_audio_volume(self, value: int) -> None:
        if isinstance(value, bool) or value not in range(0, 101, 10):
            raise ValueError("Game audio volume must be 0-100 in steps of 10")
        self._game_audio_volume = value
        self._save_and_notify()

    def set_replay_autoplay(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("Replay auto-play must be a bool")
        self._replay_autoplay = value
        self._save_and_notify()

    def set_hs_install_path(self, value: Path | str | None) -> None:
        self._hs_install_path = _optional_path(value)
        self._save_and_notify()

    def set_hs_log_path(self, value: Path | str | None) -> None:
        self._hs_log_path = _optional_path(value)
        self._save_and_notify()

    def set_replay_retention(self, value: int | None) -> None:
        if isinstance(value, bool) or value not in _RETENTION_VALUES:
            raise ValueError("Replay retention must be None, 100, 500, or 1000")
        self._replay_retention = value
        self._save_and_notify()

    def set_hotkey_chord(self, command_id: str, chord: str | None) -> None:
        if not command_id:
            raise ValueError("Hotkey command id must not be empty")
        if chord is None:
            self._hotkeys.pop(command_id, None)
        else:
            self._hotkeys[command_id] = chord
        self._save_and_notify()

    def restore_defaults(self) -> None:
        self._narration = DEFAULT_NARRATION
        self._game_audio_volume = DEFAULT_GAME_AUDIO_VOLUME
        self._replay_autoplay = DEFAULT_REPLAY_AUTOPLAY
        self._hs_install_path = None
        self._hs_log_path = None
        self._replay_retention = DEFAULT_REPLAY_RETENTION
        self._hotkeys.clear()
        self._save_and_notify()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return
        if not isinstance(raw, dict):
            return
        self._unknown = {key: value for key, value in raw.items() if key not in _KNOWN_KEYS}
        narration = raw.get("narration")
        if narration in _NARRATION_VALUES:
            self._narration = narration
        volume = raw.get("game_audio_volume")
        if isinstance(volume, int) and not isinstance(volume, bool) and volume in range(0, 101, 10):
            self._game_audio_volume = volume
        autoplay = raw.get("replay_autoplay")
        if isinstance(autoplay, bool):
            self._replay_autoplay = autoplay
        self._hs_install_path = _loaded_path(raw.get("hs_install_path"))
        self._hs_log_path = _loaded_path(raw.get("hs_log_path"))
        retention = raw.get("replay_retention")
        if not isinstance(retention, bool) and retention in _RETENTION_VALUES:
            self._replay_retention = retention
        hotkeys = raw.get("hotkeys")
        if isinstance(hotkeys, dict):
            self._hotkeys = {
                key: value
                for key, value in hotkeys.items()
                if isinstance(key, str) and isinstance(value, str)
            }

    def _save_and_notify(self) -> None:
        payload = {
            **self._unknown,
            "narration": self._narration,
            "game_audio_volume": self._game_audio_volume,
            "replay_autoplay": self._replay_autoplay,
            "hs_install_path": _serialized_path(self._hs_install_path),
            "hs_log_path": _serialized_path(self._hs_log_path),
            "replay_retention": self._replay_retention,
            "hotkeys": dict(self._hotkeys),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for subscriber in tuple(self._subscribers):
            subscriber()


def _optional_path(value: Path | str | None) -> Path | None:
    if value is None:
        return None
    return Path(value)


def _loaded_path(value: object) -> Path | None:
    return Path(value) if isinstance(value, str) else None


def _serialized_path(value: Path | None) -> str | None:
    return str(value) if value is not None else None
