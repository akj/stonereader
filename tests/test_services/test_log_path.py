"""Tests for stonereader.services._log_path."""
from __future__ import annotations
import pytest


def test_picks_newest_subdirectory_by_mtime(tmp_path):
    pytest.importorskip("stonereader.services._log_path")
    pytest.skip("stub — implemented in Wave 1 Plan 03 Task 1")


def test_falls_back_to_flat_path(tmp_path):
    pytest.importorskip("stonereader.services._log_path")
    pytest.skip("stub — implemented in Wave 1 Plan 03 Task 1")


def test_returns_none_when_not_found(tmp_path):
    pytest.importorskip("stonereader.services._log_path")
    pytest.skip("stub — implemented in Wave 1 Plan 03 Task 1")
