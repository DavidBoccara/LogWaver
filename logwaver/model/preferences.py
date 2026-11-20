"""Préférences utilisateur persistantes (dernier nom d'utilisateur, dossiers)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

from logwaver.constants import FILE_ENCODING, LOG_DIRECTORY_NAME

LOGGER = logging.getLogger(__name__)

PREFERENCES_FILE_NAME: str = "preferences.json"
KEY_LAST_USER: str = "last_user_name"


class UserPreferences:
    """Petit magasin clé/valeur stocké dans ``~/.logwaver/preferences.json``.

    Les erreurs d'entrée/sortie sont journalisées sans être propagées : les
    préférences ne doivent jamais empêcher l'application de fonctionner.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Charge les préférences.

        :param path: fichier de préférences (défaut : dossier utilisateur).
        """
        self._path: Path = path or Path.home() / LOG_DIRECTORY_NAME / PREFERENCES_FILE_NAME
        self._values: Dict[str, str] = self._load()

    @property
    def last_user_name(self) -> str:
        """Retourne le dernier nom d'utilisateur saisi."""
        return self._values.get(KEY_LAST_USER, "")

    @last_user_name.setter
    def last_user_name(self, value: str) -> None:
        """Mémorise le dernier nom d'utilisateur saisi.

        :param value: nom à mémoriser.
        """
        self._values[KEY_LAST_USER] = value
        self._save()

    def _load(self) -> Dict[str, str]:
        """Lit le fichier de préférences.

        :return: valeurs lues (vide en cas d'absence ou d'erreur).
        """
        try:
            data = json.loads(self._path.read_text(encoding=FILE_ENCODING))
            return {str(k): str(v) for k, v in dict(data).items()}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError) as error:
            LOGGER.warning("Préférences illisibles (%s) : %s", self._path, error)
            return {}

    def _save(self) -> None:
        """Écrit le fichier de préférences."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._values, indent=2, ensure_ascii=False),
                                  encoding=FILE_ENCODING)
        except OSError as error:
            LOGGER.warning("Préférences non enregistrées (%s) : %s", self._path, error)
