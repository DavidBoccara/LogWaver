"""Calcul de l'empreinte d'un élément de log.

L'empreinte est la clé qui relie un élément à sa justification. Elle est
calculée à partir d'attributs stables (outil, type, code, description, nom
court du fichier...) et volontairement *sans* numéro de ligne par défaut :
ainsi une justification survit aux modifications du code source et peut être
réutilisée par un autre concepteur.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, Mapping, Tuple

from logwaver.constants import (
    FIELD_CODE,
    FIELD_DESCRIPTION,
    FIELD_FILE,
    FIELD_LINE,
    FINGERPRINT_HASH_LENGTH,
    FINGERPRINT_SEPARATOR,
    MATCH_KEY_CODE,
    MATCH_KEY_DESCRIPTION,
    MATCH_KEY_FILE_NAME,
    MATCH_KEY_FILE_PATH,
    MATCH_KEY_LINE,
    MATCH_KEY_TOOL,
    MATCH_KEY_TYPE,
)
from logwaver.model.app_config import MatchingOptions

WHITESPACE_PATTERN = re.compile(r"\s+")


class FingerprintBuilder:
    """Construit des empreintes reproductibles selon les options choisies."""

    def __init__(self, options: MatchingOptions) -> None:
        """Initialise le calculateur.

        :param options: attributs et normalisations à appliquer.
        """
        self._options: MatchingOptions = options

    @property
    def keys(self) -> Tuple[str, ...]:
        """Retourne les attributs pris en compte."""
        return self._options.keys

    def build(
        self, tool_name: str, entry_type: str, fields: Mapping[str, str]
    ) -> str:
        """Calcule l'empreinte d'un élément.

        :param tool_name: nom de l'outil.
        :param entry_type: type d'élément.
        :param fields: champs extraits.
        :return: empreinte hexadécimale.
        """
        values = self.describe(tool_name, entry_type, fields)
        parts = [f"{key}={values[key]}" for key in self._options.keys]
        digest = hashlib.sha1(
            FINGERPRINT_SEPARATOR.join(parts).encode("utf-8")
        ).hexdigest()
        return digest[:FINGERPRINT_HASH_LENGTH]

    def describe(
        self, tool_name: str, entry_type: str, fields: Mapping[str, str]
    ) -> Dict[str, str]:
        """Retourne les valeurs normalisées de chaque attribut possible.

        :param tool_name: nom de l'outil.
        :param entry_type: type d'élément.
        :param fields: champs extraits.
        :return: dictionnaire attribut → valeur normalisée.
        """
        file_path = fields.get(FIELD_FILE, "").replace("\\", "/")
        raw_values = {
            MATCH_KEY_TOOL: tool_name,
            MATCH_KEY_TYPE: entry_type,
            MATCH_KEY_CODE: fields.get(FIELD_CODE, ""),
            MATCH_KEY_DESCRIPTION: fields.get(FIELD_DESCRIPTION, ""),
            MATCH_KEY_FILE_NAME: Path(file_path).name if file_path else "",
            MATCH_KEY_FILE_PATH: file_path,
            MATCH_KEY_LINE: fields.get(FIELD_LINE, ""),
        }
        return {key: self._normalize(value) for key, value in raw_values.items()}

    def _normalize(self, value: str) -> str:
        """Applique les normalisations configurées.

        :param value: valeur brute.
        :return: valeur normalisée.
        """
        result = value.strip()
        if self._options.normalize_whitespace:
            result = WHITESPACE_PATTERN.sub(" ", result)
        if self._options.ignore_case:
            result = result.casefold()
        return result
