"""Visionneuse PDF intégrée (PyQtWebEngine), ouverte à une page donnée.

Ce module doit être importé **avant** la création de ``QApplication`` (contrainte
de QtWebEngine) : ``main.py`` s'en charge via :func:`is_web_engine_available`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QWidget

LOGGER = logging.getLogger(__name__)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineView
    _WEB_ENGINE_ERROR: Optional[str] = None
except ImportError as import_error:  # pragma: no cover - dépend de l'installation
    QWebEngineSettings = None  # type: ignore[assignment,misc]
    QWebEngineView = None  # type: ignore[assignment,misc]
    _WEB_ENGINE_ERROR = str(import_error)


def is_web_engine_available() -> bool:
    """Indique si PyQtWebEngine est utilisable.

    :return: ``True`` si la visionneuse intégrée peut être créée.
    """
    if _WEB_ENGINE_ERROR:
        LOGGER.warning("PyQtWebEngine indisponible : %s", _WEB_ENGINE_ERROR)
    return _WEB_ENGINE_ERROR is None


class PdfViewerDialog(QDialog):
    """Fenêtre non modale affichant un PDF via le lecteur de Chromium."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit la fenêtre.

        :param parent: widget parent.
        :raises RuntimeError: si PyQtWebEngine est indisponible.
        """
        super().__init__(parent)
        if QWebEngineView is None:
            raise RuntimeError("PyQtWebEngine n'est pas disponible.")
        self.setObjectName("PdfViewerDialog")
        self.resize(1000, 800)
        self._view = QWebEngineView()
        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

    def show_page(self, pdf_path: Path, page: int) -> None:
        """Ouvre le PDF à la page demandée.

        :param pdf_path: fichier PDF.
        :param page: numéro de page (1 = première).
        """
        url = QUrl.fromLocalFile(str(pdf_path))
        url.setFragment(f"page={page}")
        self.setWindowTitle(f"{pdf_path.name} - page {page}")
        # Un rechargement explicite est nécessaire pour changer de page sur
        # un même document (le fragment seul ne relance pas la navigation).
        self._view.setUrl(QUrl("about:blank"))
        self._view.setUrl(url)
        self.show()
        self.raise_()
        self.activateWindow()
