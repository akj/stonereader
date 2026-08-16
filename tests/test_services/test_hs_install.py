from __future__ import annotations

from pathlib import Path

from stonereader.services._hs_install import detect_install


def test_existing_custom_path_wins(tmp_path: Path, monkeypatch) -> None:
    custom = tmp_path / "custom"
    standard_root = tmp_path / "programs"
    custom.mkdir()
    (standard_root / "Hearthstone").mkdir(parents=True)
    monkeypatch.setenv("ProgramFiles", str(standard_root))

    assert detect_install(custom) == custom


def test_standard_paths_and_missing_install(tmp_path: Path, monkeypatch) -> None:
    x86 = tmp_path / "x86"
    install = x86 / "Hearthstone"
    install.mkdir(parents=True)
    monkeypatch.setenv("ProgramFiles(x86)", str(x86))
    monkeypatch.delenv("ProgramFiles", raising=False)
    assert detect_install() == install

    install.rmdir()
    assert detect_install() is None
