"""Tests for stonereader.services._logging_config."""

from __future__ import annotations

import logging

import pytest


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Snapshot and restore root logger handlers/level around each test.

    configure_logging() mutates the root logger globally; without a snapshot
    handlers leak between tests in the same process (and pollute pytest's
    own logging plumbing).
    """
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


def test_creates_log_dir_and_file(tmp_path, monkeypatch):
    from stonereader.services import _logging_config

    monkeypatch.delenv("STONEREADER_DEBUG", raising=False)
    target_dir = tmp_path / ".stonereader"
    monkeypatch.setattr(_logging_config, "LOG_DIR", target_dir)

    _logging_config.configure_logging()

    assert target_dir.exists()
    assert target_dir.is_dir()
    log_file = target_dir / _logging_config.LOG_FILE_NAME
    assert log_file.exists()  # RotatingFileHandler creates the file at construction


def test_idempotent_when_called_twice(tmp_path, monkeypatch):
    from stonereader.services import _logging_config

    monkeypatch.delenv("STONEREADER_DEBUG", raising=False)
    target_dir = tmp_path / ".stonereader"
    monkeypatch.setattr(_logging_config, "LOG_DIR", target_dir)

    _logging_config.configure_logging()
    handler_count_after_first = len(logging.getLogger().handlers)

    _logging_config.configure_logging()
    handler_count_after_second = len(logging.getLogger().handlers)

    assert handler_count_after_first == handler_count_after_second
    # Sanity: there should be at least the file + console handlers.
    assert handler_count_after_first >= 2


def test_debug_env_enables_debug_level(tmp_path, monkeypatch):
    from stonereader.services import _logging_config

    target_dir = tmp_path / ".stonereader"
    monkeypatch.setattr(_logging_config, "LOG_DIR", target_dir)

    monkeypatch.setenv("STONEREADER_DEBUG", "1")
    _logging_config.configure_logging()
    assert logging.getLogger().level == logging.DEBUG

    # Reset and verify INFO when env flag is absent.
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.WARNING)

    monkeypatch.delenv("STONEREADER_DEBUG", raising=False)
    _logging_config.configure_logging()
    assert logging.getLogger().level == logging.INFO
