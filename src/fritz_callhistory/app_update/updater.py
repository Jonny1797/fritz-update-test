"""AppUpdater: prüft, ob ein neueres Release vorliegt, und ob die App sich selbst ersetzen kann."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Protocol

from packaging.version import InvalidVersion, Version

from fritz_callhistory.errors import AppError

# Release-Dateiname je Plattform (sys.platform).
PLATFORM_FILES = {
    "linux": "fritz-callhistory-linux-x86_64",
    "win32": "fritz-callhistory-windows-x86_64.exe",
}

SUMS_FILE = "SHA256SUMS"
CHUNK_SIZE = 64 * 1024


class UpdateError(AppError):
    """Fehler bei der Update-Suche oder -Installation (deutsche Einzeiler-Meldung)."""


@dataclass(frozen=True)
class ReleaseInfo:
    """Das neueste Release, wie die Release-Quelle es liefert."""

    tag: str
    notes: str
    page_url: str
    files: dict[str, str] = field(default_factory=dict)  # Dateiname -> Download-URL


class ReleaseSource(Protocol):
    def latest_release(self) -> ReleaseInfo:
        """Neuestes veröffentlichtes Release; wirft UpdateError bei Netz-/Serverfehlern."""
        ...

    def open_download(self, url: str) -> tuple[BinaryIO, int | None]:
        """Datei als Byte-Strom plus Gesamtgröße (None, falls unbekannt); Aufrufer schließt."""
        ...


@dataclass(frozen=True)
class UpToDate:
    version: str


@dataclass(frozen=True)
class ReleaseAvailable:
    version: str
    installed: str
    notes: str
    page_url: str
    can_self_update: bool
    fallback_reason: str | None = None
    files: dict[str, str] = field(default_factory=dict, compare=False)  # Dateiname -> URL


@dataclass(frozen=True)
class RestartPending:
    version: str


CheckResult = UpToDate | ReleaseAvailable | RestartPending


def _parse(text: str, what: str) -> Version:
    try:
        return Version(text.strip().removeprefix("v"))
    except InvalidVersion:
        raise UpdateError(f"{what} „{text}“ ist keine gültige Versionsnummer.") from None


class AppUpdater:
    def __init__(
        self,
        source: ReleaseSource,
        installed_version: str,
        running_file: Path,
        *,
        frozen: bool,
        platform: str,
    ) -> None:
        self._source = source
        self._installed = installed_version
        self._running_file = Path(running_file)
        self._frozen = frozen
        self._platform = platform
        self._pending_version: str | None = None  # nur für diesen Prozess

    def check(self) -> CheckResult:
        if self._pending_version is not None:
            return RestartPending(self._pending_version)
        release = self._source.latest_release()
        latest = _parse(release.tag, "Release-Tag")
        if latest <= _parse(self._installed, "Installierte Version"):
            return UpToDate(self._installed)
        reason = self._fallback_reason(release)
        return ReleaseAvailable(
            version=str(latest),
            installed=self._installed,
            notes=release.notes,
            page_url=release.page_url,
            can_self_update=reason is None,
            fallback_reason=reason,
            files=dict(release.files),
        )

    def _fallback_reason(self, release: ReleaseInfo) -> str | None:
        if not self._frozen:
            return "Die App läuft aus dem Quellcode und kann sich nicht selbst ersetzen."
        file_name = PLATFORM_FILES.get(self._platform)
        if file_name is None:
            return "Für dieses Betriebssystem gibt es keine automatische Aktualisierung."
        if not os.access(self._running_file.parent, os.W_OK):
            return "Der Ordner der App ist nicht beschreibbar."
        if file_name not in release.files:
            return "Das Release enthält keine passende Datei für dieses Betriebssystem."
        return None

    # --- Installation -----------------------------------------------------------------------

    def _sibling(self, suffix: str) -> Path:
        return self._running_file.with_name(self._running_file.name + suffix)

    def install(
        self,
        release: ReleaseAvailable,
        on_progress: Callable[[int], None],
        is_cancelled: Callable[[], bool],
    ) -> None:
        """Lädt die Plattformdatei, prüft die Prüfsumme und ersetzt die laufende Datei.

        Bei jedem Fehler oder Abbruch bleibt die laufende Datei unberührt und es bleibt keine
        `.new`-Datei übrig; der Grund kommt als UpdateError."""
        file_name = PLATFORM_FILES.get(self._platform)
        if not release.can_self_update or file_name is None:
            raise UpdateError("Die App kann sich nicht selbst aktualisieren.")
        url = release.files.get(file_name)
        sums_url = release.files.get(SUMS_FILE)
        if url is None:
            raise UpdateError("Das Release enthält keine passende Datei für dieses System.")
        if sums_url is None:
            raise UpdateError("Das Release enthält keine SHA256SUMS-Datei; Update abgebrochen.")
        expected = self._expected_checksum(sums_url, file_name)
        new_file = self._sibling(".new")
        try:
            digest = self._download(url, new_file, on_progress, is_cancelled)
            if digest != expected:
                raise UpdateError("Die Prüfsumme der Datei stimmt nicht; Update abgebrochen.")
            self._swap(new_file)
        except BaseException:
            new_file.unlink(missing_ok=True)
            raise
        self._pending_version = release.version

    def _expected_checksum(self, sums_url: str, file_name: str) -> str:
        try:
            stream, _ = self._source.open_download(sums_url)
            with stream:
                text = stream.read().decode("utf-8", errors="replace")
        except OSError as exc:
            raise UpdateError("SHA256SUMS konnte nicht geladen werden.") from exc
        for line in text.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) == 2 and parts[1].strip().lstrip("*") == file_name:
                return parts[0].lower()
        raise UpdateError(f"SHA256SUMS enthält keinen Eintrag für {file_name}.")

    def _download(
        self,
        url: str,
        target: Path,
        on_progress: Callable[[int], None],
        is_cancelled: Callable[[], bool],
    ) -> str:
        sha = hashlib.sha256()
        done = 0
        last = -1
        try:
            stream, total = self._source.open_download(url)
            with stream, target.open("wb") as out:
                while True:
                    if is_cancelled():
                        raise UpdateError("Update abgebrochen.")
                    chunk = stream.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
                    sha.update(chunk)
                    done += len(chunk)
                    if total:
                        percent = min(99, done * 100 // total)
                        if percent > last:
                            last = percent
                            on_progress(percent)
        except OSError as exc:
            raise UpdateError(f"Download fehlgeschlagen: {exc.strerror or exc}") from exc
        on_progress(100)
        return sha.hexdigest()

    def _swap(self, new_file: Path) -> None:
        old_file = self._sibling(".old")
        try:
            new_file.chmod(self._running_file.stat().st_mode & 0o7777)
            os.replace(self._running_file, old_file)
        except OSError as exc:
            raise UpdateError(f"Die App-Datei konnte nicht ersetzt werden: {exc}") from exc
        try:
            os.replace(new_file, self._running_file)
        except OSError as exc:
            try:
                os.replace(old_file, self._running_file)  # laufende Datei wiederherstellen
            except OSError:
                pass
            raise UpdateError(f"Die App-Datei konnte nicht ersetzt werden: {exc}") from exc

    def restart_command(self) -> list[str]:
        """Argv, das die (neue) Datei am Pfad der laufenden App startet."""
        return [str(self._running_file)]

    def cleanup_previous(self) -> None:
        """Beim App-Start: löscht eine übrig gebliebene `.old`-Datei eines früheren Updates."""
        if not self._frozen:
            return
        try:
            self._sibling(".old").unlink(missing_ok=True)
        except OSError:
            pass  # kein Grund, den Start zu stören
