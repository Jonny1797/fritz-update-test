"""GitHub-Adapter der Release-Quelle (stdlib urllib, öffentliche API)."""

from __future__ import annotations

import http.client
import json
import os
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

from fritz_callhistory.app_update.updater import ReleaseInfo, UpdateError
from fritz_callhistory.version import REPO

TIMEOUT_S = 15

# Nur für Tests des App-Updates: anderes GitHub-Repo (<owner>/<repo>) als Release-Quelle,
# siehe docs/testing/app-update.md. Leer oder nicht gesetzt = das echte Repo.
REPO_ENV = "FRITZ_UPDATE_REPO"


def release_repo(environ: Mapping[str, str] | None = None) -> str:
    """GitHub-Repo der Releases; die Umgebungsvariable REPO_ENV überschreibt REPO."""
    environ = os.environ if environ is None else environ
    return environ.get(REPO_ENV, "").strip() or REPO


class GitHubReleaseSource:
    def __init__(self, repo: str | None = None, opener: Callable | None = None) -> None:
        self.repo = repo or release_repo()
        self._url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        self._opener = opener or urllib.request.urlopen

    def _open(self, request: urllib.request.Request, *, http_error: str, timeout_error: str):
        """Öffnet *request* und übersetzt Netzwerkfehler in UpdateError (deutsche Meldung).

        *http_error* wird mit `code=` formatiert."""
        try:
            return self._opener(request, timeout=TIMEOUT_S)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise UpdateError(
                    "GitHub hat die Anfrage abgelehnt (Rate-Limit). Bitte später erneut versuchen."
                ) from exc
            raise UpdateError(http_error.format(code=exc.code)) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise UpdateError(timeout_error) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise UpdateError(timeout_error) from exc
            raise UpdateError("Keine Verbindung zu GitHub (Netzwerkfehler).") from exc

    def latest_release(self) -> ReleaseInfo:
        request = urllib.request.Request(
            self._url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "fritz-callhistory",
            },
        )
        response = self._open(
            request,
            http_error="GitHub-Fehler (HTTP {code}).",
            timeout_error="Zeitüberschreitung bei der Verbindung zu GitHub.",
        )
        try:
            with response:
                data = json.load(response)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            raise UpdateError("Unerwartete Antwort von GitHub.") from exc
        try:
            return ReleaseInfo(
                tag=data["tag_name"],
                notes=data.get("body") or "",
                page_url=data["html_url"],
                files={a["name"]: a["browser_download_url"] for a in data.get("assets", [])},
            )
        except (KeyError, TypeError) as exc:
            raise UpdateError("Unerwartete Antwort von GitHub.") from exc

    def open_download(self, url: str):
        """Öffnet eine Release-Datei als Byte-Strom; Rückgabe (Strom, Gesamtgröße oder None)."""
        request = urllib.request.Request(url, headers={"User-Agent": "fritz-callhistory"})
        response = self._open(
            request,
            http_error="Download fehlgeschlagen (HTTP {code}).",
            timeout_error="Zeitüberschreitung beim Download.",
        )
        length = getattr(response, "headers", {}).get("Content-Length")
        return response, int(length) if length and length.isdigit() else None
