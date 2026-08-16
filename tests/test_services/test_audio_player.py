from __future__ import annotations

import io
import struct
import wave

import ctypes

from stonereader.services._audio_player import AudioPlayer, WindowsMemoryBackend


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes | None]] = []

    def play(self, wav_bytes: bytes) -> None:
        self.calls.append(("play", wav_bytes))

    def stop(self) -> None:
        self.calls.append(("stop", None))


def _pcm16_wav(samples: tuple[int, ...]) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


def _samples(wav_bytes: bytes) -> tuple[int, ...]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        frames = reader.readframes(reader.getnframes())
    return struct.unpack(f"<{len(frames) // 2}h", frames)


def test_player_scales_pcm16_at_the_next_play_boundary() -> None:
    backend = FakeBackend()
    volume = 50
    player = AudioPlayer(backend, lambda: volume)

    player.play(_pcm16_wav((-32768, -10000, 10000, 32767)))
    assert player.wait(timeout=2)

    assert _samples(backend.calls[-1][1] or b"") == (
        -16384,
        -5000,
        5000,
        16383,
    )


def test_new_play_replaces_and_stop_is_safe_to_repeat() -> None:
    backend = FakeBackend()
    player = AudioPlayer(backend, lambda: 100)
    first = _pcm16_wav((1000,))
    second = _pcm16_wav((2000,))

    player.play(first)
    assert player.wait(timeout=2)
    player.play(second)
    assert player.wait(timeout=2)
    player.stop()
    player.stop()

    assert backend.calls == [
        ("play", first),
        ("play", second),
        ("stop", None),
        ("stop", None),
    ]


def test_windows_backend_keeps_memory_async_and_stops_with_null_pointer() -> None:
    calls: list[tuple[bytes | None, int]] = []

    def play_sound(sound, _module, flags: int) -> bool:
        calls.append(
            (
                None if sound is None else ctypes.string_at(sound, 4),
                flags,
            )
        )
        return True

    backend = WindowsMemoryBackend(play_sound=play_sound)
    backend.play(b"RIFFpayload")
    backend.stop()

    assert calls == [(b"RIFF", 0x0001 | 0x0002 | 0x0004), (None, 0)]
