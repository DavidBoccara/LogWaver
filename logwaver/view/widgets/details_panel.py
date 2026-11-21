"""Panneau de détails de l'élément sélectionné et boutons d'action."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from logwaver.view_models import ActionsState, EntryDetails

EMPTY_TITLE: str = "Sélectionnez un élément ou un groupe dans la liste"


class DetailsPanel(QWidget):
    """Affiche les champs, la justification et les actions disponibles."""

    classify_clicked = pyqtSignal()
    unclassify_clicked = pyqtSignal()
    ai_help_clicked = pyqtSignal()
    documentation_clicked = pyqtSignal()
    goto_source_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit le panneau.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("DetailsPanel")
        self._title = QLabel(EMPTY_TITLE)
        self._title.setObjectName("PanelTitle")
        self._title.setWordWrap(True)
        self._fields_box = QGroupBox("Informations extraites")
        self._raw_label = QLabel("Ligne du log :")
        self._justification_box = QGroupBox("Justification")
        self._fields_layout = QFormLayout(self._fields_box)
        self._raw_text = QPlainTextEdit()
        self._raw_text.setObjectName("RawLogLine")
        self._raw_text.setReadOnly(True)
        self._raw_text.setMaximumHeight(70)
        self._status_label = QLabel()
        self._status_label.setObjectName("StatusBadge")
        self._meta_label = QLabel()
        self._meta_label.setObjectName("MetaLabel")
        self._justification_text = QPlainTextEdit()
        self._justification_text.setReadOnly(True)
        self._classify_button = QPushButton("✔ Justifier…")
        self._classify_button.setObjectName("JustifyButton")
        self._classify_button.setProperty("role", "hero")
        self._classify_button.setToolTip("Classer la sélection et expliquer pourquoi (Ctrl+J)")
        self._unclassify_button = QPushButton("Retirer la justification")
        self._unclassify_button.setObjectName("UnjustifyButton")
        self._unclassify_button.setToolTip("L'élément redevient « non justifié » (Suppr)")
        self._ai_button = QPushButton("Demander à l'IA…")
        self._ai_button.setObjectName("AiButton")
        self._ai_button.setToolTip("Obtenir une explication et une proposition de "
                                   "justification (Ctrl+I)")
        self._doc_button = QPushButton("Voir la documentation")
        self._doc_button.setObjectName("DocButton")
        self._doc_button.setToolTip("Ouvrir le PDF de l'outil à la page de ce code (F1)")
        self._source_button = QPushButton("Ouvrir le fichier source")
        self._source_button.setObjectName("SourceButton")
        self._source_button.setToolTip("Afficher le fichier à la ligne concernée (Ctrl+G)")
        self._build_layout()
        self._connect_signals()
        self.show_details(None)

    def show_details(self, details: Optional[EntryDetails]) -> None:
        """Affiche les détails d'un élément (ou vide le panneau).

        :param details: contenu à afficher, ``None`` pour vider.
        """
        self._clear_fields()
        self._set_detail_sections_visible(details is not None)
        if details is None:
            self._title.setText(EMPTY_TITLE)
            self._raw_text.clear()
            self._set_justification("", "", "", "")
            return
        self._title.setText(details.title)
        for label, value in details.fields:
            value_label = QLabel(value or "—")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._fields_layout.addRow(f"{label} :", value_label)
        self._raw_text.setPlainText(details.raw_text)
        meta = ""
        if details.author:
            meta = f"Par {details.author} le {details.timestamp} ({details.source})"
        self._set_justification(details.status_label, details.status_color,
                                meta, details.justification_text)

    def set_actions_state(self, state: ActionsState) -> None:
        """Active/désactive les boutons.

        :param state: disponibilité des actions.
        """
        self._classify_button.setEnabled(state.has_selection)
        self._unclassify_button.setEnabled(state.selection_classified)
        self._ai_button.setEnabled(state.single_selection)
        self._doc_button.setEnabled(state.single_selection
                                    and state.can_open_documentation)
        self._source_button.setEnabled(state.single_selection
                                       and state.can_open_source)

    def _set_justification(self, status: str, color: str, meta: str,
                           text: str) -> None:
        """Met à jour la zone de justification.

        :param status: libellé de catégorie.
        :param color: couleur de la catégorie.
        :param meta: ligne auteur/date/origine.
        :param text: justification.
        """
        self._status_label.setText(status or "Non justifié")
        self._justification_text.setVisible(bool(text))
        # La couleur provient du fichier de configuration (donnée métier) ;
        # le reste du style du badge est défini dans le QSS.
        self._status_label.setStyleSheet(
            f"background-color: {color};" if color else ""
        )
        self._status_label.setProperty("classified", bool(status))
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        self._meta_label.setText(meta)
        self._justification_text.setPlainText(text)

    def _set_detail_sections_visible(self, visible: bool) -> None:
        """Masque les cadres de détail tant que rien n'est sélectionné.

        :param visible: ``True`` si une sélection est affichée.
        """
        for widget in (self._fields_box, self._raw_label, self._raw_text,
                       self._justification_box):
            widget.setVisible(visible)

    def _clear_fields(self) -> None:
        """Supprime les lignes du formulaire des champs."""
        while self._fields_layout.rowCount():
            self._fields_layout.removeRow(0)

    def _build_layout(self) -> None:
        """Dispose les widgets verticalement."""
        justification_layout = QVBoxLayout(self._justification_box)
        justification_layout.addWidget(self._status_label)
        justification_layout.addWidget(self._meta_label)
        justification_layout.addWidget(self._justification_text)
        actions_box = QGroupBox("Que voulez-vous faire ?")
        actions_layout = QVBoxLayout(actions_box)
        actions_layout.addWidget(self._classify_button)
        actions_layout.addWidget(self._unclassify_button)
        help_box = QGroupBox("Besoin d'aide pour décider ?")
        help_layout = QVBoxLayout(help_box)
        for button in (self._ai_button, self._doc_button, self._source_button):
            help_layout.addWidget(button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(actions_box)
        layout.addWidget(help_box)
        layout.addWidget(self._fields_box)
        layout.addWidget(self._raw_label)
        layout.addWidget(self._raw_text)
        layout.addWidget(self._justification_box, stretch=1)
        layout.addStretch(0)

    def _connect_signals(self) -> None:
        """Relie les boutons aux signaux publics."""
        self._classify_button.clicked.connect(self.classify_clicked)
        self._unclassify_button.clicked.connect(self.unclassify_clicked)
        self._ai_button.clicked.connect(self.ai_help_clicked)
        self._doc_button.clicked.connect(self.documentation_clicked)
        self._source_button.clicked.connect(self.goto_source_clicked)
