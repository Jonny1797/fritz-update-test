"""AppUpdater: prüft, ob ein neueres Release vorliegt, und ob die App sich selbst ersetzen kann."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from packaging.version import InvalidVersion, Version

from fritz_callhistory.errors import AppError

# Release-Dateiname je Plattform (sys.platform).
PLATFORM_FILES = {
    "linux": "fritz-callhistory-linux-x86_64",
    "win32": "fritz-callhistory-windows-x86_64.exe",
}


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

    def check(self) -> CheckResult:
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
