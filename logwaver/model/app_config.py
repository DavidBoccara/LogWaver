"""Chargement du fichier de configuration de l'application (catégories, etc.).

Ce fichier est distinct du fichier plugin : il décrit les catégories de
classement, les règles de correspondance des justifications et les options
générales (éditeur externe, langue des prompts IA).
"""

from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from logwaver.constants import (
    ALLOWED_MATCH_KEYS,
    CONFIG_STATUS_SECTION_PREFIX,
    DEFAULT_AI_LANGUAGE,
    DEFAULT_MATCH_KEYS,
    FILE_ENCODING,
)
from logwaver.model.entities import StatusDefinition
from logwaver.model.exceptions import ConfigurationError

LOGGER = logging.getLogger(__name__)

SECTION_STATUSES: str = "statuses"
SECTION_MATCHING: str = "matching"
SECTION_EDITOR: str = "editor"
SECTION_AI: str = "ai"


@dataclass(frozen=True)
class MatchingOptions:
    """Options de calcul de l'empreinte des éléments.

    :param keys: attributs utilisés pour l'empreinte.
    :param normalize_whitespace: fusionne les espaces multiples.
    :param ignore_case: ignore la casse lors de la comparaison.
    """

    keys: Tuple[str, ...] = DEFAULT_MATCH_KEYS
    normalize_whitespace: bool = True
    ignore_case: bool = False


@dataclass(frozen=True)
class AppConfig:
    """Configuration complète de l'application.

    :param statuses: catégories de classement, dans l'ordre d'affichage.
    :param matching: options de correspondance des justifications.
    :param editor_command: commande d'éditeur externe (``{file}``/``{line}``).
    :param ai_language: langue des prompts générés.
    :param default_status_id: catégorie proposée par défaut lors d'une justification.
    """

    statuses: Tuple[StatusDefinition, ...]
    matching: MatchingOptions = MatchingOptions()
    editor_command: str = ""
    ai_language: str = DEFAULT_AI_LANGUAGE
    default_status_id: str = ""

    def find_status(self, status_id: str) -> Optional[StatusDefinition]:
        """Recherche une catégorie par identifiant.

        :param status_id: identifiant recherché.
        :return: la catégorie, ou ``None`` si inconnue.
        """
        for status in self.statuses:
            if status.status_id == status_id:
                return status
        return None

    def status_label(self, status_id: str) -> str:
        """Retourne le libellé d'une catégorie (l'identifiant si inconnue).

        :param status_id: identifiant de la catégorie.
        :return: libellé affichable.
        """
        status = self.find_status(status_id)
        return status.label if status else status_id


@dataclass(frozen=True)
class ApplicationPaths:
    """Emplacements des ressources livrées avec l'application.

    :param plugins_directory: dossier des plugins (détection automatique).
    :param tutorial_file: fichier INI du didacticiel.
    :param sample_plugin: plugin de l'exemple fourni.
    :param sample_log: log de l'exemple fourni.
    """

    plugins_directory: Path
    tutorial_file: Path
    sample_plugin: Path
    sample_log: Path

    @classmethod
    def from_root(cls, root: Path) -> "ApplicationPaths":
        """Construit les chemins standards à partir du dossier de l'application.

        :param root: dossier contenant ``main.py``.
        :return: chemins des ressources.
        """
        return cls(
            plugins_directory=root / "plugins",
            tutorial_file=root / "resources" / "tutorial" / "didacticiel.ini",
            sample_plugin=root / "plugins" / "tintin.ini",
            sample_log=root / "samples" / "tintin_designer_a.log",
        )


