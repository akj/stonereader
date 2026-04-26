"""UTF-8 boundary-safe line splitter for byte streams.

Buffers partial multi-byte sequences across chunk boundaries (Pitfall 8).
"""

from __future__ import annotations

import codecs
from typing import List


class _LineReader:
    """Stateful chunk-to-lines converter.

    Usage:
        reader = _LineReader()
        for chunk in stream_of_bytes:
            for line in reader.feed(chunk):
                handle(line)
        reader.reset()  # on file rotation
    """

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._partial = ""

    def feed(self, chunk: bytes) -> List[str]:
        """Feed raw bytes; return zero or more complete lines (no trailing \\n)."""
        text = self._decoder.decode(chunk, final=False)
        text = self._partial + text
        if "\n" not in text:
            self._partial = text
            return []
        *lines, self._partial = text.split("\n")
        # Strip Windows trailing \r
        return [line.rstrip("\r") for line in lines]

    def reset(self) -> None:
        """Drop decoder state AND partial buffer (Pitfall 8)."""
        self._decoder.reset()
        self._partial = ""
