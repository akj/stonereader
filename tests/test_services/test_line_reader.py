"""Tests for _LineReader UTF-8 boundary handling."""

from __future__ import annotations

import pytest

pytest.importorskip("stonereader.services._line_reader")
from stonereader.services._line_reader import _LineReader


def test_returns_complete_lines():
    r = _LineReader()
    lines = r.feed(b"hello\nworld\n")
    assert lines == ["hello", "world"]


def test_buffers_partial_trailing_line():
    r = _LineReader()
    lines = r.feed(b"hello\npart")
    assert lines == ["hello"]
    lines = r.feed(b"ial\n")
    assert lines == ["partial"]


def test_handles_split_utf8_multibyte_at_chunk_boundary():
    # "Élise" — É is 0xC3 0x89 in UTF-8.  Split between the two bytes.
    r = _LineReader()
    first = r.feed(b"\xc3")  # incomplete sequence
    assert first == []
    second = r.feed(b"\x89lise\n")
    assert second == ["Élise"]


def test_strips_carriage_return():
    r = _LineReader()
    lines = r.feed(b"hello\r\nworld\r\n")
    assert lines == ["hello", "world"]


def test_reset_clears_partial_buffer():
    # Pitfall 8: stale partial must be dropped on file rotation.
    r = _LineReader()
    r.feed(b"hello\npart")
    r.reset()
    # After reset, "part" should be gone — feeding "ial" alone should NOT recover "partial"
    result = r.feed(b"ial\n")
    assert result == ["ial"]


def test_reset_clears_decoder_state():
    # An incomplete UTF-8 byte buffered before reset must NOT leak into post-reset decoding.
    r = _LineReader()
    r.feed(b"\xc3")  # buffered
    r.reset()
    # Feed a fresh ASCII line — must NOT contain a replacement char from leftover state
    result = r.feed(b"hi\n")
    assert result == ["hi"]
