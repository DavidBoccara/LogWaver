"""Panneau du didacticiel, ancré à droite de la fenêtre principale."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TutorialPanel(QDockWidget):
    """Affiche une étape du didacticiel et les boutons de navigation.

    Signaux : ``next_clicked``, ``previous_clicked``, ``action_clicked``,
    ``quit_clicked``.
    """

    next_clicked = pyqtSignal()
    previous_clicked = pyqtSignal()
    action_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit le panneau (masqué par défaut).

        :param parent: widget parent.
        """
        super().__init__("Didacticiel", parent)
        self.setObjectName("TutorialPanel")
        self.setFeatures(QDockWidget.DockWidgetMovable)
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._title = QLabel()
        self._title.setObjectName("TutorialTitle")
        self._title.setWordWrap(True)
        self._text = QLabel()
        self._text.setObjectName("TutorialText")
        self._text.setWordWrap(True)
        self._text.setOpenExternalLinks(False)
        self._action_button = QPushButton()
        self._action_button.setObjectName("TutorialAction")
        self._action_button.setProperty("role", "hero")
        self._previous_button = QPushButton("◀ Précédent")
        self._next_button = QPushButton("Suivant ▶")
        self._next_button.setProperty("role", "primary")
        self._quit_button = QPushButton("Quitter le didacticiel")
        self._quit_button.setProperty("role", "link")
        self._build_layout()
        self._next_button.clicked.connect(self.next_clicked)
        self._previous_button.clicked.connect(self.previous_clicked)
        self._action_button.clicked.connect(self.action_clicked)
        self._quit_button.clicked.connect(self.quit_clicked)
        self.hide()

    def show_step(self, index: int, count: int, title: str, text: str,
                  action_label: str, is_first: bool, is_last: bool) -> None:
        """Affiche une étape.

        :param index: index (0-based) de l'étape.
        :param count: nombre total d'étapes.
        :param title: titre de l'étape.
        :param text: explication (HTML simple).
        :param action_label: libellé du bouton d'action (vide = pas d'action).
        :param is_first: ``True`` pour la première étape.
        :param is_last: ``True`` pour la dernière étape.
        """
        self._progress.setRange(0, count)
        self._progress.setValue(index + 1)
        self._progress.setFormat(f"Étape {index + 1} sur {count}")
        self._title.setText(title)
        self._text.setText(text)
        self._action_button.setText(f"▶ {action_label}" if action_label else "")
        self._action_button.setVisible(bool(action_label))
        self._previous_button.setEnabled(not is_first)
        self._next_button.setText("Terminer ✔" if is_last else "Suivant ▶")
        self.show()
        self.raise_()

    def _build_layout(self) -> None:
        """Dispose le contenu du panneau."""
        navigation = QHBoxLayout()
        navigation.addWidget(self._previous_button)
        navigation.addStretch(1)
        navigation.addWidget(self._next_button)
        content = QWidget()
        content.setObjectName("TutorialContent")
        layout = QVBoxLayout(content)
        layout.addWidget(self._progress)
        layout.addWidget(self._title)
        layout.addWidget(self._text)
        layout.addWidget(self._action_button)
        layout.addStretch(1)
        layout.addLayout(navigation)
        layout.addWidget(self._quit_button)
        content.setMinimumWidth(330)
        self.setWidget(content)
