"""GitHub-Adapter der Release-Quelle (stdlib urllib, öffentliche API)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable

from fritz_callhistory.app_update.updater import ReleaseInfo, UpdateError

DEFAULT_REPO = "Jonny1797/Fritz.CallMonitor"
TIMEOUT_S = 15


class GitHubReleaseSource:
    def __init__(self, repo: str = DEFAULT_REPO, opener: Callable | None = None) -> None:
        self._url = f"https://api.github.com/repos/{repo}/releases/latest"
        self._opener = opener or urllib.request.urlopen

    def latest_release(self) -> ReleaseInfo:
        request = urllib.request.Request(
            self._url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "fritz-callhistory",
            },
        )
        try:
            with self._opener(request, timeout=TIMEOUT_S) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise UpdateError(
                    "GitHub hat die Anfrage abgelehnt (Rate-Limit). Bitte später erneut versuchen."
                ) from exc
            raise UpdateError(f"GitHub-Fehler (HTTP {exc.code}).") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise UpdateError("Zeitüberschreitung bei der Verbindung zu GitHub.") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise UpdateError("Zeitüberschreitung bei der Verbindung zu GitHub.") from exc
            raise UpdateError("Keine Verbindung zu GitHub (Netzwerkfehler).") from exc
        except (OSError, ValueError) as exc:
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
