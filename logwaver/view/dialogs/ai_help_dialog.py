"""Dialogue d'aide IA : prompt généré, réponse et justification proposée."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from logwaver.view_models import AiHelpData, AiSuggestionData

NO_AI_HINT: str = (
    "Aucune IA n'est branchée : le prompt a été affiché dans le terminal. "
    "Copiez-le dans votre IA puis collez sa réponse ci-dessous."
)


class AiHelpDialog(QDialog):
    """Dialogue passif ; le présentateur réagit à ses signaux.

    Signaux :
    * ``ask_requested(prompt)`` : (re)soumettre le prompt à l'IA ;
    * ``analyse_requested(réponse)`` : extraire la proposition de la réponse ;
    * ``apply_requested(statut, justification, même_code)`` : justifier.
    """

    ask_requested = pyqtSignal(str)
    analyse_requested = pyqtSignal(str)
    apply_requested = pyqtSignal(str, str, bool)

    def __init__(self, data: AiHelpData, parent: Optional[QWidget] = None) -> None:
        """Construit le dialogue.

        :param data: prompt, réponse initiale et catégories.
        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("AiHelpDialog")
        self.setWindowTitle(f"Aide IA - {data.title}")
        self.resize(900, 720)
        self._prompt_edit = QPlainTextEdit(data.prompt)
        self._prompt_edit.setObjectName("PromptText")
        self._copy_button = QPushButton("Copier le prompt")
        self._ask_button = QPushButton("Envoyer à l'IA")
        self._response_edit = QPlainTextEdit(data.response)
        self._response_edit.setPlaceholderText("Réponse de l'IA…")
        self._analyse_button = QPushButton("Analyser la réponse")
        self._hint_label = QLabel("" if data.response else NO_AI_HINT)
        self._hint_label.setObjectName("HintLabel")
        self._hint_label.setWordWrap(True)
        self._explanation_label = QLabel()
        self._explanation_label.setWordWrap(True)
        self._assessment_label = QLabel()
        self._assessment_label.setWordWrap(True)
        self._status_combo = QComboBox()
        for status in data.statuses:
            self._status_combo.addItem(status.label, status.status_id)
        self._justification_edit = QPlainTextEdit()
        self._justification_edit.setPlaceholderText("Justification proposée par l'IA…")
        self._same_code_check = QCheckBox(
            f"Appliquer à tous les éléments ayant le même code "
            f"({data.same_code_count} élément(s))"
        )
        self._same_code_check.setEnabled(data.same_code_count > 1)
        self._apply_button = QPushButton("Justifier avec la proposition de l'IA")
        self._apply_button.setProperty("role", "primary")
        self._close_button = QPushButton("Fermer")
        self._build_layout()
        self._connect_signals()
        self._update_apply_state()

    # -------------------------------------------------------- API du présentateur
    def set_response(self, response: str) -> None:
        """Affiche la réponse renvoyée par l'IA.

        :param response: texte de la réponse.
        """
        self._response_edit.setPlainText(response)
        self._hint_label.setText("")

    def show_hint(self, text: str) -> None:
        """Affiche un message d'information sous la réponse.

        :param text: message.
        """
        self._hint_label.setText(text)

    def show_suggestion(self, suggestion: AiSuggestionData) -> None:
        """Affiche la proposition extraite de la réponse.

        :param suggestion: proposition structurée.
        """
        self._explanation_label.setText(suggestion.explanation or "—")
        self._assessment_label.setText(suggestion.assessment or "—")
        if suggestion.status_id:
            index = self._status_combo.findData(suggestion.status_id)
            if index >= 0:
                self._status_combo.setCurrentIndex(index)
        self._justification_edit.setPlainText(suggestion.justification)

    # ------------------------------------------------------------------ interne
    def _build_layout(self) -> None:
        """Dispose les zones prompt / réponse / proposition."""
        prompt_box = QGroupBox("1. Prompt généré")
        prompt_layout = QVBoxLayout(prompt_box)
        prompt_layout.addWidget(self._prompt_edit)
        prompt_buttons = QHBoxLayout()
        prompt_buttons.addWidget(self._copy_button)
        prompt_buttons.addWidget(self._ask_button)
        prompt_buttons.addStretch(1)
        prompt_layout.addLayout(prompt_buttons)

        response_box = QGroupBox("2. Réponse de l'IA")
        response_layout = QVBoxLayout(response_box)
        response_layout.addWidget(self._response_edit)
        response_layout.addWidget(self._hint_label)
        response_layout.addWidget(self._analyse_button)

        proposal_box = QGroupBox("3. Proposition")
        proposal_form = QFormLayout(proposal_box)
        proposal_form.addRow("Explication :", self._explanation_label)
        proposal_form.addRow("Analyse :", self._assessment_label)
        proposal_form.addRow("Catégorie :", self._status_combo)
        proposal_form.addRow("Justification :", self._justification_edit)
        proposal_form.addRow("", self._same_code_check)

        splitter = QSplitter(Qt.Vertical)
        for box in (prompt_box, response_box, proposal_box):
            splitter.addWidget(box)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self._apply_button)
        bottom.addWidget(self._close_button)
        layout = QVBoxLayout(self)
        layout.addWidget(splitter, stretch=1)
        layout.addLayout(bottom)

    def _connect_signals(self) -> None:
        """Relie les boutons aux signaux publics."""
        self._copy_button.clicked.connect(self._copy_prompt)
        self._ask_button.clicked.connect(
            lambda: self.ask_requested.emit(self._prompt_edit.toPlainText())
        )
        self._analyse_button.clicked.connect(
            lambda: self.analyse_requested.emit(self._response_edit.toPlainText())
        )
        self._apply_button.clicked.connect(self._emit_apply)
        self._close_button.clicked.connect(self.reject)
        self._justification_edit.textChanged.connect(self._update_apply_state)

    def _copy_prompt(self) -> None:
        """Copie le prompt dans le presse-papiers."""
        QApplication.clipboard().setText(self._prompt_edit.toPlainText())
        self.show_hint("Prompt copié dans le presse-papiers.")

    def _emit_apply(self) -> None:
        """Émet la demande de justification."""
        self.apply_requested.emit(
            str(self._status_combo.currentData()),
            self._justification_edit.toPlainText().strip(),
            self._same_code_check.isChecked(),
        )

    def _update_apply_state(self) -> None:
        """N'autorise la justification qu'avec un texte non vide."""
        self._apply_button.setEnabled(
            bool(self._justification_edit.toPlainText().strip())
        )
