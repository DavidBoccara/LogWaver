"""Regroupement des éléments par valeur commune (code, fichier, type...).

Le regroupement permet de replier les éléments partageant un même texte
(même code, même fichier, même description...) et de les justifier en une
seule action en sélectionnant le groupe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from logwaver.constants import (
    FIELD_CODE,
    FIELD_DESCRIPTION,
    FIELD_FILE,
    FIELD_LABELS,
    FIELD_LINE,
    STANDARD_FIELDS,
)
from logwaver.model.entities import Justification, LogEntry

GROUP_NONE: str = "none"
GROUP_BY_TYPE: str = "type"
GROUP_BY_STATUS: str = "status"
GROUP_BY_AUTHOR: str = "author"
GROUP_BY_LOG: str = "log"
GROUP_BY_FILE_NAME: str = "file_name"
GROUP_FIELD_PREFIX: str = "field:"
EMPTY_GROUP_LABEL: str = "(vide)"
UNCLASSIFIED_GROUP_LABEL: str = "Non justifié"

# Champs standards pour lesquels un regroupement a un sens (la ligne seule n'en a pas).
GROUPABLE_STANDARD_FIELDS: Tuple[str, ...] = (FIELD_CODE, FIELD_FILE, FIELD_DESCRIPTION)


def field_grouping_key(field_name: str) -> str:
    """Construit la clé de regroupement associée à un champ du plugin.

    :param field_name: nom du champ (``code``, ``file``...).
    :return: clé de regroupement (ex. ``field:code``).
    """
    return f"{GROUP_FIELD_PREFIX}{field_name}"


@dataclass(frozen=True)
class GroupingOption:
    """Critère de regroupement proposé à l'utilisateur.

    :param key: identifiant technique du critère.
    :param label: libellé affiché.
    """

    key: str
    label: str


@dataclass(frozen=True)
class EntryGroup:
    """Ensemble d'éléments partageant la même valeur pour un critère.

    :param value: valeur commune (libellé du groupe).
    :param entries: éléments du groupe, dans l'ordre d'origine.
    """

    value: str
    entries: Tuple[LogEntry, ...]

    @property
    def size(self) -> int:
        """Retourne le nombre d'éléments du groupe."""
        return len(self.entries)


class EntryGrouper:
    """Calcule les critères disponibles et regroupe les éléments."""

    def __init__(
        self,
        justification_of: Callable[[LogEntry], Optional[Justification]],
        status_label: Callable[[str], str],
    ) -> None:
        """Initialise le regroupeur.

        :param justification_of: fonction donnant la justification d'un élément.
        :param status_label: fonction donnant le libellé d'une catégorie.
        """
        self._justification_of = justification_of
        self._status_label = status_label

    @staticmethod
    def available_options(plugin_fields: Iterable[str]) -> List[GroupingOption]:
        """Liste les critères de regroupement proposés.

        Les champs propres au plugin (au-delà des champs standards) sont
        ajoutés automatiquement : on peut regrouper par n'importe quel élément
        extrait.

        :param plugin_fields: champs déclarés par le plugin chargé.
        :return: critères, « Aucun regroupement » en premier.
        """
        options = [
            GroupingOption(GROUP_NONE, "Aucun regroupement"),
            GroupingOption(field_grouping_key(FIELD_CODE), "Code"),
            GroupingOption(field_grouping_key(FIELD_FILE), "Fichier (chemin complet)"),
            GroupingOption(GROUP_BY_FILE_NAME, "Fichier (nom seul)"),
            GroupingOption(field_grouping_key(FIELD_DESCRIPTION), "Description (texte identique)"),
            GroupingOption(GROUP_BY_TYPE, "Type d'élément"),
            GroupingOption(GROUP_BY_STATUS, "Catégorie"),
            GroupingOption(GROUP_BY_AUTHOR, "Auteur de la justification"),
            GroupingOption(GROUP_BY_LOG, "Fichier de log"),
        ]
        known = set(STANDARD_FIELDS)
        for field_name in plugin_fields:
            if field_name not in known and field_name != FIELD_LINE:
                known.add(field_name)
                label = FIELD_LABELS.get(field_name, field_name)
                options.append(GroupingOption(field_grouping_key(field_name),
                                              f"Champ « {label} »"))
        return options

    def group(self, entries: Sequence[LogEntry], key: str) -> List[EntryGroup]:
        """Regroupe des éléments selon un critère.

        Les groupes sont triés du plus grand au plus petit, puis par valeur,
        pour faire apparaître en premier les messages les plus redondants.

        :param entries: éléments à regrouper.
        :param key: critère de regroupement.
        :return: groupes (liste vide si ``key`` vaut ``GROUP_NONE``).
        """
        if key == GROUP_NONE:
            return []
        buckets: Dict[str, List[LogEntry]] = {}
        for entry in entries:
            buckets.setdefault(self.value_of(entry, key), []).append(entry)
        groups = [EntryGroup(value, tuple(items)) for value, items in buckets.items()]
        groups.sort(key=lambda group: (-group.size, group.value.casefold()))
        return groups

    def value_of(self, entry: LogEntry, key: str) -> str:
        """Retourne la valeur d'un élément pour un critère.

        :param entry: élément concerné.
        :param key: critère de regroupement.
        :return: valeur affichable (``EMPTY_GROUP_LABEL`` si vide).
        """
        value = self._raw_value(entry, key)
        return value.strip() or EMPTY_GROUP_LABEL

    def _raw_value(self, entry: LogEntry, key: str) -> str:
        """Calcule la valeur brute d'un critère.

        :param entry: élément concerné.
        :param key: critère de regroupement.
        :return: valeur brute (peut être vide).
        """
        if key.startswith(GROUP_FIELD_PREFIX):
            return entry.fields.get(key[len(GROUP_FIELD_PREFIX):], "")
        if key == GROUP_BY_FILE_NAME:
            return entry.file_name
        if key == GROUP_BY_TYPE:
            return entry.entry_type
        if key == GROUP_BY_LOG:
            return Path(entry.log_path).name
        justification = self._justification_of(entry)
        if key == GROUP_BY_STATUS:
            return (self._status_label(justification.status_id) if justification
                    else UNCLASSIFIED_GROUP_LABEL)
        if key == GROUP_BY_AUTHOR:
            return justification.author if justification else ""
        return ""
