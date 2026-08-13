"""Tests for best-effort Hearthstone build-number discovery."""

from pathlib import Path

from stonereader.services._build_info import read_build


def test_read_build_finds_install_root_build_info(tmp_path: Path) -> None:
    build_info = tmp_path / ".build.info"
    build_info.write_text(
        "BranchName!STRING:0|BuildId!STRING:0|ProductCode!STRING:0\n"
        "stable|240397|WTCG\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "Logs" / "Hearthstone_2026_08_12" / "Power.log"

    assert read_build(log_path) == 240397


def test_read_build_returns_none_when_build_info_is_missing(tmp_path: Path) -> None:
    log_path = tmp_path / "Logs" / "session" / "Power.log"

    assert read_build(log_path) is None


def test_read_build_returns_none_for_malformed_build_info(tmp_path: Path) -> None:
    (tmp_path / ".build.info").write_text(
        "BranchName!STRING:0|ProductCode!STRING:0\nstable|WTCG\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "Logs" / "session" / "Power.log"

    assert read_build(log_path) is None
