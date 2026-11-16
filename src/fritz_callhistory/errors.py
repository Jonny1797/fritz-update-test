"""Gemeinsame Basis aller Fehler, die der Nutzer als einzeilige deutsche Meldung sieht."""

from __future__ import annotations


class AppError(Exception):
    """Fehler mit einer deutschen, einzeiligen Nutzermeldung (str(error))."""

    @property
    def user_message(self) -> str:
        return str(self)
