from __future__ import annotations

from pathlib import Path
import threading

from stonereader.services._audio_index import (
    AudioIndex,
    ParsedClip,
    ScannedClip,
    parse_clip_name,
)
from stonereader.services._settings import SettingsStore


def test_clip_names_map_vo_foley_and_generic_event_families() -> None:
    assert parse_clip_name("VO_REV_956_Male_Dwarf_Play_01") == ParsedClip(
        card_id="REV_956",
        event="Play",
    )
    assert parse_clip_name("VO_EX1_603_Play_01") == ParsedClip(
        card_id="EX1_603",
        event="Play",
    )
    assert parse_clip_name("VO_CATA_483_X_Elemental_Death_01") == ParsedClip(
        card_id="CATA_483",
        event="Death",
    )
    assert parse_clip_name("EX1_001_Attack") == ParsedClip(
        card_id="EX1_001",
        event="Attack",
    )
    assert parse_clip_name("ALERT_YourTurn_0v2") == ParsedClip(
        generic_kind="turn",
    )
    assert parse_clip_name("draw_card_2") == ParsedClip(generic_kind="draw")
    assert parse_clip_name("FX_Minion_AttackImpactLarge") == ParsedClip(
        generic_kind="attack",
    )
    assert parse_clip_name("Minion_Death_06") == ParsedClip(
        generic_kind="minion_death",
    )
    assert parse_clip_name("FX_Secret_Birth") == ParsedClip(
        generic_kind="secret",
    )
    assert parse_clip_name("victory_jingle") == ParsedClip(
        generic_kind="victory",
    )
    assert parse_clip_name("hero_power_icon_flip_on") is None


def test_ready_index_humanizes_and_numbers_merged_vo_and_foley_labels(
    tmp_path: Path,
) -> None:
    install = tmp_path / "Hearthstone"
    managers = install / "Hearthstone_Data" / "globalgamemanagers"
    managers.parent.mkdir(parents=True)
    managers.write_bytes(b"build")
    store = SettingsStore(tmp_path / "settings.json")
    store.set_hs_install_path(install)
    scanned = [
        ScannedClip("Data/Win/a.unity3d", "VO_CARD_1_Male_Human_Trigger_02"),
        ScannedClip("Data/Win/a.unity3d", "CARD_1_Play"),
        ScannedClip("Data/Win/a.unity3d", "VO_CARD_1_Male_Human_Trigger_01"),
        ScannedClip("Data/Win/a.unity3d", "VO_CARD_1_Male_Human_Play_01"),
    ]
    index = AudioIndex(
        store,
        cache_dir=tmp_path / "cache",
        scanner=lambda _install, _version: scanned,
        unity_version_detector=lambda _install: "6000.3.11f1",
    )

    index.start()
    assert index.wait(timeout=2)

    assert [clip.event_label for clip in index.clips_for_card("CARD_1")] == [
        "Play",
        "Play 2",
        "Trigger",
        "Trigger 2",
    ]


def test_event_clip_prefers_card_audio_then_falls_back_to_generic(
    tmp_path: Path,
) -> None:
    install = tmp_path / "Hearthstone"
    managers = install / "Hearthstone_Data" / "globalgamemanagers"
    managers.parent.mkdir(parents=True)
    managers.write_bytes(b"build")
    store = SettingsStore(tmp_path / "settings.json")
    store.set_hs_install_path(install)
    index = AudioIndex(
        store,
        cache_dir=tmp_path / "cache",
        scanner=lambda _install, _version: [
            ScannedClip("Data/Win/a.unity3d", "CARD_1_Play"),
            ScannedClip("Data/Win/b.unity3d", "play_card_from_hand_1"),
            ScannedClip("Data/Win/c.unity3d", "FX_Secret_Trigger"),
        ],
        unity_version_detector=lambda _install: "6000.3.11f1",
    )
    index.start()
    assert index.wait(timeout=2)

    assert index.event_clip("CARD_1", "play") == (
        "Data/Win/a.unity3d::CARD_1_Play"
    )
    assert index.event_clip("MISSING", "play") == (
        "Data/Win/b.unity3d::play_card_from_hand_1"
    )
    assert index.event_clip(None, "secret") == (
        "Data/Win/c.unity3d::FX_Secret_Trigger"
    )
    assert index.event_clip("CARD_1", "hero_power") is None


def test_per_build_json_cache_round_trip_skips_the_bundle_scan(
    tmp_path: Path,
) -> None:
    install = tmp_path / "Hearthstone"
    managers = install / "Hearthstone_Data" / "globalgamemanagers"
    managers.parent.mkdir(parents=True)
    managers.write_bytes(b"build-fingerprint")
    store = SettingsStore(tmp_path / "settings.json")
    store.set_hs_install_path(install)
    cache_dir = tmp_path / "cache"
    scan_calls = 0

    def scan(_install: Path, _version: str) -> list[ScannedClip]:
        nonlocal scan_calls
        scan_calls += 1
        return [ScannedClip("Data/Win/a.unity3d", "CARD_1_Death")]

    first = AudioIndex(
        store,
        cache_dir=cache_dir,
        scanner=scan,
        unity_version_detector=lambda _install: "6000.3.11f1",
    )
    first.start()
    assert first.wait(timeout=2)

    second = AudioIndex(
        store,
        cache_dir=cache_dir,
        scanner=scan,
        unity_version_detector=lambda _install: "6000.3.11f1",
    )
    second.start()
    assert second.wait(timeout=2)

    assert scan_calls == 1
    assert second.event_clip("CARD_1", "death") is not None
    assert [path.suffix for path in cache_dir.iterdir()] == [".json"]


def test_status_machine_distinguishes_absent_warming_and_ready(
    tmp_path: Path,
) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    absent = AudioIndex(
        store,
        cache_dir=tmp_path / "absent-cache",
        install_detector=lambda _custom: None,
    )
    absent.start()
    assert absent.status == "absent"
    assert absent.reason == (
        "Game audio is unavailable — no Hearthstone install found"
    )

    install = tmp_path / "Hearthstone"
    managers = install / "Hearthstone_Data" / "globalgamemanagers"
    managers.parent.mkdir(parents=True)
    managers.write_bytes(b"build")
    store.set_hs_install_path(install)
    entered = threading.Event()
    release = threading.Event()

    def blocking_scan(_install: Path, _version: str) -> list[ScannedClip]:
        entered.set()
        assert release.wait(timeout=2)
        return []

    warming = AudioIndex(
        store,
        cache_dir=tmp_path / "warming-cache",
        scanner=blocking_scan,
        unity_version_detector=lambda _install: "6000.3.11f1",
    )
    warming.start()
    assert entered.wait(timeout=2)
    assert warming.status == "indexing"
    assert warming.reason == "Game audio is not ready yet"

    release.set()
    assert warming.wait(timeout=2)
    assert warming.status == "ready"
