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

EMPTY_TITLE: str = "Aucun élément sélectionné"


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
        self._classify_button = QPushButton("Classer / Justifier…")
        self._classify_button.setProperty("role", "primary")
        self._unclassify_button = QPushButton("Retirer la justification")
        self._ai_button = QPushButton("Aide IA…")
        self._doc_button = QPushButton("Documentation PDF")
        self._source_button = QPushButton("Aller à la ligne")
        self._build_layout()
        self._connect_signals()
        self.show_details(None)

    def show_details(self, details: Optional[EntryDetails]) -> None:
        """Affiche les détails d'un élément (ou vide le panneau).

        :param details: contenu à afficher, ``None`` pour vider.
        """
        self._clear_fields()
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

    def _clear_fields(self) -> None:
        """Supprime les lignes du formulaire des champs."""
        while self._fields_layout.rowCount():
            self._fields_layout.removeRow(0)

    def _build_layout(self) -> None:
        """Dispose les widgets verticalement."""
        justification_box = QGroupBox("Justification")
        justification_layout = QVBoxLayout(justification_box)
        justification_layout.addWidget(self._status_label)
        justification_layout.addWidget(self._meta_label)
        justification_layout.addWidget(self._justification_text)
        actions_box = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_box)
        for button in (self._classify_button, self._unclassify_button,
                       self._ai_button, self._doc_button, self._source_button):
            actions_layout.addWidget(button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(self._fields_box)
        layout.addWidget(QLabel("Ligne du log :"))
        layout.addWidget(self._raw_text)
        layout.addWidget(justification_box, stretch=1)
        layout.addWidget(actions_box)

    def _connect_signals(self) -> None:
        """Relie les boutons aux signaux publics."""
        self._classify_button.clicked.connect(self.classify_clicked)
        self._unclassify_button.clicked.connect(self.unclassify_clicked)
        self._ai_button.clicked.connect(self.ai_help_clicked)
        self._doc_button.clicked.connect(self.documentation_clicked)
        self._source_button.clicked.connect(self.goto_source_clicked)
