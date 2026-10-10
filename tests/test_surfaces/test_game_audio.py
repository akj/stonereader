from __future__ import annotations

import threading
from pathlib import Path

from stonereader.services._audio_index import AudioIndex, ScannedClip
from stonereader.services._settings import SettingsStore
from stonereader.surfaces._game_audio import open_sounds_for_card
from stonereader.surfaces.sounds_menu import SoundsMenuHolder

from .conftest import make_harness


def _store(tmp_path: Path, *, installed: bool) -> SettingsStore:
    store = SettingsStore(tmp_path / "settings.json")
    if installed:
        install = tmp_path / "Hearthstone"
        managers = install / "Hearthstone_Data" / "globalgamemanagers"
        managers.parent.mkdir(parents=True)
        managers.write_bytes(b"build")
        store.set_hs_install_path(install)
    return store


def _listen(index: AudioIndex) -> tuple[tuple[str, bool], tuple[str, ...]]:
    harness = make_harness(None)
    open_sounds_for_card(
        harness.announcer,
        harness.nav,
        index,
        SoundsMenuHolder(),
        card_id="CARD_1",
        card_name="Fireball",
        title="Fireball",
    )
    return harness.speech.calls[-1], harness.nav.stack


def test_listen_says_no_install_only_when_none_was_found(tmp_path: Path) -> None:
    index = AudioIndex(
        _store(tmp_path, installed=False),
        cache_dir=tmp_path / "cache",
        install_detector=lambda _custom: None,
    )
    index.start()

    assert _listen(index) == (
        ("Game audio is unavailable — no Hearthstone install found", True),
        ("Home",),
    )


def test_listen_says_still_preparing_while_indexing(tmp_path: Path) -> None:
    entered = threading.Event()
    release = threading.Event()

    def blocking_scan(_install: Path, _version: str) -> list[ScannedClip]:
        entered.set()
        assert release.wait(timeout=2)
        return []

    index = AudioIndex(
        _store(tmp_path, installed=True),
        cache_dir=tmp_path / "cache",
        scanner=blocking_scan,
        unity_version_detector=lambda _install: "6000.3.11f1",
    )
    index.start()
    assert entered.wait(timeout=2)
    try:
        assert _listen(index) == (
            ("Game audio is still preparing", True),
            ("Home",),
        )
    finally:
        release.set()
        index.wait(timeout=2)


def test_listen_says_unreadable_when_indexing_fails(tmp_path: Path) -> None:
    def broken_scan(_install: Path, _version: str) -> list[ScannedClip]:
        raise OSError("bundle unreadable")

    index = AudioIndex(
        _store(tmp_path, installed=True),
        cache_dir=tmp_path / "cache",
        scanner=broken_scan,
        unity_version_detector=lambda _install: "6000.3.11f1",
    )
    index.start()
    index.wait(timeout=2)

    assert _listen(index) == (
        (
            "Game audio is unavailable — couldn't read Hearthstone's audio files",
            True,
        ),
        ("Home",),
    )
