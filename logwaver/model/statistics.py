"""Statistiques de synthèse calculées avec numpy (types × catégories)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import numpy as np

from logwaver.constants import CATEGORY_UNCLASSIFIED
from logwaver.model.entities import Justification, LogEntry


@dataclass(frozen=True)
class SummaryTable:
    """Tableau croisé du nombre d'éléments par type et par catégorie.

    :param type_names: lignes du tableau.
    :param category_ids: colonnes (``CATEGORY_UNCLASSIFIED`` en premier).
    :param counts: matrice d'entiers ``len(type_names) × len(category_ids)``.
    """

    type_names: Tuple[str, ...]
    category_ids: Tuple[str, ...]
    counts: np.ndarray

    @property
    def total(self) -> int:
        """Retourne le nombre total d'éléments."""
        return int(self.counts.sum())

    def column_totals(self) -> np.ndarray:
        """Retourne le total par catégorie."""
        return self.counts.sum(axis=0)

    def row_totals(self) -> np.ndarray:
        """Retourne le total par type."""
        return self.counts.sum(axis=1)

    def count_for_category(self, category_id: str) -> int:
        """Retourne le nombre d'éléments d'une catégorie.

        :param category_id: identifiant de catégorie.
        :return: nombre d'éléments (0 si inconnue).
        """
        if category_id not in self.category_ids:
            return 0
        return int(self.column_totals()[self.category_ids.index(category_id)])

    def justified_ratio(self) -> float:
        """Retourne la proportion d'éléments classés (0.0 à 1.0)."""
        if self.total == 0:
            return 0.0
        unclassified = self.count_for_category(CATEGORY_UNCLASSIFIED)
        return float(1.0 - unclassified / self.total)


class StatisticsCalculator:
    """Construit les tableaux de synthèse."""

    def __init__(
        self, justification_of: Callable[[LogEntry], Optional[Justification]]
    ) -> None:
        """Initialise le calculateur.

        :param justification_of: fonction donnant la justification d'un élément.
        """
        self._justification_of = justification_of

    def summarize(
        self,
        entries: Sequence[LogEntry],
        type_names: Sequence[str],
        status_ids: Sequence[str],
    ) -> SummaryTable:
        """Compte les éléments par type et par catégorie.

        :param entries: éléments à compter.
        :param type_names: types attendus (les types inconnus sont ajoutés).
        :param status_ids: catégories configurées.
        :return: tableau de synthèse.
        """
        all_types = list(type_names)
        for entry in entries:
            if entry.entry_type not in all_types:
                all_types.append(entry.entry_type)
        categories = [CATEGORY_UNCLASSIFIED, *status_ids]
        counts = np.zeros((len(all_types), len(categories)), dtype=np.int64)
        for entry in entries:
            justification = self._justification_of(entry)
            category = (justification.status_id if justification
                        else CATEGORY_UNCLASSIFIED)
            if category not in categories:
                categories.append(category)
                counts = np.pad(counts, ((0, 0), (0, 1)))
            counts[all_types.index(entry.entry_type),
                   categories.index(category)] += 1
        return SummaryTable(tuple(all_types), tuple(categories), counts)
