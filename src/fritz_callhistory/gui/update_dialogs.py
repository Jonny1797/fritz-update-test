"""Dialoge der Update-Suche (Hilfe → Nach Updates suchen…)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

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


def make_progress_dialog(parent: QWidget, version: str) -> QProgressDialog:
    """Modaler Fortschrittsdialog (Prozent) mit „Abbrechen“; kein Auto-Schließen."""
    dialog = QProgressDialog(f"Version {version} wird heruntergeladen …", "Abbrechen", 0, 100, parent)
    dialog.setWindowTitle(TITLE)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setValue(0)
    return dialog


def ask_restart_now(parent: QWidget, text: str) -> bool:
    """Neustart-Wahl; True bei „Jetzt neu starten“."""
    box = QMessageBox(parent)
    box.setWindowTitle(TITLE)
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(text)
    restart = box.addButton("Jetzt neu starten", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Später", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is restart


def ask_restart_after_install(parent: QWidget, version: str) -> bool:
    return ask_restart_now(
        parent, f"Version {version} wurde installiert. Jetzt neu starten, um sie zu verwenden?"
    )


def ask_restart_pending(parent: QWidget, version: str) -> bool:
    return ask_restart_now(
        parent, f"Version {version} ist bereits installiert – Neustart ausstehend."
    )
