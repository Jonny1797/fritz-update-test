"""Dialoge der Update-Suche (Hilfe → Nach Updates suchen…)."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from fritz_callhistory.app_update import ReleaseAvailable

TITLE = "Nach Updates suchen"


def show_up_to_date(parent: QWidget, version: str) -> None:
    QMessageBox.information(parent, TITLE, f"Fritz Anrufhistorie ist aktuell ({version}).")


def show_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, TITLE, message)


def ask_update_now(parent: QWidget, release: ReleaseAvailable) -> bool:
    """Neue Version samt Release-Notes; True bei „Jetzt aktualisieren“."""
    box = QMessageBox(parent)
    box.setWindowTitle(TITLE)
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(f"Version {release.version} ist verfügbar (installiert: {release.installed}).")
    box.setDetailedText(release.notes)
    update = box.addButton("Jetzt aktualisieren", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Später", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is update


def ask_open_release_page(parent: QWidget, release: ReleaseAvailable) -> bool:
    """Fallback: Grund nennen; True bei „Release-Seite öffnen“."""
    box = QMessageBox(parent)
    box.setWindowTitle(TITLE)
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(
        f"Version {release.version} ist verfügbar (installiert: {release.installed}).\n\n"
        f"{release.fallback_reason}\nBitte lade das Release von Hand herunter."
    )
    box.setDetailedText(release.notes)
    open_page = box.addButton("Release-Seite öffnen", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Schließen", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is open_page
