"""Filtrage des éléments affichés (catégorie, type, code, texte libre)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from logwaver.constants import CATEGORY_ALL, CATEGORY_UNCLASSIFIED
from logwaver.model.entities import Justification, LogEntry


@dataclass(frozen=True)
class FilterCriteria:
    """Critères de filtrage de la vue principale.

    :param category: ``CATEGORY_ALL``, ``CATEGORY_UNCLASSIFIED`` ou un
        identifiant de catégorie.
    :param entry_type: type d'élément exigé (vide = tous).
    :param code_text: fragment de code recherché (insensible à la casse).
    :param file_text: fragment de nom de fichier recherché.
    :param free_text: fragment recherché dans la ligne brute et la
        justification.
    """

    category: str = CATEGORY_ALL
    entry_type: str = ""
    code_text: str = ""
    file_text: str = ""
    free_text: str = ""


class EntryFilter:
    """Applique des :class:`FilterCriteria` à une liste d'éléments."""

    def __init__(
        self, justification_of: Callable[[LogEntry], Optional[Justification]]
    ) -> None:
        """Initialise le filtre.

        :param justification_of: fonction retournant la justification d'un
            élément (ou ``None``).
        """
        self._justification_of = justification_of

    def apply(
        self, entries: Iterable[LogEntry], criteria: FilterCriteria
    ) -> List[LogEntry]:
        """Filtre une liste d'éléments.

        :param entries: éléments candidats.
        :param criteria: critères à respecter.
        :return: éléments retenus, ordre conservé.
        """
        return [entry for entry in entries if self._accepts(entry, criteria)]

    def _accepts(self, entry: LogEntry, criteria: FilterCriteria) -> bool:
        """Teste un élément contre tous les critères.

        :param entry: élément testé.
        :param criteria: critères à respecter.
        :return: ``True`` si l'élément est retenu.
        """
        justification = self._justification_of(entry)
        if not self._accepts_category(justification, criteria.category):
            return False
        if criteria.entry_type and entry.entry_type != criteria.entry_type:
            return False
        if not self._contains(entry.code, criteria.code_text):
            return False
        if not self._contains(entry.file_path, criteria.file_text):
            return False
        haystack = entry.raw_text
        if justification is not None:
            haystack = f"{haystack}\n{justification.text}\n{justification.author}"
        return self._contains(haystack, criteria.free_text)

    @staticmethod
    def _accepts_category(
        justification: Optional[Justification], category: str
    ) -> bool:
        """Teste la catégorie d'un élément.

        :param justification: justification de l'élément, si elle existe.
        :param category: catégorie demandée.
        :return: ``True`` si la catégorie correspond.
        """
        if category == CATEGORY_ALL:
            return True
        if category == CATEGORY_UNCLASSIFIED:
            return justification is None
        return justification is not None and justification.status_id == category

    @staticmethod
    def _contains(value: str, fragment: str) -> bool:
        """Recherche insensible à la casse (fragment vide = toujours vrai).

        :param value: texte analysé.
        :param fragment: fragment recherché.
        :return: ``True`` si le fragment est présent.
        """
        return not fragment or fragment.casefold() in value.casefold()
