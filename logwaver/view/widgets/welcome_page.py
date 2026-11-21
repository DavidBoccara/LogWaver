"""Page d'accueil affichée tant qu'aucun log n'est ouvert."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

STEPS_TEXT: tuple = (
    ("1", "Ouvrez un fichier de log",
     "LogWaver reconnaît automatiquement l'outil qui l'a produit."),
    ("2", "Justifiez les éléments",
     "Sélectionnez un élément, ou un groupe entier, puis cliquez sur « Justifier »."),
    ("3", "Enregistrez et partagez",
     "Le projet garde votre travail ; vos justifications se réappliquent toutes seules "
     "aux prochains logs."),
)


class WelcomePage(QWidget):
    """Accueil en trois étapes avec les actions de démarrage.

    Signaux : ``open_log_clicked``, ``open_project_clicked``,
    ``try_sample_clicked``, ``tutorial_clicked``, ``choose_plugin_clicked``.
    """

    open_log_clicked = pyqtSignal()
    open_project_clicked = pyqtSignal()
    try_sample_clicked = pyqtSignal()
    tutorial_clicked = pyqtSignal()
    choose_plugin_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit la page.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("WelcomePage")
        self._plugin_label = QLabel()
        self._plugin_label.setObjectName("HintLabel")
        self._open_log_button = QPushButton("Ouvrir un fichier de log…")
        self._open_log_button.setObjectName("WelcomeOpenLog")
        self._open_log_button.setProperty("role", "hero")
        self._open_project_button = QPushButton("Reprendre un projet enregistré…")
        self._sample_button = QPushButton("Essayer avec l'exemple fourni")
        self._sample_button.setObjectName("WelcomeSample")
        self._tutorial_button = QPushButton("Suivre le didacticiel (5 minutes)")
        self._tutorial_button.setObjectName("WelcomeTutorial")
        self._tutorial_button.setProperty("role", "primary")
        self._plugin_button = QPushButton("Choisir le plugin manuellement…")
        self._plugin_button.setProperty("role", "link")
        self._build_layout()
        self._open_log_button.clicked.connect(self.open_log_clicked)
        self._open_project_button.clicked.connect(self.open_project_clicked)
        self._sample_button.clicked.connect(self.try_sample_clicked)
        self._tutorial_button.clicked.connect(self.tutorial_clicked)
        self._plugin_button.clicked.connect(self.choose_plugin_clicked)
        self.set_plugin_info("")

    def set_plugin_info(self, tool_name: str) -> None:
        """Indique le plugin actuellement chargé.

        :param tool_name: nom de l'outil (vide = détection automatique).
        """
        self._plugin_label.setText(
            f"Plugin chargé : {tool_name}" if tool_name
            else "Plugin : détection automatique à l'ouverture du log")

    def _build_layout(self) -> None:
        """Dispose le titre, les trois étapes et les boutons."""
        title = QLabel("Bienvenue dans LogWaver")
        title.setObjectName("WelcomeTitle")
        subtitle = QLabel("Suivez et justifiez les notes, warnings et erreurs de vos logs.")
        subtitle.setObjectName("WelcomeSubtitle")
        steps = QHBoxLayout()
        for number, heading, text in STEPS_TEXT:
            steps.addWidget(self._step_card(number, heading, text))
        primary = QHBoxLayout()
        primary.addStretch(1)
        primary.addWidget(self._open_log_button)
        primary.addWidget(self._tutorial_button)
        primary.addStretch(1)
        secondary = QHBoxLayout()
        secondary.addStretch(1)
        secondary.addWidget(self._sample_button)
        secondary.addWidget(self._open_project_button)
        secondary.addStretch(1)
        plugin_row = QHBoxLayout()
        plugin_row.addStretch(1)
        plugin_row.addWidget(self._plugin_label)
        plugin_row.addWidget(self._plugin_button)
        plugin_row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(title, alignment=Qt.AlignHCenter)
        layout.addWidget(subtitle, alignment=Qt.AlignHCenter)
        layout.addSpacing(24)
        layout.addLayout(steps)
        layout.addSpacing(24)
        layout.addLayout(primary)
        layout.addLayout(secondary)
        layout.addSpacing(12)
        layout.addLayout(plugin_row)
        layout.addStretch(2)

    @staticmethod
    def _step_card(number: str, heading: str, text: str) -> QFrame:
        """Crée la carte d'une étape.

        :param number: numéro affiché.
        :param heading: titre de l'étape.
        :param text: explication.
        :return: carte prête à insérer.
        """
        card = QFrame()
        card.setObjectName("StepCard")
        number_label = QLabel(number)
        number_label.setObjectName("StepNumber")
        number_label.setAlignment(Qt.AlignCenter)
        heading_label = QLabel(heading)
        heading_label.setObjectName("StepHeading")
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setObjectName("HintLabel")
        layout = QVBoxLayout(card)
        layout.addWidget(number_label, alignment=Qt.AlignHCenter)
        layout.addWidget(heading_label, alignment=Qt.AlignHCenter)
        layout.addWidget(text_label)
        return card
