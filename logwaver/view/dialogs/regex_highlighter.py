"""Coloration des correspondances de regex et des sélections dans l'exemple."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt5.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument

MATCH_COLOR: str = "#ffe08a"
MARK_COLOR: str = "#a8d8ff"
IGNORED_COLOR: str = "#d9d9d9"

Ranges = Dict[int, List[Tuple[int, int]]]


class RegexHighlighter(QSyntaxHighlighter):
    """Surligne des plages de caractères fournies par le présentateur.

    Deux couches : les correspondances du test (jaune) et les sélections
    marquées pour la génération automatique (bleu).
    """

    def __init__(self, document: QTextDocument) -> None:
        """Attache le surligneur à un document.

        :param document: document à colorer.
        """
        super().__init__(document)
        self._match_ranges: Ranges = {}
        self._mark_ranges: Ranges = {}
        self._ignored_ranges: Ranges = {}
        self._match_format = self._make_format(MATCH_COLOR)
        self._mark_format = self._make_format(MARK_COLOR)
        self._ignored_format = self._make_format(IGNORED_COLOR)

    def set_match_ranges(self, ranges: Ranges) -> None:
        """Définit les correspondances à surligner.

        :param ranges: n° de ligne (1-based) → plages (début, fin).
        """
        self._match_ranges = ranges
        self.rehighlight()

    def set_mark_ranges(self, ranges: Ranges) -> None:
        """Définit les sélections marquées à surligner.

        :param ranges: n° de ligne (1-based) → plages (début, fin).
        """
        self._mark_ranges = ranges
        self.rehighlight()

    def set_ignored_ranges(self, ranges: Ranges) -> None:
        """Définit les parties variables ignorées à griser.

        :param ranges: n° de ligne (1-based) → plages (début, fin).
        """
        self._ignored_ranges = ranges
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        """Colore une ligne du document (API Qt).

        :param text: texte de la ligne.
        """
        line_number = self.currentBlock().blockNumber() + 1
        self._apply(self._match_ranges.get(line_number), self._match_format, len(text))
        self._apply(self._mark_ranges.get(line_number), self._mark_format, len(text))
        self._apply(self._ignored_ranges.get(line_number), self._ignored_format, len(text))

    def _apply(self, ranges: Optional[List[Tuple[int, int]]],
               text_format: QTextCharFormat, length: int) -> None:
        """Applique un format à des plages bornées à la ligne.

        :param ranges: plages à colorer.
        :param text_format: format à appliquer.
        :param length: longueur de la ligne.
        """
        for start, end in ranges or ():
            start = max(0, min(start, length))
            end = max(start, min(end, length))
            if end > start:
                self.setFormat(start, end - start, text_format)

    @staticmethod
    def _make_format(color: str) -> QTextCharFormat:
        """Crée un format de fond coloré.

        :param color: couleur ``#RRGGBB``.
        :return: format de texte.
        """
        text_format = QTextCharFormat()
        text_format.setBackground(QColor(color))
        return text_format
