"""Asynchronous, single-clip game-audio playback."""

from __future__ import annotations

import io
import ctypes
import logging
import struct
import threading
import wave
from collections.abc import Callable
from typing import Any, Protocol


class AudioBackend(Protocol):
    """The tiny platform boundary used by the async player."""

    def play(self, wav_bytes: bytes) -> None: ...

    def stop(self) -> None: ...


class _PlaySound(Protocol):
    def __call__(self, sound: Any, module: None, flags: int) -> bool: ...


class WindowsMemoryBackend:
    """Asynchronous Win32 memory playback with owned buffer lifetime."""

    _SND_ASYNC = 0x0001
    _SND_NODEFAULT = 0x0002
    _SND_MEMORY = 0x0004

    def __init__(self, *, play_sound: _PlaySound | None = None) -> None:
        if play_sound is None:
            native = ctypes.WinDLL("winmm").PlaySoundW
            native.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
            native.restype = ctypes.c_bool
            play_sound = native
        self._play_sound = play_sound
        self._buffer: Any | None = None
        self._lock = threading.Lock()

    def play(self, wav_bytes: bytes) -> None:
        with self._lock:
            buffer = ctypes.create_string_buffer(wav_bytes)
            if not self._play_sound(
                ctypes.cast(buffer, ctypes.c_void_p),
                None,
                self._SND_ASYNC | self._SND_NODEFAULT | self._SND_MEMORY,
            ):
                raise RuntimeError("Windows PlaySoundW could not start game audio")
            # Win32 requires the memory image to remain valid until replacement
            # or stop. Keeping only the current buffer matches replace semantics.
            self._buffer = buffer

    def stop(self) -> None:
        with self._lock:
            self._play_sound(None, None, 0)
            self._buffer = None


class AudioPlayer:
    """Scale and start clips off the UI thread with replace semantics."""

    def __init__(
        self,
        backend: AudioBackend,
        volume_provider: Callable[[], int],
    ) -> None:
        self._backend = backend
        self._volume_provider = volume_provider
        self._lock = threading.Lock()
        self._generation = 0
        self._worker: threading.Thread | None = None

    def play(self, wav_bytes: bytes) -> None:
        """Scale and asynchronously start a clip, replacing any older request."""
        with self._lock:
            self._generation += 1
            generation = self._generation
            volume = self._volume_provider()
            worker = threading.Thread(
                target=self._play_worker,
                args=(generation, wav_bytes, volume),
                name="stonereader-audio-player",
                daemon=True,
            )
            self._worker = worker
        worker.start()

    def stop(self) -> None:
        """Cancel pending starts and stop current playback; safe when already idle."""
        with self._lock:
            self._generation += 1
        try:
            self._backend.stop()
        except Exception:
            logging.getLogger(__name__).exception("Game audio stop failed")

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the latest start request; primarily useful at test/smoke seams."""
        with self._lock:
            worker = self._worker
        if worker is None:
            return True
        worker.join(timeout)
        return not worker.is_alive()

    def _play_worker(self, generation: int, wav_bytes: bytes, volume: int) -> None:
        try:
            scaled = _scale_pcm16(wav_bytes, volume)
            with self._lock:
                if generation != self._generation:
                    return
                self._backend.play(scaled)
        except Exception:
            logging.getLogger(__name__).exception("Game audio playback failed")


def _scale_pcm16(wav_bytes: bytes, volume: int) -> bytes:
    if volume >= 100:
        return wav_bytes
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            params = reader.getparams()
            frames = reader.readframes(reader.getnframes())
    except (EOFError, wave.Error):
        return wav_bytes
    # The verified Hearthstone extraction currently yields 16-bit PCM WAVs.
    # Other payloads pass through at full volume rather than being corrupted.
    if params.sampwidth != 2:
        return wav_bytes
    sample_count = len(frames) // 2
    samples = struct.unpack(f"<{sample_count}h", frames)
    factor = min(max(volume, 0), 100) / 100
    scaled = tuple(
        min(32767, max(-32768, int(sample * factor))) for sample in samples
    )
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams(params)
        writer.writeframes(struct.pack(f"<{sample_count}h", *scaled))
    return output.getvalue()
