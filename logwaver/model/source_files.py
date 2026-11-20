"""Accès aux fichiers sources cités par les logs (lecture, éditeur externe)."""

from __future__ import annotations

import logging
import shlex
import subprocess
import sys
from pathlib import Path

from logwaver.constants import FILE_ENCODING, LOG_FALLBACK_ENCODING
from logwaver.model.exceptions import LogWaverError

LOGGER = logging.getLogger(__name__)

MAX_SOURCE_SIZE_BYTES: int = 20_000_000


class SourceFileReader:
    """Lit un fichier source pour la visionneuse intégrée."""

    def read(self, path: Path) -> str:
        """Lit le contenu textuel d'un fichier.

        :param path: fichier à lire.
        :return: contenu du fichier.
        :raises LogWaverError: si le fichier est trop gros ou illisible.
        """
        try:
            if path.stat().st_size > MAX_SOURCE_SIZE_BYTES:
                raise LogWaverError(
                    f"Fichier trop volumineux pour la visionneuse : {path}"
                )
            try:
                return path.read_text(encoding=FILE_ENCODING)
            except UnicodeDecodeError:
                return path.read_text(encoding=LOG_FALLBACK_ENCODING)
        except OSError as error:
            raise LogWaverError(
                f"Impossible de lire « {path} » : {error}"
            ) from error


class ExternalEditorLauncher:
    """Ouvre un fichier à une ligne donnée dans un éditeur externe."""

    def __init__(self, command_template: str) -> None:
        """Initialise le lanceur.

        :param command_template: commande avec jetons ``{file}`` et ``{line}``.
        """
        self._template: str = command_template.strip()

    @property
    def is_configured(self) -> bool:
        """Indique si une commande d'éditeur est configurée."""
        return bool(self._template)

    def open(self, path: Path, line: int) -> None:
        """Lance l'éditeur externe.

        :param path: fichier à ouvrir.
        :param line: ligne à atteindre.
        :raises LogWaverError: si la commande est absente ou échoue.
        """
        if not self.is_configured:
            raise LogWaverError("Aucun éditeur externe n'est configuré.")
        command_text = self._template.replace("{file}", str(path)).replace(
            "{line}", str(line)
        )
        try:
            arguments = shlex.split(command_text, posix=sys.platform != "win32")
            subprocess.Popen(arguments)  # noqa: S603 - commande de l'utilisateur
        except (OSError, ValueError) as error:
            raise LogWaverError(
                f"Échec du lancement de l'éditeur « {command_text} » : {error}"
            ) from error
        LOGGER.info("Éditeur externe lancé : %s", command_text)
