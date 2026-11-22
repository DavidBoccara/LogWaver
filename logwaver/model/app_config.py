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
from typing import Dict, List, Mapping, Optional, Tuple

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
    """Règles de comparaison utilisées pour retrouver une justification.

    Deux éléments sont considérés comme « le même » s'ils ont la même valeur
    pour chaque attribut de ``keys``, après application des tolérances.

    :param keys: attributs comparés.
    :param normalize_whitespace: fusionne les espaces multiples.
    :param ignore_case: ignore la casse.
    :param mask_numbers: ignore les nombres dans la description.
    :param mask_quoted: ignore le texte entre guillemets ou apostrophes de la
        description.
    :param mask_paths: ignore les noms de fichiers et chemins de la description.
    """

    keys: Tuple[str, ...] = DEFAULT_MATCH_KEYS
    normalize_whitespace: bool = True
    ignore_case: bool = False
    mask_numbers: bool = False
    mask_quoted: bool = False
    mask_paths: bool = False

    def to_dict(self) -> Dict[str, object]:
        """Sérialise les options (fichier projet).

        :return: dictionnaire JSON-compatible.
        """
        return {
            "keys": list(self.keys),
            "normalize_whitespace": self.normalize_whitespace,
            "ignore_case": self.ignore_case,
            "mask_numbers": self.mask_numbers,
            "mask_quoted": self.mask_quoted,
            "mask_paths": self.mask_paths,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object],
                  default: "MatchingOptions") -> "MatchingOptions":
        """Reconstruit des options ; les attributs absents ou invalides
        reprennent la valeur par défaut.

        :param data: dictionnaire issu de :meth:`to_dict`.
        :param default: options de repli.
        :return: options reconstruites.
        """
        raw_keys = data.get("keys", default.keys)
        keys = tuple(str(k) for k in raw_keys if str(k) in ALLOWED_MATCH_KEYS) \
            if isinstance(raw_keys, (list, tuple)) else default.keys

        def flag(name: str) -> bool:
            value = data.get(name, getattr(default, name))
            return value if isinstance(value, bool) else bool(getattr(default, name))

        return cls(keys or default.keys, flag("normalize_whitespace"), flag("ignore_case"),
                   flag("mask_numbers"), flag("mask_quoted"), flag("mask_paths"))


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

    def status_priority(self, status_id: str) -> int:
        """Retourne la priorité d'une catégorie (0 si inconnue).

        :param status_id: identifiant de la catégorie.
        :return: priorité (la plus élevée l'emporte en cas de conflit).
        """
        status = self.find_status(status_id)
        return status.priority if status else 0


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
                    priority=self._read_int(parser, section, "priority"),
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
            flags = [parser.getboolean(SECTION_MATCHING, name, fallback=default)
                     for name, default in (("normalize_whitespace", True),
                                           ("ignore_case", False),
                                           ("mask_numbers", False),
                                           ("mask_quoted", False),
                                           ("mask_paths", False))]
        except ValueError as error:
            raise ConfigurationError(
                f"Valeur booléenne invalide dans [matching] : {error}"
            ) from error
        return MatchingOptions(keys, *flags)

    @staticmethod
    def _read_int(parser: configparser.ConfigParser, section: str, key: str) -> int:
        """Lit un entier facultatif (0 par défaut).

        :param parser: configuration INI déjà lue.
        :param section: section concernée.
        :param key: clé à lire.
        :return: valeur entière.
        :raises ConfigurationError: si la valeur n'est pas un entier.
        """
        try:
            return parser.getint(section, key, fallback=0)
        except ValueError as error:
            raise ConfigurationError(
                f"[{section}] {key} doit être un nombre entier : {error}") from error

    @staticmethod
    def _split_list(raw_value: str) -> List[str]:
        """Découpe une liste séparée par des virgules.

        :param raw_value: texte brut.
        :return: éléments non vides, sans espaces superflus.
        """
        return [item.strip() for item in raw_value.split(",") if item.strip()]
