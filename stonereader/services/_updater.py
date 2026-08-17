"""Background update checks and installer downloads (ADR-0016)."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


OWNER_REPO = "akj/stonereader"
_LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{OWNER_REPO}/releases/latest"
)
_REQUEST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "StoneReader",
}


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    installer_url: str
    installer_name: str


@dataclass(frozen=True)
class CheckResult:
    status: Literal["update", "up_to_date", "error", "unavailable"]
    info: UpdateInfo | None


def parse_version(tag: str) -> tuple[int, int, int] | None:
    """Parse an exact stable X.Y.Z release tag, with an optional v prefix."""
    candidate = tag[1:] if tag.startswith("v") else tag
    parts = candidate.split(".")
    if len(parts) != 3 or any(
        not part or any(character not in "0123456789" for character in part)
        for part in parts
    ):
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def select_installer_asset(assets: object) -> dict[str, object] | None:
    """Return the preferred installer asset from a release assets list."""
    if not isinstance(assets, list):
        return None
    executables: list[dict[str, object]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        if isinstance(name, str) and name.endswith(".exe"):
            executables.append(asset)
    return next(
        (
            asset
            for asset in executables
            if str(asset["name"]).endswith("-Setup.exe")
        ),
        executables[0] if executables else None,
    )


def _fetch_latest_release() -> dict[str, object]:
    request = urllib.request.Request(
        _LATEST_RELEASE_URL,
        headers=_REQUEST_HEADERS,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload: object = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("GitHub release response is not an object")
    return payload


def _download_file(url: str, path: Path) -> None:
    request = urllib.request.Request(url, headers=_REQUEST_HEADERS)
    part_path = Path(f"{path}.part")
    with (
        urllib.request.urlopen(request, timeout=10) as response,
        part_path.open("wb") as destination,
    ):
        shutil.copyfileobj(response, destination)
    part_path.replace(path)


def _launch_installer(path: Path) -> None:
    subprocess.Popen([str(path), "/SILENT"])


def _invoke(callback: Callable[[], None]) -> None:
    callback()


class UpdateChecker:
    """Check GitHub Releases and download an accepted update off the UI thread."""

    def __init__(
        self,
        current_version: str | None = None,
        *,
        fetch_release: Callable[[], dict[str, object]] = _fetch_latest_release,
        download_file: Callable[[str, Path], None] = _download_file,
        launch_installer: Callable[[Path], None] = _launch_installer,
        marshal: Callable[[Callable[[], None]], None] = _invoke,
    ) -> None:
        self._current_version = current_version
        self._fetch_release = fetch_release
        self._download_file = download_file
        self._launch_installer = launch_installer
        self._marshal = marshal
        self._lock = threading.Lock()
        self._checking = False
        self._downloading = False

    def check(self, on_result: Callable[[CheckResult], None]) -> None:
        """Check for an update without blocking the caller."""
        if self._current_version is None:
            self._deliver(lambda: on_result(CheckResult("unavailable", None)))
            return
        with self._lock:
            if self._checking:
                return
            self._checking = True
        threading.Thread(
            target=self._check,
            args=(on_result,),
            name="stonereader-update-check",
            daemon=True,
        ).start()

    def download_and_install(
        self,
        info: UpdateInfo,
        on_done: Callable[[bool], None],
    ) -> None:
        """Download and launch an installer without blocking the caller."""
        with self._lock:
            if self._downloading:
                return
            self._downloading = True
        threading.Thread(
            target=self._download_and_install,
            args=(info, on_done),
            name="stonereader-update-download",
            daemon=True,
        ).start()

    def _check(self, on_result: Callable[[CheckResult], None]) -> None:
        try:
            result = self._check_result()
        except Exception:
            logging.getLogger(__name__).exception("Update check failed")
            result = CheckResult("error", None)
        finally:
            with self._lock:
                self._checking = False
        self._deliver(lambda: on_result(result))

    def _check_result(self) -> CheckResult:
        current_text = self._current_version
        if current_text is None:
            return CheckResult("unavailable", None)
        current = parse_version(current_text)
        if current is None:
            raise ValueError(f"Invalid installed version: {current_text}")
        release = self._fetch_release()
        tag = release.get("tag_name")
        if not isinstance(tag, str):
            raise ValueError("GitHub release has no tag name")
        remote = parse_version(tag)
        if remote is None:
            raise ValueError(f"Invalid release tag: {tag}")
        asset = select_installer_asset(release.get("assets"))
        if asset is None:
            raise ValueError("GitHub release has no installer asset")
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(url, str):
            raise ValueError("GitHub installer asset is incomplete")
        if remote <= current:
            return CheckResult("up_to_date", None)
        version = tag[1:] if tag.startswith("v") else tag
        return CheckResult(
            "update",
            UpdateInfo(version, url, name),
        )

    def _download_and_install(
        self,
        info: UpdateInfo,
        on_done: Callable[[bool], None],
    ) -> None:
        success = False
        try:
            directory = Path(tempfile.mkdtemp(prefix="stonereader-update-"))
            installer = directory / Path(info.installer_name).name
            self._download_file(info.installer_url, installer)
            self._launch_installer(installer)
            success = True
        except Exception:
            logging.getLogger(__name__).exception(
                "Update download or installer launch failed"
            )
        finally:
            with self._lock:
                self._downloading = False
        self._deliver(lambda: on_done(success))

    def _deliver(self, callback: Callable[[], None]) -> None:
        try:
            self._marshal(callback)
        except Exception:
            logging.getLogger(__name__).exception("Update callback failed")
