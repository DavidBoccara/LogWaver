"""Adaptateurs Qt (QAbstractTableModel) pour la table des éléments."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PyQt5.QtGui import QBrush, QColor

from logwaver.view_models import EntryRow

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


class EntryTableModel(QAbstractTableModel):
    """Expose une liste de :class:`EntryRow` à une ``QTableView``."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Crée un modèle vide.

        :param parent: objet Qt parent.
        """
        super().__init__(parent)
        self._rows: List[EntryRow] = []

    def set_rows(self, rows: Sequence[EntryRow]) -> None:
        """Remplace toutes les lignes affichées.

        :param rows: nouvelles lignes.
        """
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> Optional[EntryRow]:
        """Retourne la ligne à une position.

        :param row: index de ligne.
        :return: ligne, ou ``None`` si hors limites.
        """
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        """Retourne le nombre de lignes (API Qt).

        :param parent: index parent (inutilisé : modèle plat).
        :return: nombre de lignes.
        """
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        """Retourne le nombre de colonnes (API Qt).

        :param parent: index parent (inutilisé).
        :return: nombre de colonnes.
        """
        return 0 if parent.isValid() else len(COLUMN_TITLES)

    def headerData(self, section: int, orientation: Qt.Orientation,  # noqa: N802
                   role: int = Qt.DisplayRole) -> Any:
        """Retourne les titres de colonnes (API Qt).

        :param section: index de colonne ou de ligne.
        :param orientation: orientation de l'en-tête.
        :param role: rôle Qt demandé.
        :return: titre, ou ``None``.
        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMN_TITLES[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Retourne la donnée d'une cellule pour un rôle (API Qt).

        :param index: cellule.
        :param role: rôle Qt demandé.
        :return: valeur, ou ``None``.
        """
        row = self.row_at(index.row()) if index.isValid() else None
        if row is None:
            return None
        column = index.column()
        if role == Qt.DisplayRole:
            return self._display_value(row, column)
        if role == Qt.ToolTipRole and column == COLUMN_DESCRIPTION:
            return row.description
        if role == SORT_ROLE:
            if column == COLUMN_LINE and row.line.isdigit():
                return int(row.line)
            return self._display_value(row, column).casefold()
        if role == ENTRY_ID_ROLE:
            return row.entry_id
        if role == Qt.BackgroundRole and column == COLUMN_STATUS and row.status_color:
            color = QColor(row.status_color)
            color.setAlpha(STATUS_BACKGROUND_ALPHA)
            return QBrush(color)
        return None

    @staticmethod
    def _display_value(row: EntryRow, column: int) -> str:
        """Retourne le texte affiché dans une colonne.

        :param row: ligne concernée.
        :param column: index de colonne.
        :return: texte de la cellule.
        """
        values = (row.entry_type, row.code, row.file_name, row.line,
                  row.description, row.status_label, row.author, row.log_name)
        return values[column]
