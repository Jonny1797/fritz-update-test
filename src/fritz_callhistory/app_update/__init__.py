"""App update: Suche nach neueren Releases (ohne Qt-Imports)."""

from fritz_callhistory.app_update.github import GitHubReleaseSource
from fritz_callhistory.app_update.updater import (
    AppUpdater,
    CheckResult,
    ReleaseAvailable,
    ReleaseInfo,
    ReleaseSource,
    RestartPending,
    UpdateCancelled,
    UpdateError,
    UpToDate,
)

__all__ = [
    "AppUpdater",
    "CheckResult",
    "GitHubReleaseSource",
    "ReleaseAvailable",
    "ReleaseInfo",
    "ReleaseSource",
    "RestartPending",
    "UpToDate",
    "UpdateCancelled",
    "UpdateError",
]
