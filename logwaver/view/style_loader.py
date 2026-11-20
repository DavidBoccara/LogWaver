"""Chargement de la feuille de style QSS (style séparé de la structure)."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import QApplication

LOGGER = logging.getLogger(__name__)


class StyleLoader:
    """Applique une feuille de style QSS à l'application."""

    def apply(self, application: QApplication, stylesheet_path: Path) -> bool:
        """Charge et applique un fichier QSS.

        :param application: application Qt.
        :param stylesheet_path: fichier ``.qss``.
        :return: ``True`` si le style a été appliqué.
        """
        try:
            application.setStyleSheet(
                stylesheet_path.read_text(encoding="utf-8")
            )
        except OSError as error:
            LOGGER.warning("Feuille de style non chargée (%s) : %s",
                           stylesheet_path, error)
            return False
        LOGGER.info("Feuille de style appliquée : %s", stylesheet_path)
        return True
