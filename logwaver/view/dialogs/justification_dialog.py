"""Dialogue de classement : choix de la catégorie et saisie de la justification."""

from __future__ import annotations

from typing import Optional, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from logwaver.view_models import JustificationRequest, StatusChoice


class JustificationDialog(QDialog):
    """Demande une catégorie et une justification à l'utilisateur."""

    def __init__(
        self,
        statuses: Sequence[StatusChoice],
        selection_count: int,
        same_code_count: int,
        initial_status_id: str = "",
        initial_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Construit le dialogue.

        :param statuses: catégories proposées.
        :param selection_count: nombre d'éléments sélectionnés.
        :param same_code_count: éléments partageant le(s) même(s) code(s).
        :param initial_status_id: catégorie présélectionnée.
        :param initial_text: justification préremplie.
        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("JustificationDialog")
        self.setWindowTitle("Classer et justifier")
        self.setMinimumWidth(520)
        self._status_combo = QComboBox()
        for status in statuses:
            self._status_combo.addItem(status.label, status.status_id)
            self._status_combo.setItemData(
                self._status_combo.count() - 1, status.description, Qt.ToolTipRole
            )
        index = self._status_combo.findData(initial_status_id)
        self._status_combo.setCurrentIndex(max(index, 0))
        self._description_label = QLabel()
        self._description_label.setObjectName("HintLabel")
        self._description_label.setWordWrap(True)
        self._text_edit = QPlainTextEdit(initial_text)
        self._text_edit.setPlaceholderText("Expliquez pourquoi cet élément est classé ainsi…")
        self._same_code_check = QCheckBox(
            f"Appliquer à tous les éléments ayant le même code "
            f"({same_code_count} élément(s))"
        )
        self._same_code_check.setEnabled(same_code_count > selection_count)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._build_layout(selection_count)
        self._status_combo.currentIndexChanged.connect(self._update_description)
        self._text_edit.textChanged.connect(self._update_ok_state)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._update_description()
        self._update_ok_state()

    def request(self) -> JustificationRequest:
        """Retourne la saisie de l'utilisateur.

        :return: catégorie, texte et option d'extension au même code.
        """
        return JustificationRequest(
            status_id=str(self._status_combo.currentData()),
            text=self._text_edit.toPlainText().strip(),
            apply_to_same_code=self._same_code_check.isChecked(),
        )

    def _build_layout(self, selection_count: int) -> None:
        """Dispose les widgets.

        :param selection_count: nombre d'éléments sélectionnés.
        """
        form = QFormLayout()
        form.addRow("Catégorie :", self._status_combo)
        form.addRow("", self._description_label)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{selection_count} élément(s) sélectionné(s)."))
        layout.addLayout(form)
        layout.addWidget(QLabel("Justification :"))
        layout.addWidget(self._text_edit, stretch=1)
        layout.addWidget(self._same_code_check)
        layout.addWidget(self._buttons)

    def _update_description(self) -> None:
        """Affiche la description de la catégorie choisie."""
        index = self._status_combo.currentIndex()
        description = self._status_combo.itemData(index, Qt.ToolTipRole)
        self._description_label.setText(str(description or ""))

    def _update_ok_state(self) -> None:
        """N'autorise la validation qu'avec une justification non vide."""
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(
            bool(self._text_edit.toPlainText().strip())
        )
