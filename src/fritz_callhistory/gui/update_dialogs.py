"""Dialoge der Update-Suche (Hilfe → Nach Updates suchen…)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from fritz_callhistory.app_update import ReleaseAvailable
from fritz_callhistory.version import APP_NAME

TITLE = "Nach Updates suchen"


def show_up_to_date(parent: QWidget, version: str) -> None:
    QMessageBox.information(parent, TITLE, f"{APP_NAME} ist aktuell ({version}).")


def show_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, TITLE, message)


def _ask(
    parent: QWidget,
    text: str,
    accept: str,
    reject: str,
    *,
    icon: QMessageBox.Icon = QMessageBox.Icon.Information,
    details: str | None = None,
) -> bool:
    """Frage mit zwei Knöpfen; True, wenn *accept* geklickt wurde."""
    box = QMessageBox(parent)
    box.setWindowTitle(TITLE)
    box.setIcon(icon)
    box.setText(text)
    if details is not None:
        box.setDetailedText(details)
    accept_button = box.addButton(accept, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(reject, QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is accept_button


def _available_text(release: ReleaseAvailable) -> str:
    return f"Version {release.version} ist verfügbar (installiert: {release.installed})."


def ask_update_now(parent: QWidget, release: ReleaseAvailable) -> bool:
    """Neue Version samt Release-Notes; True bei „Jetzt aktualisieren“."""
    return _ask(
        parent, _available_text(release), "Jetzt aktualisieren", "Später", details=release.notes
    )


def ask_open_release_page(parent: QWidget, release: ReleaseAvailable) -> bool:
    """Fallback: Grund nennen; True bei „Release-Seite öffnen“."""
    text = (
        f"{_available_text(release)}\n\n"
        f"{release.fallback_reason}\nBitte lade das Release von Hand herunter."
    )
    return _ask(parent, text, "Release-Seite öffnen", "Schließen", details=release.notes)


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
    return _ask(parent, text, "Jetzt neu starten", "Später", icon=QMessageBox.Icon.Question)


def ask_restart_after_install(parent: QWidget, version: str) -> bool:
    return ask_restart_now(
        parent, f"Version {version} wurde installiert. Jetzt neu starten, um sie zu verwenden?"
    )


def ask_restart_pending(parent: QWidget, version: str) -> bool:
    return ask_restart_now(
        parent, f"Version {version} ist bereits installiert – Neustart ausstehend."
    )
