"""Tests für AppUpdater.check() und den GitHub-Adapter (kein echtes Netz)."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error

import pytest

from fritz_callhistory.app_update import (
    AppUpdater,
    GitHubReleaseSource,
    ReleaseAvailable,
    ReleaseInfo,
    UpdateError,
    UpToDate,
)

LINUX_FILE = "fritz-callhistory-linux-x86_64"
WINDOWS_FILE = "fritz-callhistory-windows-x86_64.exe"


class FakeSource:
    def __init__(self, tag="v1.2.0", files=None, error=None):
        self._release = ReleaseInfo(
            tag=tag,
            notes="Neu: Dinge",
            page_url="https://example.test/release",
            files={LINUX_FILE: "u1", WINDOWS_FILE: "u2"} if files is None else files,
        )
        self._error = error

    def latest_release(self):
        if self._error:
            raise self._error
        return self._release

    def open_download(self, url):
        self.opened = getattr(self, "opened", []) + [url]
        data = self.blobs[url]
        return io.BytesIO(data), len(data)


def _updater(tmp_path, source=None, installed="1.1.0", frozen=True, platform="linux"):
    return AppUpdater(
        source or FakeSource(),
        installed,
        tmp_path / "fritz-callhistory",
        frozen=frozen,
        platform=platform,
    )


@pytest.mark.parametrize(
    ("tag", "installed", "newer"),
    [
        ("v1.2.0", "1.1.0", True),
        ("1.2.0", "1.1.0", True),
        ("v1.1.0", "1.1.0", False),
        ("v1.0.0", "1.1.0", False),
        ("v1.1.0", "1.1.0.dev3+gabc123", True),  # Dev-Build liegt vor dem Release
        ("v1.1.0", "1.2.0.dev3+gabc123", False),
    ],
)
def test_only_strictly_newer_release_is_offered(tmp_path, tag, installed, newer):
    result = _updater(tmp_path, FakeSource(tag=tag), installed=installed).check()

    assert isinstance(result, ReleaseAvailable) is newer
    if not newer:
        assert result == UpToDate(installed)


def test_available_release_carries_versions_notes_and_page(tmp_path):
    result = _updater(tmp_path).check()

    assert result.version == "1.2.0"
    assert result.installed == "1.1.0"
    assert result.notes == "Neu: Dinge"
    assert result.page_url == "https://example.test/release"
    assert result.can_self_update is True
    assert result.fallback_reason is None


def test_unparseable_tag_is_an_error(tmp_path):
    with pytest.raises(UpdateError, match="nightly"):
        _updater(tmp_path, FakeSource(tag="nightly")).check()


def test_source_error_propagates(tmp_path):
    with pytest.raises(UpdateError, match="kaputt"):
        _updater(tmp_path, FakeSource(error=UpdateError("kaputt"))).check()


def test_windows_file_allows_self_update(tmp_path):
    assert _updater(tmp_path, platform="win32").check().can_self_update is True


def test_fallback_when_running_from_source(tmp_path):
    result = _updater(tmp_path, frozen=False).check()

    assert result.can_self_update is False
    assert "Quellcode" in result.fallback_reason


def test_fallback_on_unsupported_os(tmp_path):
    result = _updater(tmp_path, platform="darwin").check()

    assert result.can_self_update is False
    assert "Betriebssystem" in result.fallback_reason


def test_fallback_when_folder_not_writable(tmp_path):
    folder = tmp_path / "ro"
    folder.mkdir()
    folder.chmod(0o555)
    try:
        updater = AppUpdater(
            FakeSource(), "1.1.0", folder / "app", frozen=True, platform="linux"
        )
        result = updater.check()
    finally:
        folder.chmod(0o755)

    assert result.can_self_update is False
    assert "beschreibbar" in result.fallback_reason


def test_fallback_when_release_has_no_matching_file(tmp_path):
    result = _updater(tmp_path, FakeSource(files={WINDOWS_FILE: "u"})).check()

    assert result.can_self_update is False
    assert "Datei" in result.fallback_reason


# --- GitHub-Adapter -------------------------------------------------------------------------


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_github_adapter_parses_latest_release_json():
    payload = {
        "tag_name": "v1.2.0",
        "body": "Release notes",
        "html_url": "https://github.com/x/y/releases/tag/v1.2.0",
        "assets": [
            {"name": LINUX_FILE, "browser_download_url": "https://dl.test/linux"},
            {"name": "SHA256SUMS", "browser_download_url": "https://dl.test/sums"},
        ],
    }
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return _Response(json.dumps(payload).encode())

    release = GitHubReleaseSource("x/y", opener=opener).latest_release()

    assert seen == {"url": "https://api.github.com/repos/x/y/releases/latest", "timeout": 15}
    assert release == ReleaseInfo(
        tag="v1.2.0",
        notes="Release notes",
        page_url="https://github.com/x/y/releases/tag/v1.2.0",
        files={LINUX_FILE: "https://dl.test/linux", "SHA256SUMS": "https://dl.test/sums"},
    )


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (urllib.error.URLError("dns"), "Keine Verbindung"),
        (urllib.error.URLError(TimeoutError()), "Zeitüberschreitung"),
        (TimeoutError(), "Zeitüberschreitung"),
        (urllib.error.HTTPError("u", 403, "rate", {}, None), "Rate-Limit"),
        (urllib.error.HTTPError("u", 500, "boom", {}, None), "HTTP 500"),
    ],
)
def test_github_adapter_translates_errors_to_german_messages(raised, expected):
    def opener(request, timeout):
        raise raised

    with pytest.raises(UpdateError, match=expected):
        GitHubReleaseSource("x/y", opener=opener).latest_release()


def test_github_adapter_rejects_garbage_response():
    with pytest.raises(UpdateError, match="Unerwartete Antwort"):
        GitHubReleaseSource("x/y", opener=lambda r, timeout: _Response(b"<html>")).latest_release()


# --- Installation ---------------------------------------------------------------------------

NEW_BINARY = b"neue-version" * 50_000  # mehrere Chunks
SUMS_URL = "https://dl.test/sums"


def _install_setup(tmp_path, *, sums="ok", binary=NEW_BINARY, platform="linux", name=LINUX_FILE):
    files = {name: "https://dl.test/bin"}
    blobs = {"https://dl.test/bin": binary}
    if sums is not None:
        digest = hashlib.sha256(NEW_BINARY).hexdigest() if sums == "ok" else "0" * 64
        files["SHA256SUMS"] = SUMS_URL
        blobs[SUMS_URL] = f"{'1' * 64}  other-file\n{digest}  {name}\n".encode()
    source = FakeSource(files=files)
    source.blobs = blobs
    running = tmp_path / "meine-app"
    running.write_bytes(b"alte-version")
    running.chmod(0o755)
    updater = AppUpdater(source, "1.1.0", running, frozen=True, platform=platform)
    return updater, running, source


def _names(tmp_path):
    return sorted(p.name for p in tmp_path.iterdir())


def test_install_with_matching_checksum_swaps_files(tmp_path):
    updater, running, _ = _install_setup(tmp_path)
    release = updater.check()

    updater.install(release, lambda p: None, lambda: False)

    assert running.read_bytes() == NEW_BINARY
    assert (tmp_path / "meine-app.old").read_bytes() == b"alte-version"
    assert _names(tmp_path) == ["meine-app", "meine-app.old"]
    assert running.stat().st_mode & 0o111  # bleibt ausführbar


def test_install_windows_file_name(tmp_path):
    updater, running, _ = _install_setup(tmp_path, platform="win32", name=WINDOWS_FILE)

    updater.install(updater.check(), lambda p: None, lambda: False)

    assert running.read_bytes() == NEW_BINARY


def test_install_checksum_mismatch_refuses_and_leaves_no_new(tmp_path):
    updater, running, _ = _install_setup(tmp_path, sums="bad")

    with pytest.raises(UpdateError, match="Prüfsumme"):
        updater.install(updater.check(), lambda p: None, lambda: False)

    assert running.read_bytes() == b"alte-version"
    assert _names(tmp_path) == ["meine-app"]


def test_install_without_sha256sums_refuses_and_leaves_no_new(tmp_path):
    updater, running, _ = _install_setup(tmp_path, sums=None)

    with pytest.raises(UpdateError, match="SHA256SUMS"):
        updater.install(updater.check(), lambda p: None, lambda: False)

    assert running.read_bytes() == b"alte-version"
    assert _names(tmp_path) == ["meine-app"]


def test_install_cancel_mid_download_leaves_running_file_and_no_new(tmp_path):
    updater, running, _ = _install_setup(tmp_path)
    seen = []

    with pytest.raises(UpdateError, match="abgebrochen"):
        updater.install(updater.check(), seen.append, lambda: len(seen) >= 2)

    assert running.read_bytes() == b"alte-version"
    assert _names(tmp_path) == ["meine-app"]


def test_install_progress_is_monotonic_and_ends_at_100(tmp_path):
    updater, _, _ = _install_setup(tmp_path)
    seen = []

    updater.install(updater.check(), seen.append, lambda: False)

    assert seen == sorted(seen)
    assert len(set(seen)) > 2
    assert seen[-1] == 100
    assert all(0 <= p <= 100 for p in seen)


def test_install_download_error_leaves_no_new(tmp_path):
    updater, running, source = _install_setup(tmp_path)
    original = source.open_download

    def broken(url):
        if url == "https://dl.test/bin":
            raise UpdateError("Keine Verbindung zu GitHub (Netzwerkfehler).")
        return original(url)

    source.open_download = broken

    with pytest.raises(UpdateError, match="Keine Verbindung"):
        updater.install(updater.check(), lambda p: None, lambda: False)

    assert _names(tmp_path) == ["meine-app"]


def test_install_refuses_release_that_cannot_self_update(tmp_path):
    updater, _, _ = _install_setup(tmp_path, sums=None)
    release = _updater(tmp_path, frozen=False).check()  # Fallback-Release

    with pytest.raises(UpdateError):
        updater.install(release, lambda p: None, lambda: False)

    assert _names(tmp_path) == ["meine-app"]


def test_after_install_check_reports_restart_pending_without_new_download(tmp_path):
    from fritz_callhistory.app_update import RestartPending

    updater, _, source = _install_setup(tmp_path)
    updater.install(updater.check(), lambda p: None, lambda: False)
    downloads = len(source.opened)

    assert updater.check() == RestartPending("1.2.0")
    assert len(source.opened) == downloads


def test_restart_command_starts_the_new_file(tmp_path):
    updater, running, _ = _install_setup(tmp_path)

    assert updater.restart_command() == [str(running)]


def test_cleanup_previous_removes_old_file(tmp_path):
    updater, running, _ = _install_setup(tmp_path)
    updater.install(updater.check(), lambda p: None, lambda: False)
    fresh = AppUpdater(FakeSource(), "1.2.0", running, frozen=True, platform="linux")

    fresh.cleanup_previous()

    assert _names(tmp_path) == ["meine-app"]


def test_cleanup_previous_without_old_file_is_a_noop(tmp_path):
    updater, _, _ = _install_setup(tmp_path)

    updater.cleanup_previous()

    assert _names(tmp_path) == ["meine-app"]


def test_github_adapter_open_download_returns_stream_and_total_size():
    class Response(_Response):
        headers = {"Content-Length": "5"}

    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        return Response(b"hallo")

    stream, total = GitHubReleaseSource("x/y", opener=opener).open_download("https://dl.test/f")

    assert seen["url"] == "https://dl.test/f"
    assert (stream.read(), total) == (b"hallo", 5)


def test_github_adapter_open_download_translates_http_error():
    def opener(request, timeout):
        raise urllib.error.HTTPError("u", 404, "nf", {}, None)

    with pytest.raises(UpdateError, match="HTTP 404"):
        GitHubReleaseSource("x/y", opener=opener).open_download("https://dl.test/f")
