"""Lecture/écriture des fichiers projet (.lwp) et de justifications (.lwj).

* Le **fichier projet** mémorise tout le travail : plugin, logs ouverts,
  utilisateur, justifications.
* Le **fichier de justifications** ne contient que les règles : c'est le
  fichier « automatique » transmis d'un concepteur à un autre.

Les deux formats sont en JSON lisible. Un fichier projet peut aussi être
importé comme source de justifications.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from logwaver import __version__
from logwaver.constants import (
    FILE_ENCODING,
    FILE_FORMAT_VERSION,
    PROJECT_FORMAT_NAME,
    RULES_FORMAT_NAME,
)
from logwaver.model.entities import Justification
from logwaver.model.exceptions import ProjectFileError

LOGGER = logging.getLogger(__name__)

JSON_INDENT: int = 2


@dataclass
class ProjectData:
    """Contenu d'un fichier projet.

    :param plugin_path: chemin absolu du plugin utilisé.
    :param log_paths: chemins absolus des logs ouverts.
    :param user_name: nom du dernier utilisateur ayant justifié.
    :param matching_keys: clés d'empreinte utilisées lors de l'enregistrement.
    :param justifications: règles de justification.
    """

    plugin_path: str = ""
    log_paths: List[str] = field(default_factory=list)
    user_name: str = ""
    matching_keys: Tuple[str, ...] = ()
    justifications: List[Justification] = field(default_factory=list)


@dataclass(frozen=True)
class RulesData:
    """Contenu d'un fichier de justifications.

    :param tool_name: outil d'origine des règles (informatif).
    :param matching_keys: clés d'empreinte utilisées à la création.
    :param justifications: règles exportées.
    """

    tool_name: str
    matching_keys: Tuple[str, ...]
    justifications: Tuple[Justification, ...]


class ProjectStore:
    """Sérialise et désérialise projets et fichiers de justifications."""

    # ----------------------------------------------------------------- projet
    def save_project(self, data: ProjectData, path: Path) -> None:
        """Enregistre un projet (chemins rendus relatifs au fichier projet).

        :param data: contenu du projet.
        :param path: fichier de destination.
        :raises ProjectFileError: si l'écriture échoue.
        """
        base = path.resolve().parent
        document = {
            "format": PROJECT_FORMAT_NAME,
            "version": FILE_FORMAT_VERSION,
            "application_version": __version__,
            "plugin_path": self._to_relative(data.plugin_path, base),
            "log_paths": [self._to_relative(p, base) for p in data.log_paths],
            "user_name": data.user_name,
            "matching_keys": list(data.matching_keys),
            "justifications": [j.to_dict() for j in data.justifications],
        }
        self._write_json(document, path)
        LOGGER.info("Projet enregistré : %s (%d justifications)",
                    path, len(data.justifications))

    def load_project(self, path: Path) -> ProjectData:
        """Charge un projet.

        :param path: fichier projet.
        :return: contenu du projet (chemins absolus).
        :raises ProjectFileError: si le fichier est invalide.
        """
        document = self._read_json(path)
        self._check_format(document, PROJECT_FORMAT_NAME, path)
        base = path.resolve().parent
        try:
            return ProjectData(
                plugin_path=self._to_absolute(
                    str(document.get("plugin_path", "")), base
                ),
                log_paths=[
                    self._to_absolute(str(p), base)
                    for p in document.get("log_paths", [])
                ],
                user_name=str(document.get("user_name", "")),
                matching_keys=tuple(document.get("matching_keys", [])),
                justifications=self._parse_justifications(document),
            )
        except (TypeError, ValueError) as error:
            raise ProjectFileError(
                f"Projet « {path} » corrompu : {error}"
            ) from error

    # ------------------------------------------------------- justifications
    def save_rules(self, data: RulesData, path: Path) -> None:
        """Enregistre un fichier de justifications.

        :param data: règles à exporter.
        :param path: fichier de destination.
        :raises ProjectFileError: si l'écriture échoue.
        """
        document = {
            "format": RULES_FORMAT_NAME,
            "version": FILE_FORMAT_VERSION,
            "application_version": __version__,
            "tool_name": data.tool_name,
            "matching_keys": list(data.matching_keys),
            "justifications": [j.to_dict() for j in data.justifications],
        }
        self._write_json(document, path)
        LOGGER.info("%d justifications exportées vers %s",
                    len(data.justifications), path)

    def load_rules(self, path: Path) -> RulesData:
        """Charge des règles depuis un fichier de justifications ou un projet.

        :param path: fichier ``.lwj`` ou ``.lwp``.
        :return: règles lues.
        :raises ProjectFileError: si le fichier est invalide.
        """
        document = self._read_json(path)
        file_format = document.get("format")
        if file_format not in (RULES_FORMAT_NAME, PROJECT_FORMAT_NAME):
            raise ProjectFileError(
                f"« {path} » n'est ni un fichier de justifications ni un projet."
            )
        return RulesData(
            tool_name=str(document.get("tool_name", "")),
            matching_keys=tuple(document.get("matching_keys", [])),
            justifications=tuple(self._parse_justifications(document)),
        )

    # -------------------------------------------------------------- interne
    @staticmethod
    def _parse_justifications(document: Dict[str, Any]) -> List[Justification]:
        """Reconstruit les justifications d'un document JSON.

        :param document: document lu.
        :return: justifications valides (les invalides sont journalisées).
        """
        result: List[Justification] = []
        for raw in document.get("justifications", []):
            try:
                result.append(Justification.from_dict(raw))
            except (KeyError, TypeError, AttributeError) as error:
                LOGGER.warning("Justification ignorée (invalide) : %s", error)
        return result

    @staticmethod
    def _check_format(document: Dict[str, Any], expected: str,
                      path: Path) -> None:
        """Vérifie le format et la version d'un document.

        :param document: document lu.
        :param expected: nom de format attendu.
        :param path: fichier d'origine (pour le message).
        :raises ProjectFileError: si le format ne correspond pas.
        """
        if document.get("format") != expected:
            raise ProjectFileError(f"« {path} » n'est pas un fichier {expected}.")
        version = document.get("version", 0)
        if not isinstance(version, int) or version > FILE_FORMAT_VERSION:
            raise ProjectFileError(
                f"Version de fichier non supportée ({version}) pour « {path} »."
            )

    @staticmethod
    def _write_json(document: Dict[str, Any], path: Path) -> None:
        """Écrit un document JSON de façon atomique (fichier temporaire).

        :param document: contenu à écrire.
        :param path: fichier de destination.
        :raises ProjectFileError: si l'écriture échoue.
        """
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(document, indent=JSON_INDENT, ensure_ascii=False),
                encoding=FILE_ENCODING,
            )
            os.replace(temporary, path)
        except OSError as error:
            raise ProjectFileError(
                f"Impossible d'écrire « {path} » : {error}"
            ) from error

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        """Lit un document JSON.

        :param path: fichier à lire.
        :return: document (dictionnaire).
        :raises ProjectFileError: si le fichier est illisible ou invalide.
        """
        try:
            document = json.loads(path.read_text(encoding=FILE_ENCODING))
        except (OSError, json.JSONDecodeError) as error:
            raise ProjectFileError(
                f"Impossible de lire « {path} » : {error}"
            ) from error
        if not isinstance(document, dict):
            raise ProjectFileError(f"« {path} » n'est pas un objet JSON.")
        return document

    @staticmethod
    def _to_relative(raw_path: str, base: Path) -> str:
        """Rend un chemin relatif au répertoire du projet si possible.

        :param raw_path: chemin absolu.
        :param base: répertoire du projet.
        :return: chemin relatif (style POSIX) ou absolu si impossible.
        """
        if not raw_path:
            return ""
        try:
            return Path(os.path.relpath(raw_path, base)).as_posix()
        except ValueError:  # lecteurs différents sous Windows
            return raw_path

    @staticmethod
    def _to_absolute(raw_path: str, base: Path) -> str:
        """Résout un chemin stocké relativement au projet.

        :param raw_path: chemin stocké.
        :param base: répertoire du projet.
        :return: chemin absolu (chaîne vide si ``raw_path`` est vide).
        """
        if not raw_path:
            return ""
        path = Path(raw_path)
        if not path.is_absolute():
            path = base / path
        return str(path.resolve())


def describe_rules_compatibility(
    rules_keys: Tuple[str, ...], current_keys: Tuple[str, ...]
) -> Optional[str]:
    """Explique une éventuelle incompatibilité de clés d'empreinte.

    :param rules_keys: clés utilisées pour créer les règles.
    :param current_keys: clés de la configuration courante.
    :return: message d'avertissement, ou ``None`` si compatible.
    """
    if not rules_keys or tuple(rules_keys) == tuple(current_keys):
        return None
    return (
        "Les justifications ont été créées avec les clés de correspondance "
        f"« {', '.join(rules_keys)} » alors que la configuration actuelle "
        f"utilise « {', '.join(current_keys)} ». Certaines justifications "
        "pourraient ne pas être retrouvées."
    )
