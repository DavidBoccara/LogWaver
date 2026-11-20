"""Dialogue de justification : choix de la catégorie et saisie du motif."""

from __future__ import annotations

from typing import List, Optional, Sequence

from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from logwaver.view_models import JustificationRequest, StatusChoice

OK_BUTTON_LABEL: str = "Justifier"


class JustificationDialog(QDialog):
    """Demande une catégorie et un motif, avec des choix explicites."""

    def __init__(
        self,
        statuses: Sequence[StatusChoice],
        selection_label: str,
        selection_count: int,
        same_code_count: int,
        initial_status_id: str = "",
        initial_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Construit le dialogue.

        :param statuses: catégories proposées.
        :param selection_label: description de ce qui est justifié.
        :param selection_count: nombre d'éléments sélectionnés.
        :param same_code_count: éléments partageant le(s) même(s) code(s).
        :param initial_status_id: catégorie présélectionnée.
        :param initial_text: motif prérempli.
        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("JustificationDialog")
        self.setWindowTitle("Justifier")
        self.setMinimumWidth(560)
        self._radio_group = QButtonGroup(self)
        self._radios: List[QRadioButton] = []
        self._status_ids: List[str] = []
        self._text_edit = QPlainTextEdit(initial_text)
        self._text_edit.setPlaceholderText(
            "Exemple : « Fichier optionnel, son absence est prévue en configuration "
            "minimale. »")
        self._same_code_check = QCheckBox(
            f"Appliquer aussi aux autres éléments ayant le même code "
            f"({same_code_count} au total)")
        self._same_code_check.setVisible(same_code_count > selection_count)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.button(QDialogButtonBox.Ok).setText(OK_BUTTON_LABEL)
        self._buttons.button(QDialogButtonBox.Ok).setProperty("role", "primary")
        self._buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        self._build_layout(statuses, selection_label, initial_status_id)
        self._text_edit.textChanged.connect(self._update_ok_state)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._update_ok_state()
        self._text_edit.setFocus()

    def request(self) -> JustificationRequest:
        """Retourne la saisie de l'utilisateur.

        :return: catégorie, motif et extension éventuelle au même code.
        """
        index = max(self._radio_group.checkedId(), 0)
        return JustificationRequest(
            status_id=self._status_ids[index],
            text=self._text_edit.toPlainText().strip(),
            apply_to_same_code=self._same_code_check.isChecked(),
        )

    def _build_layout(self, statuses: Sequence[StatusChoice], selection_label: str,
                      initial_status_id: str) -> None:
        """Dispose les trois étapes : quoi, quelle catégorie, pourquoi.

        :param statuses: catégories proposées.
        :param selection_label: description de la sélection.
        :param initial_status_id: catégorie présélectionnée.
        """
        target = QLabel(selection_label)
        target.setObjectName("PanelTitle")
        target.setWordWrap(True)
        status_box = QGroupBox("1. Choisissez la catégorie")
        status_layout = QVBoxLayout(status_box)
        for index, status in enumerate(statuses):
            radio = QRadioButton(status.label)
            radio.setToolTip(status.description)
            hint = QLabel(status.description)
            hint.setObjectName("HintLabel")
            hint.setWordWrap(True)
            self._radio_group.addButton(radio, index)
            self._radios.append(radio)
            self._status_ids.append(status.status_id)
            status_layout.addWidget(radio)
            status_layout.addWidget(hint)
        initial = (self._status_ids.index(initial_status_id)
                   if initial_status_id in self._status_ids else 0)
        if self._radios:
            self._radios[initial].setChecked(True)
        reason_box = QGroupBox("2. Expliquez pourquoi")
        reason_layout = QVBoxLayout(reason_box)
        reason_layout.addWidget(self._text_edit)
        reason_layout.addWidget(self._same_code_check)
        layout = QVBoxLayout(self)
        layout.addWidget(target)
        layout.addWidget(status_box)
        layout.addWidget(reason_box, stretch=1)
        layout.addWidget(self._buttons)

    def _update_ok_state(self) -> None:
        """N'autorise la validation qu'avec un motif non vide."""
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(
            bool(self._text_edit.toPlainText().strip()))
