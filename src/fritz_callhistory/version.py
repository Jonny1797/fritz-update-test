"""Installierte App-Version aus den Paket-Metadaten (kommt aus dem Git-Tag, ADR 0001)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

PACKAGE_NAME = "fritz-callhistory"
REPO_URL = "https://github.com/Jonny1797/Fritz.CallMonitor"


def installed_version() -> str:
    """Version der laufenden App; "0.0.0", wenn keine Metadaten vorhanden sind."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0"
