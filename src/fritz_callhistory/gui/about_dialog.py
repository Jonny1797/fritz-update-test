"""Über-Dialog: App-Name, Version, Repo-Link, Python- und Qt-Version."""

from __future__ import annotations

import platform

import PySide6
from PySide6.QtWidgets import QMessageBox, QWidget

from fritz_callhistory.version import APP_NAME, REPO_URL, installed_version


def about_text() -> str:
    return (
        f"<b>{APP_NAME}</b><br>"
        f"Version {installed_version()}<br><br>"
        f'<a href="{REPO_URL}">{REPO_URL}</a><br><br>'
        f"Python {platform.python_version()}<br>"
        f"Qt {PySide6.QtCore.qVersion()} (PySide6 {PySide6.__version__})"
    )


def show_about_dialog(parent: QWidget | None = None) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(f"Über {APP_NAME}")
    box.setIcon(QMessageBox.Icon.Information)
    box.setTextFormat(box.textFormat().RichText)
    box.setText(about_text())
    box.exec()
