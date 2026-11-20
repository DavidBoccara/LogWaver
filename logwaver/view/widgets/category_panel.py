"""Panneau listant les catégories de classement et leurs effectifs."""

from __future__ import annotations

from typing import Optional, Sequence

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from logwaver.view_models import CategoryItem

KEY_ROLE: int = Qt.UserRole + 10
COLOR_ICON_SIZE: int = 12


class CategoryPanel(QWidget):
    """Liste des catégories ; émet ``category_selected(clé)`` au clic."""

    category_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit le panneau.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("CategoryPanel")
        self._list = QListWidget()
        self._list.setObjectName("CategoryList")
        title = QLabel("Catégories")
        title.setObjectName("PanelTitle")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)
        layout.addWidget(self._list)
        self._list.currentItemChanged.connect(self._on_current_changed)

    def set_categories(self, items: Sequence[CategoryItem], selected_key: str) -> None:
        """Affiche les catégories sans émettre de signal.

        :param items: catégories à afficher.
        :param selected_key: catégorie à sélectionner.
        """
        self._list.blockSignals(True)
        self._list.clear()
        for item in items:
            widget_item = QListWidgetItem(f"{item.label}  ({item.count})")
            widget_item.setData(KEY_ROLE, item.key)
            widget_item.setToolTip(item.tooltip)
            if item.color:
                widget_item.setIcon(self._color_icon(item.color))
            self._list.addItem(widget_item)
            if item.key == selected_key:
                self._list.setCurrentItem(widget_item)
        self._list.blockSignals(False)

    @staticmethod
    def _color_icon(color: str) -> QIcon:
        """Crée une pastille de couleur.

        :param color: couleur ``#RRGGBB``.
        :return: icône carrée unie.
        """
        pixmap = QPixmap(COLOR_ICON_SIZE, COLOR_ICON_SIZE)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def _on_current_changed(self, current: Optional[QListWidgetItem],
                            _previous: Optional[QListWidgetItem]) -> None:
        """Relaie le changement de catégorie.

        :param current: élément sélectionné.
        :param _previous: élément précédent (inutilisé).
        """
        if current is not None:
            self.category_selected.emit(str(current.data(KEY_ROLE)))
