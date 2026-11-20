"""Barre de filtres de la vue principale."""

from __future__ import annotations

from typing import Optional, Sequence

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

ALL_TYPES_LABEL: str = "Tous les types"
FILTER_DEBOUNCE_MS: int = 200


class FilterBar(QWidget):
    """Champs de filtrage : texte libre, type, code et fichier.

    Signal ``filter_changed(texte, type, code, fichier)`` émis (avec un
    léger délai anti-rebond) à chaque modification.
    """

    filter_changed = pyqtSignal(str, str, str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit la barre.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("FilterBar")
        self._text_edit = QLineEdit()
        self._text_edit.setPlaceholderText("Rechercher (message, justification, auteur)…")
        self._text_edit.setClearButtonEnabled(True)
        self._type_combo = QComboBox()
        self._code_edit = QLineEdit()
        self._code_edit.setPlaceholderText("Code")
        self._code_edit.setClearButtonEnabled(True)
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Fichier")
        self._file_edit.setClearButtonEnabled(True)
        self._reset_button = QPushButton("Effacer les filtres")
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(FILTER_DEBOUNCE_MS)
        self._build_layout()
        self._connect_signals()
        self.set_type_options(())

    def set_type_options(self, type_names: Sequence[str]) -> None:
        """Met à jour la liste des types proposés.

        :param type_names: types disponibles.
        """
        current = self._type_combo.currentData()
        self._type_combo.blockSignals(True)
        self._type_combo.clear()
        self._type_combo.addItem(ALL_TYPES_LABEL, "")
        for name in type_names:
            self._type_combo.addItem(name, name)
        index = self._type_combo.findData(current)
        self._type_combo.setCurrentIndex(max(index, 0))
        self._type_combo.blockSignals(False)

    def focus_search(self) -> None:
        """Place le curseur dans le champ de recherche."""
        self._text_edit.setFocus()
        self._text_edit.selectAll()

    def _build_layout(self) -> None:
        """Dispose les widgets horizontalement."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Filtres :"))
        layout.addWidget(self._text_edit, stretch=3)
        layout.addWidget(self._type_combo, stretch=1)
        layout.addWidget(self._code_edit, stretch=1)
        layout.addWidget(self._file_edit, stretch=1)
        layout.addWidget(self._reset_button)

    def _connect_signals(self) -> None:
        """Relie les modifications au minuteur anti-rebond."""
        for edit in (self._text_edit, self._code_edit, self._file_edit):
            edit.textChanged.connect(self._debounce.start)
        self._type_combo.currentIndexChanged.connect(self._emit_filter)
        self._debounce.timeout.connect(self._emit_filter)
        self._reset_button.clicked.connect(self._reset)

    def _reset(self) -> None:
        """Vide tous les filtres."""
        for edit in (self._text_edit, self._code_edit, self._file_edit):
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        self._type_combo.blockSignals(True)
        self._type_combo.setCurrentIndex(0)
        self._type_combo.blockSignals(False)
        self._emit_filter()

    def _emit_filter(self) -> None:
        """Émet les critères courants."""
        self.filter_changed.emit(
            self._text_edit.text().strip(),
            self._type_combo.currentData() or "",
            self._code_edit.text().strip(),
            self._file_edit.text().strip(),
        )
