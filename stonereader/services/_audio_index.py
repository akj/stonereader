"""Runtime-only index of Hearthstone's locally installed game audio."""

from __future__ import annotations

import re
import logging
import threading
import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from stonereader.services._hs_install import detect_install
from stonereader.services._settings import SettingsStore


_ABSENT_REASON = "Game audio is unavailable — no Hearthstone install found"
# UI-spec ruling: warming is distinct from the install-absent state.
_INDEXING_REASON = "Game audio is not ready yet"


@dataclass(frozen=True)
class ParsedClip:
    """The card event or generic replay-event family encoded in a clip name."""

    card_id: str | None = None
    event: str | None = None
    generic_kind: str | None = None


@dataclass(frozen=True)
class ScannedClip:
    """Name-only result returned by the local Unity bundle boundary."""

    bundle_path: str
    name: str


@dataclass(frozen=True)
class CardClip:
    """One user-facing card sound option and its opaque decode key."""

    event_label: str
    clip_key: str


_VO_NAME = re.compile(
    r"^VO_(?P<body>.+)_(?P<event>[A-Za-z][A-Za-z0-9]*)_(?P<number>\d+)$"
)
_VO_METADATA = re.compile(r"_(?:Male|Female|Neutral|Unknown|X|x)_")
_FOLEY_NAME = re.compile(r"^(?P<card_id>.+)_(?P<event>Play|Attack|Death)$")

_GENERIC_NAMES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^ALERT_YourTurn_0v2$", re.IGNORECASE), "turn"),
    (re.compile(r"^(?:draw_card_[1-3]|draw_card_and_add_to_hand_opp_[1-3])$", re.IGNORECASE), "draw"),
    (re.compile(r"^(?:play_card_from_hand_[1-3]|Minion_Drop_Basic_[1-5])$", re.IGNORECASE), "play"),
    (re.compile(r"^(?:FX_Minion_AttackLaunch|FX_Minion_AttackImpact(?:Mid|Large)?|Hero_Attack_Generic_(?:Start|End)_01)$", re.IGNORECASE), "attack"),
    (re.compile(r"^Minion_Death_0[1-6]$", re.IGNORECASE), "minion_death"),
    (re.compile(r"^(?:Mulligan[ABC]?|FX_MulliganCoin01_HeroCoinDrop)$", re.IGNORECASE), "mulligan"),
    (re.compile(r"^the_coin_card$", re.IGNORECASE), "coin"),
    (re.compile(r"^(?:victory_jingle|victory_screen_start)$", re.IGNORECASE), "victory"),
    (re.compile(r"^(?:defeat_jingle|defeat_screen_start)$", re.IGNORECASE), "defeat"),
    (re.compile(r"^FX_Secret_(?:Trigger|Birth)$", re.IGNORECASE), "secret"),
)


def parse_clip_name(name: str) -> ParsedClip | None:
    """Classify the two card-name families and the canonical generic SFX."""
    vo_match = _VO_NAME.fullmatch(name)
    if vo_match is not None:
        card_id = _VO_METADATA.split(vo_match.group("body"), maxsplit=1)[0]
        if not card_id:
            return None
        return ParsedClip(
            card_id=card_id,
            event=vo_match.group("event"),
        )
    foley_match = _FOLEY_NAME.fullmatch(name)
    if foley_match is not None:
        return ParsedClip(
            card_id=foley_match.group("card_id"),
            event=foley_match.group("event"),
        )
    for pattern, kind in _GENERIC_NAMES:
        if pattern.fullmatch(name):
            return ParsedClip(generic_kind=kind)
    return None


