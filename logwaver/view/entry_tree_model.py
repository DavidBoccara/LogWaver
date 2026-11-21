"""Modèle Qt de l'arbre des éléments : liste à plat ou groupes repliables."""

from __future__ import annotations

from typing import List, Optional, Sequence

from PyQt5.QtCore import QModelIndex, QObject, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QStandardItem, QStandardItemModel

from logwaver.view_models import EntryGroupView, EntryRow

COLUMN_TYPE: int = 0
COLUMN_CODE: int = 1
COLUMN_FILE: int = 2
COLUMN_LINE: int = 3
COLUMN_DESCRIPTION: int = 4
COLUMN_STATUS: int = 5
COLUMN_AUTHOR: int = 6
COLUMN_LOG: int = 7
COLUMN_TITLES: tuple = ("Type", "Code", "Fichier", "Ligne", "Description",
                        "Catégorie", "Auteur", "Log")
STATUS_BACKGROUND_ALPHA: int = 70
SORT_ROLE: int = Qt.UserRole + 1
ENTRY_ID_ROLE: int = Qt.UserRole + 2
GROUP_VALUE_ROLE: int = Qt.UserRole + 3


def group_label(group: EntryGroupView) -> str:
    """Construit le libellé d'une ligne de groupe.

    :param group: groupe affiché.
    :return: libellé (valeur, effectif, non justifiés).
    """
    total = len(group.rows)
    pending = f", {group.unclassified} non justifié(s)" if group.unclassified else ""
    return f"{group.value}    —    {total} élément(s){pending}"


class EntryTreeModel(QStandardItemModel):
    """Expose les éléments à une ``QTreeView``, groupés ou non."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Crée un modèle vide avec ses titres de colonnes.

        :param parent: objet Qt parent.
        """
        super().__init__(parent)
        self._grouped: bool = False
        self.setHorizontalHeaderLabels(list(COLUMN_TITLES))

    @property
    def is_grouped(self) -> bool:
        """Indique si le contenu courant est groupé."""
        return self._grouped

    def set_flat_rows(self, rows: Sequence[EntryRow]) -> None:
        """Affiche une liste à plat.

        :param rows: lignes à afficher.
        """
        self._reset(grouped=False)
        root = self.invisibleRootItem()
        for row in rows:
            root.appendRow(self._entry_items(row))

    def set_groups(self, groups: Sequence[EntryGroupView]) -> None:
        """Affiche des groupes repliables contenant leurs éléments.

        :param groups: groupes à afficher.
        """
        self._reset(grouped=True)
        root = self.invisibleRootItem()
        for group in groups:
            group_items = self._group_items(group)
            for row in group.rows:
                group_items[0].appendRow(self._entry_items(row))
            root.appendRow(group_items)

    @staticmethod
    def entry_id(index: QModelIndex) -> Optional[int]:
        """Retourne l'identifiant de l'élément d'une ligne.

        :param index: index d'une cellule (modèle source ou proxy).
        :return: identifiant, ou ``None`` pour une ligne de groupe.
        """
        value = index.sibling(index.row(), 0).data(ENTRY_ID_ROLE)
        return None if value is None else int(value)

    @staticmethod
    def group_value(index: QModelIndex) -> Optional[str]:
        """Retourne la valeur du groupe d'une ligne de groupe.

        :param index: index d'une cellule (modèle source ou proxy).
        :return: valeur du groupe, ou ``None`` pour une ligne d'élément.
        """
        value = index.sibling(index.row(), 0).data(GROUP_VALUE_ROLE)
        return None if value is None else str(value)

    def _reset(self, grouped: bool) -> None:
        """Vide le modèle en conservant les titres de colonnes.

        :param grouped: mode d'affichage à venir.
        """
        self.removeRows(0, self.rowCount())
        self._grouped = grouped

    @staticmethod
    def _group_items(group: EntryGroupView) -> List[QStandardItem]:
        """Crée les cellules d'une ligne de groupe.

        Le libellé est porté par la première colonne, que la vue étend sur
        toute la largeur ; les autres cellules ne servent qu'au tri.

        :param group: groupe affiché.
        :return: cellules de la ligne.
        """
        items: List[QStandardItem] = []
        for column in range(len(COLUMN_TITLES)):
            item = QStandardItem(group_label(group) if column == 0 else "")
            item.setEditable(False)
            item.setData(group.value, GROUP_VALUE_ROLE)
            item.setData(group.value.casefold(), SORT_ROLE)
            items.append(item)
        # Mise en évidence sémantique des lignes de groupe (aucune feuille QSS
        # ne permet de cibler une ligne précise d'un arbre).
        font = QFont()
        font.setBold(True)
        items[0].setFont(font)
        items[0].setToolTip(f"{group.value}\nSélectionnez cette ligne pour traiter "
                            "tout le groupe en une fois.")
        return items

    @staticmethod
    def _entry_items(row: EntryRow) -> List[QStandardItem]:
        """Crée les cellules d'une ligne d'élément.

        :param row: élément affiché.
        :return: cellules de la ligne.
        """
        values = (row.entry_type, row.code, row.file_name, row.line, row.description,
                  row.status_label, row.author, row.log_name)
        items: List[QStandardItem] = []
        for column, text in enumerate(values):
            item = QStandardItem(text)
            item.setEditable(False)
            item.setData(row.entry_id, ENTRY_ID_ROLE)
            sort_value = int(text) if column == COLUMN_LINE and text.isdigit() else text.casefold()
            item.setData(sort_value, SORT_ROLE)
            items.append(item)
        items[COLUMN_DESCRIPTION].setToolTip(row.description)
        if row.status_color:
            color = QColor(row.status_color)
            color.setAlpha(STATUS_BACKGROUND_ALPHA)
            items[COLUMN_STATUS].setBackground(QBrush(color))
        return items
