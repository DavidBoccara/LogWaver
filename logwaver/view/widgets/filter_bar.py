"""Barre de recherche, de regroupement et de filtres de la vue principale."""

from __future__ import annotations

from typing import Optional, Sequence

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from logwaver.view_models import GroupingChoice

ALL_TYPES_LABEL: str = "Tous les types"
FILTER_DEBOUNCE_MS: int = 200
MORE_FILTERS_LABEL: str = "Plus de filtres ▾"
LESS_FILTERS_LABEL: str = "Moins de filtres ▴"


class FilterBar(QWidget):
    """Recherche, regroupement et filtres avancés (repliés par défaut).

    Signaux :
    * ``filter_changed(texte, type, code, fichier)`` (avec anti-rebond) ;
    * ``grouping_changed(clé)`` : critère de regroupement choisi ;
    * ``expand_all_requested`` / ``collapse_all_requested``.
    """

    filter_changed = pyqtSignal(str, str, str, str)
    grouping_changed = pyqtSignal(str)
    expand_all_requested = pyqtSignal()
    collapse_all_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit la barre.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("FilterBar")
        self._text_edit = QLineEdit()
        self._text_edit.setObjectName("SearchEdit")
        self._text_edit.setPlaceholderText("🔍 Rechercher un message, un code, une justification…")
        self._text_edit.setClearButtonEnabled(True)
        self._grouping_combo = QComboBox()
        self._grouping_combo.setObjectName("GroupingCombo")
        self._grouping_combo.setToolTip(
            "Regroupe les éléments qui ont la même valeur (même code, même fichier…).\n"
            "Sélectionnez ensuite un groupe pour le justifier en une seule fois.")
        self._expand_button = QPushButton("Tout déplier")
        self._collapse_button = QPushButton("Tout replier")
        self._more_button = QPushButton(MORE_FILTERS_LABEL)
        self._more_button.setCheckable(True)
        self._type_combo = QComboBox()
        self._code_edit = QLineEdit()
        self._code_edit.setPlaceholderText("Code contient…")
        self._code_edit.setClearButtonEnabled(True)
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Fichier contient…")
        self._file_edit.setClearButtonEnabled(True)
        self._reset_button = QPushButton("Effacer les filtres")
        self._advanced = QWidget()
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(FILTER_DEBOUNCE_MS)
        self._build_layout()
        self._connect_signals()
        self.set_type_options(())
        self._advanced.setVisible(False)
        self._set_group_buttons_enabled(False)

    # ================================================================== API
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
        self._type_combo.setCurrentIndex(max(self._type_combo.findData(current), 0))
        self._type_combo.blockSignals(False)

    def set_grouping_options(self, choices: Sequence[GroupingChoice], current: str) -> None:
        """Met à jour les critères de regroupement sans émettre de signal.

        :param choices: critères disponibles.
        :param current: critère sélectionné.
        """
        self._grouping_combo.blockSignals(True)
        self._grouping_combo.clear()
        for choice in choices:
            self._grouping_combo.addItem(choice.label, choice.key)
        self._grouping_combo.setCurrentIndex(max(self._grouping_combo.findData(current), 0))
        self._grouping_combo.blockSignals(False)
        self._set_group_buttons_enabled(self._grouping_combo.currentIndex() > 0)

    def select_grouping(self, key: str) -> None:
        """Choisit un critère de regroupement comme si l'utilisateur l'avait fait.

        :param key: critère à sélectionner.
        """
        index = self._grouping_combo.findData(key)
        if index >= 0:
            self._grouping_combo.setCurrentIndex(index)

    def focus_search(self) -> None:
        """Place le curseur dans le champ de recherche."""
        self._text_edit.setFocus()
        self._text_edit.selectAll()

    # ============================================================== interne
    def _build_layout(self) -> None:
        """Dispose la ligne principale puis la ligne des filtres avancés."""
        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.addWidget(self._text_edit, stretch=3)
        main_row.addWidget(QLabel("Regrouper par :"))
        main_row.addWidget(self._grouping_combo, stretch=1)
        main_row.addWidget(self._expand_button)
        main_row.addWidget(self._collapse_button)
        main_row.addWidget(self._more_button)
        advanced_row = QHBoxLayout(self._advanced)
        advanced_row.setContentsMargins(0, 0, 0, 0)
        advanced_row.addWidget(QLabel("Type :"))
        advanced_row.addWidget(self._type_combo, stretch=1)
        advanced_row.addWidget(self._code_edit, stretch=1)
        advanced_row.addWidget(self._file_edit, stretch=1)
        advanced_row.addWidget(self._reset_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(main_row)
        layout.addWidget(self._advanced)

    def _connect_signals(self) -> None:
        """Relie les widgets aux signaux publics."""
        for edit in (self._text_edit, self._code_edit, self._file_edit):
            edit.textChanged.connect(self._debounce.start)
        self._type_combo.currentIndexChanged.connect(self._emit_filter)
        self._debounce.timeout.connect(self._emit_filter)
        self._reset_button.clicked.connect(self._reset)
        self._more_button.toggled.connect(self._toggle_advanced)
        self._grouping_combo.currentIndexChanged.connect(self._emit_grouping)
        self._expand_button.clicked.connect(self.expand_all_requested)
        self._collapse_button.clicked.connect(self.collapse_all_requested)

    def _toggle_advanced(self, visible: bool) -> None:
        """Affiche ou masque les filtres avancés.

        :param visible: ``True`` pour afficher.
        """
        self._advanced.setVisible(visible)
        self._more_button.setText(LESS_FILTERS_LABEL if visible else MORE_FILTERS_LABEL)

    def _set_group_buttons_enabled(self, enabled: bool) -> None:
        """Active les boutons de dépliage seulement en mode groupé.

        :param enabled: ``True`` si un regroupement est actif.
        """
        self._expand_button.setEnabled(enabled)
        self._collapse_button.setEnabled(enabled)

    def _emit_grouping(self) -> None:
        """Émet le critère de regroupement courant."""
        self._set_group_buttons_enabled(self._grouping_combo.currentIndex() > 0)
        self.grouping_changed.emit(str(self._grouping_combo.currentData() or ""))

    def _reset(self) -> None:
        """Vide tous les filtres (le regroupement est conservé)."""
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
