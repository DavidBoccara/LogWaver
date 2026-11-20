"""Visionneuse de fichier source positionnée sur la ligne d'un élément."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFontDatabase,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCursor,
    QTextFormat,
)
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

LINE_HIGHLIGHT_COLOR: str = "#fff3a0"
GUTTER_PADDING: int = 6


class _LineNumberArea(QWidget):
    """Marge affichant les numéros de ligne d'un :class:`CodeViewer`."""

    def __init__(self, viewer: "CodeViewer") -> None:
        """Crée la marge.

        :param viewer: éditeur associé.
        """
        super().__init__(viewer)
        self.setObjectName("LineNumberArea")
        self._viewer = viewer

    def sizeHint(self) -> QSize:  # noqa: N802
        """Retourne la largeur nécessaire (API Qt).

        :return: taille recommandée.
        """
        return QSize(self._viewer.gutter_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Délègue le dessin à l'éditeur (API Qt).

        :param event: événement de dessin.
        """
        self._viewer.paint_gutter(event)


class CodeViewer(QPlainTextEdit):
    """Éditeur en lecture seule avec numéros de ligne."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Crée la visionneuse.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("CodeViewer")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self._gutter = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._on_update_request)
        self._update_margin()

    def gutter_width(self) -> int:
        """Calcule la largeur de la marge selon le nombre de lignes.

        :return: largeur en pixels.
        """
        digits = len(str(max(1, self.blockCount())))
        return GUTTER_PADDING * 2 + self.fontMetrics().horizontalAdvance("9") * digits

    def go_to_line(self, line: int) -> None:
        """Positionne le curseur et surligne une ligne.

        :param line: numéro de ligne (1 = première).
        """
        block = self.document().findBlockByNumber(max(line - 1, 0))
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.centerCursor()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(LINE_HIGHLIGHT_COLOR))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = cursor
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def paint_gutter(self, event: QPaintEvent) -> None:
        """Dessine les numéros de ligne visibles.

        :param event: événement de dessin de la marge.
        """
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), self.palette().alternateBase())
        painter.setPen(self.palette().placeholderText().color())
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                painter.drawText(0, top, self._gutter.width() - GUTTER_PADDING, height,
                                 Qt.AlignRight, str(block.blockNumber() + 1))
            top += int(self.blockBoundingRect(block).height())
            block = block.next()
        painter.end()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Repositionne la marge lors d'un redimensionnement (API Qt).

        :param event: événement de redimensionnement.
        """
        super().resizeEvent(event)
        rect = self.contentsRect()
        self._gutter.setGeometry(QRect(rect.left(), rect.top(),
                                       self.gutter_width(), rect.height()))

    def _update_margin(self) -> None:
        """Réserve la place de la marge à gauche du texte."""
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _on_update_request(self, rect: QRect, dy: int) -> None:
        """Synchronise la marge avec le défilement.

        :param rect: zone à redessiner.
        :param dy: décalage vertical.
        """
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())


class SourceViewerDialog(QDialog):
    """Affiche un fichier source sur la ligne citée par un élément.

    Signal ``external_editor_requested`` : ouvrir dans l'éditeur externe.
    """

    external_editor_requested = pyqtSignal()

    def __init__(self, path_text: str, content: str, line: int,
                 external_editor_available: bool,
                 parent: Optional[QWidget] = None) -> None:
        """Construit la visionneuse.

        :param path_text: chemin affiché.
        :param content: contenu du fichier.
        :param line: ligne à atteindre.
        :param external_editor_available: affiche le bouton d'éditeur externe.
        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("SourceViewerDialog")
        self.setWindowTitle(f"{path_text} - ligne {line}")
        self.resize(950, 650)
        self._viewer = CodeViewer()
        self._viewer.setPlainText(content)
        external_button = QPushButton("Ouvrir dans l'éditeur externe")
        external_button.setVisible(external_editor_available)
        external_button.clicked.connect(self.external_editor_requested)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)
        header = QLabel(path_text)
        header.setObjectName("PanelTitle")
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(external_button)
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self._viewer, stretch=1)
        layout.addLayout(buttons)
        self._viewer.go_to_line(line)