class AudioIndex:
    """Build and expose a thread-safe name index over the local install."""

    def __init__(
        self,
        settings: SettingsStore,
        *,
        cache_dir: Path = Path.home() / ".stonereader",
        install_detector: Callable[[Path | None], Path | None] = detect_install,
        scanner: Callable[[Path, str], Iterable[ScannedClip]] | None = None,
        unity_version_detector: Callable[[Path], str] | None = None,
    ) -> None:
        self._settings = settings
        self._cache_dir = cache_dir
        self._install_detector = install_detector
        self._scanner = scanner or _scan_install
        self._unity_version_detector = (
            unity_version_detector or _detect_unity_version
        )
        self._lock = threading.Lock()
        self._finished = threading.Event()
        self._status = "absent"
        self._reason = _ABSENT_REASON
        self._install: Path | None = None
        self._unity_version = ""
        self._clip_count = 0
        self._card_clips: dict[str, tuple[CardClip, ...]] = {}
        self._card_events: dict[str, dict[str, tuple[str, ...]]] = {}
        self._generic_clips: dict[str, tuple[str, ...]] = {}

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    @property
    def clip_count(self) -> int:
        """Return the full AudioClip corpus size once the index is ready."""
        with self._lock:
            return self._clip_count if self._status == "ready" else 0

    def start(self) -> None:
        """Start a cache load or full-corpus scan without blocking the UI."""
        custom_path = self._settings.hs_install_path
        install = (
            custom_path
            if custom_path is not None and custom_path.exists()
            else (
                None
                if custom_path is not None
                else self._install_detector(None)
            )
        )
        if install is None:
            with self._lock:
                self._set_absent(_ABSENT_REASON)
            self._finished.set()
            return
        with self._lock:
            if self._status == "indexing":
                return
            self._status = "indexing"
            self._reason = _INDEXING_REASON
            self._install = install
            self._card_clips = {}
            self._card_events = {}
            self._generic_clips = {}
            self._clip_count = 0
            self._finished.clear()
        threading.Thread(
            target=self._build,
            args=(install,),
            name="stonereader-audio-index",
            daemon=True,
        ).start()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for background indexing and report whether the channel is ready."""
        self._finished.wait(timeout)
        return self.status == "ready"

    def clips_for_card(self, card_id: str) -> list[CardClip]:
        with self._lock:
            if self._status != "ready":
                return []
            return list(self._card_clips.get(card_id, ()))

    def event_clip(self, card_id: str | None, kind: str) -> str | None:
        """Return card-specific audio first, then the canonical generic SFX."""
        event_names = {
            "play": ("play",),
            "attack": ("attack",),
            "death": ("death",),
            "minion_death": ("death",),
            "draw": ("draw",),
            "turn": ("turn",),
            "secret": ("secret", "trigger"),
            "victory": ("victory",),
            "defeat": ("defeat",),
        }.get(kind)
        if event_names is None:
            return None
        with self._lock:
            if self._status != "ready":
                return None
            if card_id is not None:
                events = self._card_events.get(card_id, {})
                for event_name in event_names:
                    values = events.get(event_name)
                    if values:
                        return values[0]
            generic = self._generic_clips.get(kind)
            return generic[0] if generic else None

    def decode(self, clip_key: str) -> bytes:
        """Decode one indexed local AudioClip to WAV without persisting it."""
        with self._lock:
            if self._status != "ready" or self._install is None:
                return b""
            install = self._install
            unity_version = self._unity_version
        try:
            scanned = _scanned_clip_from_key(clip_key)
            return _decode_clip(install, unity_version, scanned)
        except Exception:
            logging.getLogger(__name__).exception(
                "Game audio decode failed; disabling the channel"
            )
            with self._lock:
                self._set_absent("Game audio is unavailable")
            return b""

    def _build(self, install: Path) -> None:
        try:
            fingerprint = _build_fingerprint(install)
            cache_path = self._cache_dir / f"audio_index_{fingerprint}.json"
            version = self._unity_version_detector(install)
            scanned = _load_cache(cache_path, fingerprint)
            if scanned is None:
                scanned = list(self._scanner(install, version))
                _write_cache(cache_path, fingerprint, scanned)
            card_clips, card_events, generic_clips = _build_query_index(scanned)
            with self._lock:
                self._card_clips = card_clips
                self._card_events = card_events
                self._generic_clips = generic_clips
                self._unity_version = version
                self._clip_count = len(scanned)
                self._status = "ready"
                self._reason = ""
        except Exception:
            logging.getLogger(__name__).exception(
                "Game audio indexing failed; disabling the channel"
            )
            with self._lock:
                self._set_absent("Game audio is unavailable")
        finally:
            self._finished.set()

    def _set_absent(self, reason: str) -> None:
        self._status = "absent"
        self._reason = reason
        self._card_clips = {}
        self._card_events = {}
        self._generic_clips = {}
        self._unity_version = ""
        self._clip_count = 0


def _build_query_index(
    scanned: Iterable[ScannedClip],
) -> tuple[
    dict[str, tuple[CardClip, ...]],
    dict[str, dict[str, tuple[str, ...]]],
    dict[str, tuple[str, ...]],
]:
    by_card: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    generic: dict[str, list[str]] = defaultdict(list)
    for clip in scanned:
        parsed = parse_clip_name(clip.name)
        if parsed is None:
            continue
        key = _clip_key(clip.bundle_path, clip.name)
        if parsed.card_id is not None and parsed.event is not None:
            by_card[parsed.card_id].append((parsed.event, clip.name, key))
        elif parsed.generic_kind is not None:
            generic[parsed.generic_kind].append(key)

    ready_cards: dict[str, tuple[CardClip, ...]] = {}
    ready_events: dict[str, dict[str, tuple[str, ...]]] = {}
    for card_id, values in by_card.items():
        values.sort(key=lambda value: (_event_sort_key(value[0]), value[1]))
        counts: dict[str, int] = defaultdict(int)
        event_keys: dict[str, list[str]] = defaultdict(list)
        clips: list[CardClip] = []
        for event, _name, key in values:
            label = _humanize_event(event)
            counts[label] += 1
            event_keys[event.casefold()].append(key)
            number = counts[label]
            clips.append(
                CardClip(
                    label if number == 1 else f"{label} {number}",
                    key,
                )
            )
        ready_cards[card_id] = tuple(clips)
        ready_events[card_id] = {
            event: tuple(keys) for event, keys in event_keys.items()
        }
    return ready_cards, ready_events, {
        kind: tuple(sorted(keys, key=lambda key: _generic_sort_key(kind, key)))
        for kind, keys in generic.items()
    }


def _humanize_event(event: str) -> str:
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", event.replace("_", " "))
    return words.strip().title()


def _event_sort_key(event: str) -> tuple[int, str]:
    preferred = {"Play": 0, "Attack": 1, "Death": 2, "Trigger": 3}
    return preferred.get(event, 100), event.casefold()


def _generic_sort_key(kind: str, clip_key: str) -> tuple[int, str]:
    name = clip_key.partition("::")[2]
    preferred = {
        "turn": ("ALERT_YourTurn_0v2",),
        "draw": ("draw_card_1",),
        "play": ("play_card_from_hand_1",),
        "attack": ("FX_Minion_AttackLaunch",),
        "minion_death": ("Minion_Death_01",),
        "victory": ("victory_jingle",),
        "defeat": ("defeat_jingle",),
        "secret": ("FX_Secret_Trigger",),
    }.get(kind, ())
    try:
        priority = preferred.index(name)
    except ValueError:
        priority = len(preferred)
    return priority, name.casefold()


def _clip_key(bundle_path: str, name: str) -> str:
    return f"{bundle_path}::{name}"


def _scanned_clip_from_key(clip_key: str) -> ScannedClip:
    bundle_path, separator, name = clip_key.partition("::")
    if not separator or not bundle_path or not name:
        raise ValueError("Invalid game-audio clip key")
    return ScannedClip(bundle_path, name)


def _build_fingerprint(install: Path) -> str:
    """Hash globalgamemanagers because its bytes change with each client build."""
    managers = install / "Hearthstone_Data" / "globalgamemanagers"
    digest = hashlib.sha256()
    with managers.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _load_cache(path: Path, fingerprint: str) -> list[ScannedClip] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema") != 1 or raw.get("build") != fingerprint:
            return None
        clips = raw["clips"]
        if not isinstance(clips, list):
            return None
        return [
            ScannedClip(bundle_path=item["bundle"], name=item["name"])
            for item in clips
            if isinstance(item, dict)
            and isinstance(item.get("bundle"), str)
            and isinstance(item.get("name"), str)
        ]
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError):
        logging.getLogger(__name__).warning(
            "Ignoring unreadable game-audio index cache: %s", path
        )
        return None


def _write_cache(
    path: Path,
    fingerprint: str,
    clips: Iterable[ScannedClip],
) -> None:
    # Only bundle-relative paths and clip names are persisted. Decoded Blizzard
    # audio is deliberately never written to disk (ADR-0008 bright line).
    payload = {
        "schema": 1,
        "build": fingerprint,
        "clips": [
            {"bundle": clip.bundle_path, "name": clip.name} for clip in clips
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )


def _detect_unity_version(install: Path) -> str:
    import UnityPy
    import UnityPy.config as unity_config

    managers = install / "Hearthstone_Data" / "globalgamemanagers"
    environment = UnityPy.load(str(managers))
    if not environment.assets:
        raise ValueError("globalgamemanagers contains no serialized assets")
    version = str(environment.assets[0].unity_version)
    if not version:
        raise ValueError("Could not detect the Hearthstone Unity version")
    # Blizzard strips bundle version headers. The version recovered from
    # globalgamemanagers is therefore the required fallback for every bundle.
    unity_config.FALLBACK_UNITY_VERSION = version
    return version


def _scan_install(install: Path, unity_version: str) -> Iterable[ScannedClip]:
    import UnityPy
    import UnityPy.config as unity_config

    unity_config.FALLBACK_UNITY_VERSION = unity_version
    data_win = install / "Data" / "Win"
    # This must be the full corpus: generic event SFX live outside bundles
    # whose filenames look sound-related (research finding 9).
    for bundle_path in sorted(data_win.rglob("*.unity3d")):
        environment = UnityPy.load(str(bundle_path))
        relative = bundle_path.relative_to(install).as_posix()
        for obj in environment.objects:
            if obj.type.name != "AudioClip":
                continue
            clip = obj.read()
            name = getattr(clip, "m_Name", "")
            if isinstance(name, str) and name:
                yield ScannedClip(relative, name)


def _decode_clip(
    install: Path,
    unity_version: str,
    scanned: ScannedClip,
) -> bytes:
    import UnityPy
    import UnityPy.config as unity_config
    import fsb5
    from UnityPy.helpers.ResourceReader import get_resource_data

    unity_config.FALLBACK_UNITY_VERSION = unity_version
    data_win = (install / "Data" / "Win").resolve()
    bundle_path = (install / Path(scanned.bundle_path)).resolve()
    if not bundle_path.is_relative_to(data_win):
        raise ValueError("Game-audio cache points outside Data/Win")
    environment = UnityPy.load(str(bundle_path))
    for obj in environment.objects:
        if obj.type.name != "AudioClip":
            continue
        audio = obj.read()
        if getattr(audio, "m_Name", "") != scanned.name:
            continue
        embedded = getattr(audio, "m_AudioData", None)
        if embedded:
            audio_data = bytes(embedded)
        else:
            resource = getattr(audio, "m_Resource", None)
            if resource is None or not getattr(resource, "m_Source", ""):
                raise ValueError("AudioClip has no embedded or external audio data")
            if audio.object_reader is None:
                raise ValueError("AudioClip has no object reader")
            audio_data = get_resource_data(
                resource.m_Source,
                audio.object_reader.assets_file,
                resource.m_Offset,
                resource.m_Size,
            )
        archive = fsb5.load(audio_data)
        if not archive.samples:
            raise ValueError("AudioClip FSB5 archive has no samples")
        sample = archive.samples[0]
        try:
            rebuilt = bytes(archive.rebuild_sample(sample))
        except OSError:
            # fsb5's Windows wheel does not bundle the native Vorbis/Ogg DLLs.
            # UnityPy already installs fmod-toolkit with a bundled FMOD decoder,
            # so retain fsb5 parsing/rebuild as the primary path and use that
            # local, in-memory decoder when the native rebuild library is absent.
            rebuilt = audio_data
        if rebuilt.startswith(b"RIFF"):
            return rebuilt
        # UnityPy's public AudioClip converter uses its bundled local FMOD
        # decoder for the FSB/Ogg payload; it returns in-memory WAV samples.
        wav_samples = audio.samples
        if not wav_samples:
            raise ValueError("AudioClip decoder returned no WAV samples")
        return next(iter(wav_samples.values()))
    raise KeyError(f"AudioClip disappeared from bundle: {scanned.name}")
