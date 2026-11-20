"""Gestion d'erreurs uniforme pour les gestionnaires d'actions des présentateurs."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Optional, TypeVar

from logwaver.model.exceptions import LogWaverError

LOGGER = logging.getLogger(__name__)

HandlerType = TypeVar("HandlerType", bound=Callable[..., Any])
UNEXPECTED_ERROR_MESSAGE: str = (
    "Une erreur inattendue s'est produite. Consultez le journal pour le détail :\n{error}"
)


def guarded(handler: HandlerType) -> HandlerType:
    """Décore une méthode de présentateur pour intercepter les erreurs.

    * ``LogWaverError`` : erreur métier attendue → message à l'utilisateur ;
    * toute autre exception : bug → trace complète dans le journal et
      message générique (l'application reste utilisable).

    La classe décorée doit fournir ``_report_error(message: str)``.

    :param handler: méthode à protéger.
    :return: méthode protégée (retourne ``None`` en cas d'erreur).
    """
    @functools.wraps(handler)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Optional[Any]:
        try:
            return handler(self, *args, **kwargs)
        except LogWaverError as error:
            LOGGER.warning("%s : %s", handler.__name__, error)
            self._report_error(str(error))
        except Exception as error:  # noqa: BLE001 - dernier rempart de l'IHM
            LOGGER.exception("Erreur inattendue dans %s", handler.__name__)
            self._report_error(UNEXPECTED_ERROR_MESSAGE.format(error=error))
        return None

    return wrapper  # type: ignore[return-value]
