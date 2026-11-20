"""Pile d'annulation (Ctrl+Z / Ctrl+Y) indépendante de Qt (patron Commande)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Mapping, Optional

from logwaver.model.entities import Justification
from logwaver.model.justification_repository import JustificationRepository

LOGGER = logging.getLogger(__name__)

DEFAULT_UNDO_LIMIT: int = 500


class Command(ABC):
    """Action réversible."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Retourne le libellé affiché dans les menus Annuler/Rétablir."""

    @abstractmethod
    def execute(self) -> None:
        """Applique (ou ré-applique) l'action."""

    @abstractmethod
    def revert(self) -> None:
        """Annule l'action."""


class ChangeJustificationsCommand(Command):
    """Modifie un lot de justifications en mémorisant l'état précédent.

    Cette unique commande couvre le classement, le retrait d'une
    justification, le classement en masse et l'import de règles.
    """

    def __init__(
        self,
        repository: JustificationRepository,
        changes: Mapping[str, Optional[Justification]],
        description: str,
    ) -> None:
        """Prépare la commande.

        :param repository: dépôt à modifier.
        :param changes: empreinte → nouvelle valeur (``None`` = retrait).
        :param description: libellé de l'action.
        """
        self._repository = repository
        self._changes: Dict[str, Optional[Justification]] = dict(changes)
        self._previous = repository.snapshot(self._changes.keys())
        self._description = description

    @property
    def description(self) -> str:
        """Retourne le libellé de l'action."""
        return self._description

    @property
    def affected_count(self) -> int:
        """Retourne le nombre d'empreintes modifiées."""
        return len(self._changes)

    def execute(self) -> None:
        """Applique les nouvelles justifications."""
        self._repository.apply(self._changes)

    def revert(self) -> None:
        """Restaure les justifications précédentes."""
        self._repository.apply(self._previous)


class UndoStack:
    """Historique linéaire de commandes avec repère « enregistré »."""

    def __init__(self, limit: int = DEFAULT_UNDO_LIMIT) -> None:
        """Crée une pile vide.

        :param limit: nombre maximal de commandes conservées.
        """
        self._commands: List[Command] = []
        self._index: int = 0
        self._clean_index: Optional[int] = 0
        self._limit: int = limit
        self._listeners: List[Callable[[], None]] = []

    def add_listener(self, listener: Callable[[], None]) -> None:
        """Enregistre une fonction appelée à chaque changement d'état.

        :param listener: fonction sans argument.
        """
        self._listeners.append(listener)

    def push(self, command: Command) -> None:
        """Exécute une commande et l'ajoute à l'historique.

        :param command: commande à exécuter.
        """
        command.execute()
        del self._commands[self._index:]
        if self._clean_index is not None and self._clean_index > self._index:
            self._clean_index = None  # l'état enregistré n'est plus atteignable
        self._commands.append(command)
        self._index += 1
        self._enforce_limit()
        LOGGER.debug("Commande exécutée : %s", command.description)
        self._notify()

    def undo(self) -> Optional[str]:
        """Annule la dernière commande.

        :return: libellé de la commande annulée, ou ``None``.
        """
        if not self.can_undo:
            return None
        self._index -= 1
        command = self._commands[self._index]
        command.revert()
        LOGGER.info("Annulation : %s", command.description)
        self._notify()
        return command.description

    def redo(self) -> Optional[str]:
        """Rétablit la dernière commande annulée.

        :return: libellé de la commande rétablie, ou ``None``.
        """
        if not self.can_redo:
            return None
        command = self._commands[self._index]
        command.execute()
        self._index += 1
        LOGGER.info("Rétablissement : %s", command.description)
        self._notify()
        return command.description

    def clear(self) -> None:
        """Vide l'historique et marque l'état courant comme enregistré."""
        self._commands.clear()
        self._index = 0
        self._clean_index = 0
        self._notify()

    def mark_clean(self) -> None:
        """Mémorise l'état courant comme état enregistré."""
        self._clean_index = self._index
        self._notify()

    @property
    def is_clean(self) -> bool:
        """Indique si l'état courant correspond au dernier enregistrement."""
        return self._clean_index == self._index

    @property
    def can_undo(self) -> bool:
        """Indique si une annulation est possible."""
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        """Indique si un rétablissement est possible."""
        return self._index < len(self._commands)

    @property
    def undo_text(self) -> str:
        """Retourne le libellé de la prochaine annulation."""
        return self._commands[self._index - 1].description if self.can_undo else ""

    @property
    def redo_text(self) -> str:
        """Retourne le libellé du prochain rétablissement."""
        return self._commands[self._index].description if self.can_redo else ""

    def _enforce_limit(self) -> None:
        """Supprime les commandes les plus anciennes au-delà de la limite."""
        overflow = len(self._commands) - self._limit
        if overflow <= 0:
            return
        del self._commands[:overflow]
        self._index -= overflow
        if self._clean_index is not None:
            self._clean_index -= overflow
            if self._clean_index < 0:
                self._clean_index = None

    def _notify(self) -> None:
        """Prévient les observateurs d'un changement d'état."""
        for listener in self._listeners:
            listener()
