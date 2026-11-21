"""Arbre des éléments : liste à plat ou groupes repliables, sélection multiple.

Sélectionner une ligne de groupe revient à sélectionner tous les éléments du
groupe : c'est ce qui permet de justifier en une fois tous les éléments d'un
même fichier, d'un même code, etc.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set

from PyQt5.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, QPoint, Qt
from PyQt5.QtCore import QSortFilterProxyModel, pyqtSignal
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QTreeView, QWidget

from logwaver.view.entry_tree_model import (
    COLUMN_CODE,
    COLUMN_DESCRIPTION,
    COLUMN_LINE,
    COLUMN_TYPE,
    SORT_ROLE,
    EntryTreeModel,
)
from logwaver.view_models import EntryGroupView, EntryRow


class EntryTree(QTreeView):
    """Vue arborescente des éléments.

    Signaux :
    * ``entries_selected(list)`` : identifiants des éléments sélectionnés
      (les groupes sélectionnés sont développés en leurs éléments) ;
    * ``entry_activated()`` : double-clic sur un élément ;
    * ``context_menu_requested(QPoint)`` : clic droit (position globale).
    """

    entries_selected = pyqtSignal(list)
    entry_activated = pyqtSignal()
    context_menu_requested = pyqtSignal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit l'arbre et son modèle.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("EntryTree")
        self._source = EntryTreeModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._source)
        self._proxy.setSortRole(SORT_ROLE)
        self._proxy.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setModel(self._proxy)
        self._configure()
        self._proxy.layoutChanged.connect(self._span_group_rows)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.doubleClicked.connect(self._on_double_click)
        self.customContextMenuRequested.connect(
            lambda position: self.context_menu_requested.emit(
                self.viewport().mapToGlobal(position)))

    # ================================================================== API
    def set_flat_rows(self, rows: Sequence[EntryRow]) -> None:
        """Affiche les éléments à plat en conservant la sélection.

        :param rows: lignes à afficher.
        """
        selected_ids, selected_groups, _ = self._capture_state()
        self.selectionModel().blockSignals(True)
        self._source.set_flat_rows(rows)
        self.setRootIsDecorated(False)
        self._restore_state(selected_ids, selected_groups, set())
        self.selectionModel().blockSignals(False)
        self._emit_selection()

    def set_groups(self, groups: Sequence[EntryGroupView]) -> None:
        """Affiche des groupes repliables en conservant dépliage et sélection.

        :param groups: groupes à afficher.
        """
        selected_ids, selected_groups, expanded = self._capture_state()
        self.selectionModel().blockSignals(True)
        self._source.set_groups(groups)
        self.setRootIsDecorated(True)
        self._span_group_rows()
        self._restore_state(selected_ids, selected_groups, expanded)
        self.selectionModel().blockSignals(False)
        self._emit_selection()

    def selected_entry_ids(self) -> List[int]:
        """Retourne les éléments sélectionnés, groupes développés.

        :return: identifiants uniques, dans l'ordre d'affichage.
        """
        ordered: Dict[int, None] = {}
        for index in sorted(self.selectionModel().selectedRows(0),
                            key=lambda i: (self._top_row(i), i.row())):
            entry_id = EntryTreeModel.entry_id(index)
            if entry_id is not None:
                ordered[entry_id] = None
                continue
            for child_row in range(self._proxy.rowCount(index)):
                child_id = EntryTreeModel.entry_id(self._proxy.index(child_row, 0, index))
                if child_id is not None:
                    ordered[child_id] = None
        return list(ordered)

    def selected_group_values(self) -> List[str]:
        """Retourne les valeurs des groupes sélectionnés.

        :return: valeurs des lignes de groupe sélectionnées.
        """
        values = [EntryTreeModel.group_value(index)
                  for index in self.selectionModel().selectedRows(0)]
        return [value for value in values if value is not None]

    def select_first_row(self) -> None:
        """Sélectionne la première ligne (groupe ou élément)."""
        if self._proxy.rowCount():
            self.setCurrentIndex(self._proxy.index(0, 0))
            self.selectionModel().select(
                self._proxy.index(0, 0),
                QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

    @property
    def row_count(self) -> int:
        """Retourne le nombre de lignes de premier niveau."""
        return self._proxy.rowCount()

    # ============================================================== interne
    def _configure(self) -> None:
        """Règle l'apparence et le comportement de l'arbre."""
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.setAllColumnsShowFocus(True)
        self.setRootIsDecorated(False)
        self.setExpandsOnDoubleClick(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(COLUMN_DESCRIPTION, QHeaderView.Stretch)
        for column in (COLUMN_TYPE, COLUMN_CODE, COLUMN_LINE):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.sortByColumn(COLUMN_TYPE, Qt.AscendingOrder)

    def _span_group_rows(self) -> None:
        """Étend le libellé des groupes sur toute la largeur."""
        grouped = self._source.is_grouped
        for row in range(self._proxy.rowCount()):
            self.setFirstColumnSpanned(row, QModelIndex(), grouped)

    def _capture_state(self) -> tuple:
        """Mémorise sélection et groupes dépliés avant un rafraîchissement.

        :return: (identifiants sélectionnés, groupes sélectionnés, groupes dépliés).
        """
        selected_ids: Set[int] = set()
        for index in self.selectionModel().selectedRows(0):
            entry_id = EntryTreeModel.entry_id(index)
            if entry_id is not None:
                selected_ids.add(entry_id)
        expanded: Set[str] = set()
        for row in range(self._proxy.rowCount()):
            index = self._proxy.index(row, 0)
            value = EntryTreeModel.group_value(index)
            if value is not None and self.isExpanded(index):
                expanded.add(value)
        return selected_ids, set(self.selected_group_values()), expanded

    def _restore_state(self, selected_ids: Set[int], selected_groups: Set[str],
                       expanded: Set[str]) -> None:
        """Rétablit sélection et dépliage après un rafraîchissement.

        :param selected_ids: éléments précédemment sélectionnés.
        :param selected_groups: groupes précédemment sélectionnés.
        :param expanded: groupes précédemment dépliés.
        """
        selection = QItemSelection()
        for row in range(self._proxy.rowCount()):
            index = self._proxy.index(row, 0)
            group = EntryTreeModel.group_value(index)
            if group is None:
                if EntryTreeModel.entry_id(index) in selected_ids:
                    selection.select(index, index)
                continue
            if group in expanded:
                self.expand(index)
            if group in selected_groups:
                selection.select(index, index)
            for child_row in range(self._proxy.rowCount(index)):
                child = self._proxy.index(child_row, 0, index)
                if EntryTreeModel.entry_id(child) in selected_ids:
                    selection.select(child, child)
        self.selectionModel().select(
            selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

    @staticmethod
    def _top_row(index: QModelIndex) -> int:
        """Retourne la ligne de premier niveau contenant un index.

        :param index: index quelconque.
        :return: numéro de ligne de premier niveau.
        """
        return index.parent().row() if index.parent().isValid() else index.row()

    def _on_selection_changed(self, _selected: QItemSelection,
                              _deselected: QItemSelection) -> None:
        """Relaie un changement de sélection.

        :param _selected: plages sélectionnées (inutilisées).
        :param _deselected: plages désélectionnées (inutilisées).
        """
        self._emit_selection()

    def _emit_selection(self) -> None:
        """Émet les éléments sélectionnés."""
        self.entries_selected.emit(self.selected_entry_ids())

    def _on_double_click(self, index: QModelIndex) -> None:
        """Double-clic sur un élément : demande sa justification.

        Sur un groupe, le double-clic garde son rôle habituel (déplier).

        :param index: cellule double-cliquée.
        """
        if EntryTreeModel.entry_id(index) is not None:
            self.entry_activated.emit()
