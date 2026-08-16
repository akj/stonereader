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
        "[Achievements]\nLogLevel=1\nFilePrinting=True\n\n[FullScreenFX]\nLogLevel=1\n",
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


def test_raises_services_error_on_write_failure(tmp_path):
    """ensure_log_config raises ServicesError (not bare OSError) on write failure."""
    from unittest.mock import patch

    from stonereader.services._exceptions import ServicesError
    from stonereader.services._log_config import ensure_log_config

    path = tmp_path / "log.config"

    # Patch Path.open on the specific module so only the write call fails.
    # pathlib.Path.open is what _log_config.py calls — not builtins.open.
    original_open = path.__class__.open

    def failing_open(self, mode="r", **kwargs):
        if "w" in mode:
            raise PermissionError("read-only filesystem")
        return original_open(self, mode, **kwargs)

    with patch.object(path.__class__, "open", failing_open):
        with pytest.raises(ServicesError, match="Cannot write log.config"):
            ensure_log_config(path)


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
