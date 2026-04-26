"""Tests for stonereader.services._log_config."""

from __future__ import annotations

import configparser

import pytest


def test_creates_file_when_absent(tmp_path):
    from stonereader.services._log_config import (
        REQUIRED_POWER_SECTION,
        ensure_log_config,
    )

    path = tmp_path / "Blizzard" / "Hearthstone" / "log.config"
    result = ensure_log_config(path)

    assert result is True
    assert path.exists()

    parser = configparser.RawConfigParser()
    parser.optionxform = str  # type: ignore[assignment]
    parser.read(path, encoding="utf-8")
    assert parser.has_section("Power")
    for key, value in REQUIRED_POWER_SECTION.items():
        assert parser.get("Power", key) == value


def test_preserves_other_sections(tmp_path):
    """Pitfall 5: other tools' sections (HDT, Firestone) must survive."""
    from stonereader.services._log_config import ensure_log_config

    path = tmp_path / "log.config"
    path.write_text(
        "[Achievements]\n"
        "LogLevel=1\n"
        "FilePrinting=True\n"
        "\n"
        "[FullScreenFX]\n"
        "LogLevel=1\n",
        encoding="utf-8",
    )

    ensure_log_config(path)
    content = path.read_text(encoding="utf-8")

    assert "[Achievements]" in content
    assert "[FullScreenFX]" in content
    assert "[Power]" in content


def test_idempotent_when_correct(tmp_path):
    from stonereader.services._log_config import ensure_log_config

    path = tmp_path / "log.config"

    first = ensure_log_config(path)
    assert first is True

    second = ensure_log_config(path)
    assert second is False  # no change on second call


def test_log_config_path_uses_localappdata(monkeypatch, tmp_path):
    """log_config_path() resolves under %LOCALAPPDATA%\\Blizzard\\Hearthstone."""
    from stonereader.services._log_config import log_config_path

    fake_appdata = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(fake_appdata))

    path = log_config_path()
    assert path.parent.name == "Hearthstone"
    assert path.parent.parent.name == "Blizzard"
    assert path.name == "log.config"
    assert str(path).startswith(str(fake_appdata))
