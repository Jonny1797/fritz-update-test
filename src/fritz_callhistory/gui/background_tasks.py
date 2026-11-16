"""BackgroundTasks: ein Besitzer für alle einmaligen Hintergrundaufgaben (je ein QThread)."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

import shiboken6
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from fritz_callhistory.errors import AppError
from fritz_callhistory.fritz.exceptions import FritzBoxError

# Sekunden, die nach Beginn des Beendens auf laufende Aufgaben gewartet wird.
DEFAULT_FAILSAFE_TIMEOUT_S = 10.0


class CancelHandle:
    """Abbruch-Griff: der Starter ruft cancel(), die Aufgabe fragt is_cancelled."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class TaskControl:
    """Wird der Aufgabenfunktion übergeben, wenn Fortschritt oder Abbruch genutzt wird."""

    def __init__(self, report: Callable[[object], None], cancel: CancelHandle) -> None:
        self._report = report
        self._cancel = cancel

    def report_progress(self, value: object) -> None:
        """Meldet Fortschritt; der Fortschritts-Callback läuft im GUI-Thread."""
        self._report(value)

    @property
    def is_cancelled(self) -> bool:
        return self._cancel.is_cancelled


class _TaskThread(QThread):
    """Führt genau eine Funktion aus und legt Ergebnis oder Fehler am Thread-Objekt ab.

    Der Aufrufer wertet beides erst im finished-Signal (GUI-Thread) aus."""

    progress = Signal(object)

    def __init__(self, fn: Callable[[], object], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn
        self.result: object = None
        self.error: AppError | None = None

    def run(self) -> None:
        try:
            self.result = self._fn()
        except AppError as exc:
            self.error = exc
        except Exception as exc:  # Thread darf nie stillschweigend sterben
            self.error = FritzBoxError(f"Unerwarteter Fehler: {exc}")


@dataclass
class _Task:
    thread: _TaskThread
    key: str | None
    context: QObject
    on_success: Callable[[object], None]
    on_error: Callable[[AppError], None]
    on_progress: Callable[[object], None] | None = None


class BackgroundTasks(QObject):
    """Startet blockierende Funktionen im Hintergrund und liefert das Ergebnis im GUI-Thread."""

    all_finished = Signal()  # letzte laufende Aufgabe ist beendet

    def __init__(
        self,
        parent=None,
        *,
        exit_fn: Callable[[], None] | None = None,
        failsafe_timeout_s: float = DEFAULT_FAILSAFE_TIMEOUT_S,
    ) -> None:
        super().__init__(parent)
        self._exit_fn = exit_fn or (lambda: os._exit(1))
        self._tasks: list[_Task] = []
        self._quitting = False
        self._failsafe = QTimer(self)
        self._failsafe.setSingleShot(True)
        self._failsafe.setInterval(int(failsafe_timeout_s * 1000))
        self._failsafe.timeout.connect(self._on_failsafe)

    def start(
        self,
        fn: Callable[[], object],
        context: QObject,
        on_success: Callable[[object], None],
        on_error: Callable[[AppError], None],
        key: str | None = None,
        *,
        on_progress: Callable[[object], None] | None = None,
        cancel: CancelHandle | None = None,
    ) -> bool:
        """Startet *fn* im Hintergrund. Gibt False zurück, wenn der Start abgelehnt wurde
        (Schlüssel läuft schon oder die App wird beendet) - dann wird nichts aufgerufen.

        Mit *on_progress* und/oder *cancel* wird *fn* mit einem `TaskControl` aufgerufen
        (Fortschritt melden, Abbruch abfragen), sonst ohne Argument. *on_progress* läuft im
        GUI-Thread; ein abgebrochener Lauf endet wie jeder andere (fn entscheidet, ob sie
        einen Fehler wirft)."""
        if self._quitting:
            return False
        if key is not None and self.is_running(key):
            return False
        if on_progress is None and cancel is None:
            thread = _TaskThread(fn)
        else:
            handle = cancel or CancelHandle()
            # Der Lambda-Körper liest `thread` erst beim Aufruf, also nach der Zuweisung unten.
            control = TaskControl(lambda v: thread.progress.emit(v), handle)
            thread = _TaskThread(lambda: fn(control))  # type: ignore[call-arg]
        task = _Task(thread, key, context, on_success, on_error, on_progress)
        thread.progress.connect(lambda v, t=task: self._on_progress(t, v))
        self._tasks.append(task)
        thread.finished.connect(lambda t=task: self._on_thread_finished(t))
        thread.start()
        return True

    def is_running(self, key: str) -> bool:
        return any(t.key == key for t in self._tasks)

    def is_idle(self) -> bool:
        return not self._tasks

    @property
    def is_quitting(self) -> bool:
        """True, sobald begin_quit() aufgerufen wurde."""
        return self._quitting

    def begin_quit(self) -> None:
        """Ab jetzt keine neuen Aufgaben mehr und keine Callbacks; Failsafe wird gestartet."""
        self._quitting = True
        if self._tasks:
            self._failsafe.start()

    def _on_progress(self, task: _Task, value: object) -> None:
        if (
            task.on_progress is not None
            and not self._quitting
            and shiboken6.isValid(task.context)
        ):
            task.on_progress(value)

    def _on_thread_finished(self, task: _Task) -> None:
        # Erst aus der Liste entfernen, damit is_running() in den Callbacks False ist.
        self._tasks.remove(task)
        thread = task.thread
        try:
            if not self._quitting and shiboken6.isValid(task.context):
                if thread.error is not None:
                    task.on_error(thread.error)
                else:
                    task.on_success(thread.result)
        finally:
            thread.deleteLater()
            if not self._tasks:
                self._failsafe.stop()
                self.all_finished.emit()

    def _on_failsafe(self) -> None:
        if self._tasks:
            self._exit_fn()
