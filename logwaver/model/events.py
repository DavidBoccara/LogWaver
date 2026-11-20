"""Mécanisme d'observation minimaliste (patron Observateur) sans Qt."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

LOGGER = logging.getLogger(__name__)

EVENT_ENTRIES_CHANGED: str = "entries_changed"
EVENT_JUSTIFICATIONS_CHANGED: str = "justifications_changed"
EVENT_PROJECT_CHANGED: str = "project_changed"
EVENT_HISTORY_CHANGED: str = "history_changed"


class EventHub:
    """Diffuse des événements nommés à des observateurs abonnés."""

    def __init__(self) -> None:
        """Crée un diffuseur sans abonné."""
        self._subscribers: Dict[str, List[Callable[[], None]]] = {}

    def subscribe(self, event_name: str, callback: Callable[[], None]) -> None:
        """Abonne une fonction à un événement.

        :param event_name: nom de l'événement.
        :param callback: fonction sans argument appelée lors de l'événement.
        """
        self._subscribers.setdefault(event_name, []).append(callback)

    def publish(self, event_name: str) -> None:
        """Notifie les abonnés d'un événement.

        Une erreur dans un abonné est journalisée sans interrompre les
        autres notifications.

        :param event_name: nom de l'événement.
        """
        for callback in list(self._subscribers.get(event_name, [])):
            try:
                callback()
            except Exception:  # noqa: BLE001 - isolation des observateurs
                LOGGER.exception("Erreur dans un observateur de « %s ».",
                                 event_name)
