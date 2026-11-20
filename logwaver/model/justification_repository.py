"""Base des règles de justification (empreinte → justification)."""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional

from logwaver.model.entities import Justification


class JustificationRepository:
    """Stocke les justifications indexées par empreinte.

    Le dépôt ne fait aucune hypothèse sur les éléments du log : il peut
    contenir des justifications d'éléments absents du log courant (règles
    héritées ou problèmes clôturés).
    """

    def __init__(self) -> None:
        """Crée un dépôt vide."""
        self._items: Dict[str, Justification] = {}

    def get(self, fingerprint: str) -> Optional[Justification]:
        """Retourne la justification d'une empreinte.

        :param fingerprint: empreinte recherchée.
        :return: justification, ou ``None`` si l'empreinte n'est pas justifiée.
        """
        return self._items.get(fingerprint)

    def put(self, justification: Justification) -> None:
        """Ajoute ou remplace une justification.

        :param justification: justification à enregistrer.
        """
        self._items[justification.fingerprint] = justification

    def remove(self, fingerprint: str) -> None:
        """Supprime une justification si elle existe.

        :param fingerprint: empreinte à libérer.
        """
        self._items.pop(fingerprint, None)

    def apply(self, changes: Mapping[str, Optional[Justification]]) -> None:
        """Applique un lot de modifications.

        :param changes: empreinte → nouvelle justification (``None`` = retrait).
        """
        for fingerprint, justification in changes.items():
            if justification is None:
                self.remove(fingerprint)
            else:
                self.put(justification)

    def snapshot(self, fingerprints: Iterable[str]) -> Dict[str, Optional[Justification]]:
        """Capture l'état actuel d'un ensemble d'empreintes.

        :param fingerprints: empreintes à capturer.
        :return: empreinte → justification actuelle (ou ``None``).
        """
        return {fp: self._items.get(fp) for fp in fingerprints}

    def all(self) -> List[Justification]:
        """Retourne toutes les justifications, triées par date.

        :return: liste des justifications.
        """
        return sorted(self._items.values(), key=lambda item: item.timestamp)

    def replace_all(self, justifications: Iterable[Justification]) -> None:
        """Remplace intégralement le contenu du dépôt.

        :param justifications: nouvelles justifications.
        """
        self._items = {item.fingerprint: item for item in justifications}

    def __len__(self) -> int:
        """Retourne le nombre de justifications stockées."""
        return len(self._items)

    def __contains__(self, fingerprint: object) -> bool:
        """Indique si une empreinte est justifiée."""
        return fingerprint in self._items