class AppConfigLoader:
    """Lit et valide un fichier de configuration au format INI."""

    def load(self, path: Path) -> AppConfig:
        """Charge la configuration depuis un fichier.

        :param path: chemin du fichier INI.
        :return: configuration validée.
        :raises ConfigurationError: si le fichier est absent ou invalide.
        """
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # type: ignore[assignment]
        try:
            with path.open("r", encoding=FILE_ENCODING) as handle:
                parser.read_file(handle)
        except (OSError, configparser.Error) as error:
            raise ConfigurationError(
                f"Impossible de lire la configuration « {path} » : {error}"
            ) from error

        statuses = self._read_statuses(parser)
        matching = self._read_matching(parser)
        editor_command = parser.get(SECTION_EDITOR, "command", fallback="")
        ai_language = parser.get(
            SECTION_AI, "language", fallback=DEFAULT_AI_LANGUAGE
        )
        default_status = parser.get(SECTION_STATUSES, "default", fallback="").strip()
        if default_status and default_status not in {s.status_id for s in statuses}:
            raise ConfigurationError(
                f"La catégorie par défaut « {default_status} » n'est pas déclarée."
            )
        LOGGER.info(
            "Configuration chargée : %d catégories, clés=%s",
            len(statuses),
            ",".join(matching.keys),
        )
        return AppConfig(
            statuses=statuses,
            matching=matching,
            editor_command=editor_command.strip(),
            ai_language=ai_language.strip() or DEFAULT_AI_LANGUAGE,
            default_status_id=default_status,
        )

    def _read_statuses(
        self, parser: configparser.ConfigParser
    ) -> Tuple[StatusDefinition, ...]:
        """Lit la liste ordonnée des catégories.

        :param parser: configuration INI déjà lue.
        :return: catégories dans l'ordre déclaré.
        :raises ConfigurationError: si aucune catégorie valide n'est trouvée.
        """
        order = self._split_list(parser.get(SECTION_STATUSES, "order",
                                            fallback=""))
        if not order:
            raise ConfigurationError(
                "La section [statuses] doit définir « order = ... »."
            )
        statuses: List[StatusDefinition] = []
        for status_id in order:
            section = f"{CONFIG_STATUS_SECTION_PREFIX}{status_id}"
            if not parser.has_section(section):
                raise ConfigurationError(
                    f"Catégorie « {status_id} » déclarée sans section "
                    f"[{section}]."
                )
            statuses.append(
                StatusDefinition(
                    status_id=status_id,
                    label=parser.get(section, "label", fallback=status_id),
                    description=parser.get(section, "description",
                                           fallback=""),
                    color=parser.get(section, "color", fallback="#9e9e9e"),
                )
            )
        return tuple(statuses)

    def _read_matching(
        self, parser: configparser.ConfigParser
    ) -> MatchingOptions:
        """Lit les options de correspondance des justifications.

        :param parser: configuration INI déjà lue.
        :return: options validées.
        :raises ConfigurationError: si une clé inconnue est utilisée.
        """
        raw_keys = parser.get(SECTION_MATCHING, "keys", fallback="")
        keys = tuple(self._split_list(raw_keys)) or DEFAULT_MATCH_KEYS
        unknown = [key for key in keys if key not in ALLOWED_MATCH_KEYS]
        if unknown:
            raise ConfigurationError(
                f"Clés de correspondance inconnues : {', '.join(unknown)}. "
                f"Clés autorisées : {', '.join(ALLOWED_MATCH_KEYS)}."
            )
        try:
            normalize = parser.getboolean(
                SECTION_MATCHING, "normalize_whitespace", fallback=True
            )
            ignore_case = parser.getboolean(
                SECTION_MATCHING, "ignore_case", fallback=False
            )
        except ValueError as error:
            raise ConfigurationError(
                f"Valeur booléenne invalide dans [matching] : {error}"
            ) from error
        return MatchingOptions(keys, normalize, ignore_case)

    @staticmethod
    def _split_list(raw_value: str) -> List[str]:
        """Découpe une liste séparée par des virgules.

        :param raw_value: texte brut.
        :return: éléments non vides, sans espaces superflus.
        """
        return [item.strip() for item in raw_value.split(",") if item.strip()]
