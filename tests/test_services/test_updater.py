from __future__ import annotations

import threading
from pathlib import Path

import pytest

from stonereader.services._updater import (
    CheckResult,
    UpdateChecker,
    UpdateInfo,
    parse_version,
    select_installer_asset,
)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.2.3", (1, 2, 3)),
        ("1.2.3", (1, 2, 3)),
        ("v01.002.0003", (1, 2, 3)),
        ("v1.2.3-beta", None),
        ("1.2", None),
        ("1.2.3.4", None),
        ("version-1.2.3", None),
        ("v1.two.3", None),
        ("", None),
    ],
)
def test_parse_version_accepts_only_complete_stable_versions(
    tag: str,
    expected: tuple[int, int, int] | None,
) -> None:
    assert parse_version(tag) == expected


def test_installer_asset_prefers_setup_executable_then_any_executable() -> None:
    fallback = {
        "name": "StoneReader-portable.exe",
        "browser_download_url": "https://example.test/portable.exe",
    }
    setup = {
        "name": "StoneReader-1.2.3-Setup.exe",
        "browser_download_url": "https://example.test/setup.exe",
    }

    assert select_installer_asset([fallback, setup]) == setup
    assert select_installer_asset([fallback]) == fallback
    assert select_installer_asset([{"name": "checksums.txt"}]) is None


def _release(
    tag: str = "v1.2.3",
    *,
    assets: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "tag_name": tag,
        "assets": assets
        if assets is not None
        else [
            {
                "name": "StoneReader-1.2.3-Setup.exe",
                "browser_download_url": "https://example.test/setup.exe",
            }
        ],
    }


def _check(checker: UpdateChecker) -> CheckResult:
    finished = threading.Event()
    results: list[CheckResult] = []

    def on_result(result: CheckResult) -> None:
        results.append(result)
        finished.set()

    checker.check(on_result)
    assert finished.wait(timeout=2)
    assert len(results) == 1
    return results[0]


def test_check_reports_a_strictly_newer_release() -> None:
    checker = UpdateChecker("1.2.2", fetch_release=_release)

    assert _check(checker) == CheckResult(
        "update",
        UpdateInfo(
            version="1.2.3",
            installer_url="https://example.test/setup.exe",
            installer_name="StoneReader-1.2.3-Setup.exe",
        ),
    )


@pytest.mark.parametrize("current", ["1.2.4", "1.2.3"])
def test_check_reports_up_to_date_for_older_or_equal_release(
    current: str,
) -> None:
    checker = UpdateChecker(current, fetch_release=_release)

    assert _check(checker) == CheckResult("up_to_date", None)


def test_check_reports_error_for_an_invalid_release_tag() -> None:
    checker = UpdateChecker(
        "1.2.2",
        fetch_release=lambda: _release("v1.2.3-beta"),
    )

    assert _check(checker) == CheckResult("error", None)


def test_check_reports_error_when_fetching_fails() -> None:
    def fail() -> dict[str, object]:
        raise OSError("offline")

    checker = UpdateChecker("1.2.2", fetch_release=fail)

    assert _check(checker) == CheckResult("error", None)


def test_check_is_unavailable_without_a_current_version_and_stays_sync() -> None:
    fetch_calls = 0
    callback_thread: list[int] = []
    caller_thread = threading.get_ident()

    def fetch() -> dict[str, object]:
        nonlocal fetch_calls
        fetch_calls += 1
        return _release()

    checker = UpdateChecker(None, fetch_release=fetch)
    checker.check(
        lambda result: callback_thread.append(threading.get_ident())
        if result == CheckResult("unavailable", None)
        else None
    )

    assert fetch_calls == 0
    assert callback_thread == [caller_thread]


def test_download_and_install_launches_downloaded_asset_and_reports_success() -> None:
    downloaded: list[tuple[str, Path]] = []
    launched: list[Path] = []
    results: list[bool] = []
    finished = threading.Event()

    def download(url: str, path: Path) -> None:
        downloaded.append((url, path))
        path.write_bytes(b"installer")

    def on_done(success: bool) -> None:
        results.append(success)
        finished.set()

    checker = UpdateChecker(
        "1.2.2",
        download_file=download,
        launch_installer=launched.append,
    )
    info = UpdateInfo(
        "1.2.3",
        "https://example.test/setup.exe",
        "StoneReader-1.2.3-Setup.exe",
    )

    checker.download_and_install(info, on_done)

    assert finished.wait(timeout=2)
    assert results == [True]
    assert downloaded[0][0] == info.installer_url
    assert downloaded[0][1].name == info.installer_name
    assert downloaded[0][1].parent.name.startswith("stonereader-update-")
    assert launched == [downloaded[0][1]]


def test_download_failure_reports_false_without_launching() -> None:
    launched: list[Path] = []
    results: list[bool] = []
    finished = threading.Event()

    def fail(_url: str, _path: Path) -> None:
        raise OSError("download failed")

    def on_done(success: bool) -> None:
        results.append(success)
        finished.set()

    checker = UpdateChecker(
        "1.2.2",
        download_file=fail,
        launch_installer=launched.append,
    )

    checker.download_and_install(
        UpdateInfo("1.2.3", "https://example.test/setup.exe", "setup.exe"),
        on_done,
    )

    assert finished.wait(timeout=2)
    assert results == [False]
    assert launched == []


def test_reentrant_check_is_dropped_while_the_first_is_in_flight() -> None:
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    fetch_calls = 0
    first_results: list[CheckResult] = []
    second_results: list[CheckResult] = []

    def fetch() -> dict[str, object]:
        nonlocal fetch_calls
        fetch_calls += 1
        entered.set()
        assert release.wait(timeout=2)
        return _release()

    checker = UpdateChecker("1.2.2", fetch_release=fetch)

    def first_done(result: CheckResult) -> None:
        first_results.append(result)
        finished.set()

    checker.check(first_done)
    assert entered.wait(timeout=2)
    checker.check(second_results.append)
    release.set()

    assert finished.wait(timeout=2)
    assert fetch_calls == 1
    assert len(first_results) == 1
    assert second_results == []
