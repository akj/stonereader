from __future__ import annotations

from pathlib import Path

import pytest

from stonereader.services._audio_index import AudioIndex
from stonereader.services._hs_install import detect_install
from stonereader.services._settings import SettingsStore


@pytest.mark.slow_audio
def test_real_install_indexes_and_decodes_a_known_voice_line(tmp_path: Path) -> None:
    install = detect_install()
    if install is None:
        pytest.skip("No local Hearthstone install detected")
    store = SettingsStore(tmp_path / "settings.json")
    store.set_hs_install_path(install)
    index = AudioIndex(store)

    index.start()
    assert index.wait(timeout=600), index.reason
    assert index.clip_count > 1000
    known_voice_lines = [
        clip
        for clip in index.clips_for_card("REV_956")
        if "VO_REV_956_" in clip.clip_key
    ]
    assert known_voice_lines
    assert index.decode(known_voice_lines[0].clip_key).startswith(b"RIFF")
