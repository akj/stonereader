from __future__ import annotations

import json
from pathlib import Path

from stonereader.services._settings import SettingsStore


def test_defaults_when_file_is_missing(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "nested" / "settings.json")

    assert store.narration == "key_moments"
    assert store.game_audio_volume == 80
    assert store.replay_autoplay is True
    assert store.hs_install_path is None
    assert store.hs_log_path is None
    assert store.replay_retention is None
    assert store.hotkey_overrides == {}


def test_missing_keys_use_defaults_and_unknown_keys_survive_save(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"narration": "off", "future_setting": {"enabled": True}}),
        encoding="utf-8",
    )

    store = SettingsStore(path)
    assert store.narration == "off"
    assert store.game_audio_volume == 80

    store.set_replay_autoplay(False)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["future_setting"] == {"enabled": True}
    assert saved["replay_autoplay"] is False


def test_every_setter_autosaves_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "subdirectory" / "settings.json"
    store = SettingsStore(path)
    changes: list[str] = []
    store.subscribe(lambda: changes.append("changed"))

    install = tmp_path / "Hearthstone"
    log = tmp_path / "Power.log"
    store.set_narration("everything")
    store.set_game_audio_volume(30)
    store.set_replay_autoplay(False)
    store.set_hs_install_path(install)
    store.set_hs_log_path(log)
    store.set_replay_retention(500)
    store.set_hotkey_chord("jump_cards", "ctrl+alt+c")

    assert path.exists()
    assert len(changes) == 7
    loaded = SettingsStore(path)
    assert loaded.narration == "everything"
    assert loaded.game_audio_volume == 30
    assert loaded.replay_autoplay is False
    assert loaded.hs_install_path == install
    assert loaded.hs_log_path == log
    assert loaded.replay_retention == 500
    assert loaded.hotkey_chord("jump_cards") == "ctrl+alt+c"


def test_restore_defaults_preserves_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"future": 1, "narration": "off"}), encoding="utf-8")
    store = SettingsStore(path)
    store.set_hotkey_chord("jump_cards", "ctrl+alt+c")

    store.restore_defaults()

    assert store.narration == "key_moments"
    assert store.hotkey_overrides == {}
    assert json.loads(path.read_text(encoding="utf-8"))["future"] == 1
