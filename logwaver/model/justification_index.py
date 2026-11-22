"""Index des justifications selon les règles de correspondance courantes.

Chaque justification est stockée sous un identifiant stable (empreinte
« stricte ») avec le contexte de l'élément justifié. L'index recalcule, pour
les règles de correspondance choisies, la clé de comparaison de chaque
justification. Plusieurs justifications peuvent alors partager une clé
(règles assouplies, import d'un collègue) : la plus prioritaire l'emporte,
puis, à priorité égale, la plus récente.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Tuple

from logwaver.model.entities import Justification
from logwaver.model.fingerprint import FingerprintBuilder

PriorityFunction = Callable[[str], int]


class JustificationIndex:
    """Associe une clé de comparaison à la justification qui s'applique."""

    def __init__(self, builder: FingerprintBuilder, priority_of: PriorityFunction) -> None:
        """Crée un index vide.

        :param builder: calculateur d'empreintes (règles courantes).
        :param priority_of: priorité d'une catégorie.
        """
        self._builder = builder
        self._priority_of = priority_of
        self._best: Dict[str, Justification] = {}
        self._rule_ids: Dict[str, List[str]] = {}

    def rebuild(self, justifications: Iterable[Justification]) -> None:
        """Recalcule l'index à partir de toutes les justifications stockées.

        :param justifications: justifications du dépôt.
        """
        self._best.clear()
        self._rule_ids.clear()
        for justification in justifications:
            key = self.key_of(justification)
            self._rule_ids.setdefault(key, []).append(justification.fingerprint)
            current = self._best.get(key)
            if current is None or self.rank(justification) > self.rank(current):
                self._best[key] = justification

    def key_of(self, justification: Justification) -> str:
        """Calcule la clé de comparaison d'une justification.

        Une justification sans contexte (format très ancien) garde son
        identifiant comme clé.

        :param justification: justification concernée.
        :return: clé de comparaison.
        """
        if not justification.context:
            return justification.fingerprint
        return self._builder.build_from_context(justification.context)

    def best(self, key: str) -> Optional[Justification]:
        """Retourne la justification retenue pour une clé.

        :param key: clé de comparaison d'un élément.
        :return: justification retenue, ou ``None``.
        """
        return self._best.get(key)

    def rule_ids(self, key: str) -> List[str]:
        """Retourne les identifiants de toutes les justifications d'une clé.

        :param key: clé de comparaison.
        :return: identifiants (vide si aucune).
        """
        return list(self._rule_ids.get(key, ()))

    def rank(self, justification: Justification) -> Tuple[int, str]:
        """Ordre de préséance : priorité de la catégorie, puis date.

        :param justification: justification évaluée.
        :return: couple comparable (le plus grand l'emporte).
        """
        return self._priority_of(justification.status_id), justification.timestamp

    def is_retained(self, justification: Justification) -> bool:
        """Indique si une justification est celle retenue pour sa clé.

        :param justification: justification évaluée.
        :return: ``True`` si elle s'applique effectivement.
        """
        best = self._best.get(self.key_of(justification))
        return best is not None and best.fingerprint == justification.fingerprint
