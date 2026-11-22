"""Calcul de l'empreinte de comparaison d'un élément de log.

Deux éléments ayant la même empreinte sont considérés comme « le même
élément » : une justification de l'un s'applique à l'autre. L'empreinte est
calculée à partir des attributs choisis dans les règles de correspondance
(outil, type, code, description, nom du fichier...), après application des
tolérances (espaces, casse, nombres, texte entre guillemets, chemins).

Par défaut le numéro de ligne et le répertoire sont exclus : une
justification survit ainsi aux modifications du code source et peut être
réutilisée par un autre concepteur.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, Mapping, Tuple

from logwaver.constants import (
    ALLOWED_MATCH_KEYS,
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
MASK_TOKEN: str = "‹…›"
# Texte entre guillemets droits, typographiques ou français ; les apostrophes
# simples ne comptent que si elles ne sont pas collées à une lettre (« l'erreur »
# n'est donc pas concerné).
QUOTED_PATTERN = re.compile(
    r'"[^"\n]*"|«[^»\n]*»|“[^”\n]*”|(?<![\w])\'[^\'\n]+\'(?![\w])'
)
# Chemins (présence d'un / ou d'un \) ou noms de fichiers avec extension.
PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:)?[\w.\-~]*[\\/][\w.\-\\/~]+|\b[\w\-]+\.[A-Za-z][A-Za-z0-9]{0,5}\b"
)
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*")


class FingerprintBuilder:
    """Construit des empreintes reproductibles selon des règles de correspondance."""

    def __init__(self, options: MatchingOptions) -> None:
        """Initialise le calculateur.

        :param options: attributs comparés et tolérances.
        """
        self._options: MatchingOptions = options

    @classmethod
    def strict(cls) -> "FingerprintBuilder":
        """Crée un calculateur « identité exacte » (tous les attributs, sans tolérance).

        Il sert à attribuer un identifiant stable à chaque justification,
        indépendant des règles de correspondance choisies par l'utilisateur.

        :return: calculateur strict.
        """
        return cls(MatchingOptions(keys=ALLOWED_MATCH_KEYS))

    @property
    def options(self) -> MatchingOptions:
        """Retourne les règles de correspondance appliquées."""
        return self._options

    @property
    def keys(self) -> Tuple[str, ...]:
        """Retourne les attributs comparés."""
        return self._options.keys

    @staticmethod
    def raw_context(tool_name: str, entry_type: str,
                    fields: Mapping[str, str]) -> Dict[str, str]:
        """Extrait les valeurs brutes de tous les attributs comparables.

        Ce contexte est mémorisé avec chaque justification : il permet de
        recalculer l'empreinte si l'utilisateur change les règles.

        :param tool_name: nom de l'outil.
        :param entry_type: type d'élément.
        :param fields: champs extraits.
        :return: attribut → valeur brute (sans espaces aux extrémités).
        """
        file_path = fields.get(FIELD_FILE, "").replace("\\", "/").strip()
        return {
            MATCH_KEY_TOOL: tool_name.strip(),
            MATCH_KEY_TYPE: entry_type.strip(),
            MATCH_KEY_CODE: fields.get(FIELD_CODE, "").strip(),
            MATCH_KEY_DESCRIPTION: fields.get(FIELD_DESCRIPTION, "").strip(),
            MATCH_KEY_FILE_NAME: Path(file_path).name if file_path else "",
            MATCH_KEY_FILE_PATH: file_path,
            MATCH_KEY_LINE: fields.get(FIELD_LINE, "").strip(),
        }

    def build(self, tool_name: str, entry_type: str, fields: Mapping[str, str]) -> str:
        """Calcule l'empreinte d'un élément.

        :param tool_name: nom de l'outil.
        :param entry_type: type d'élément.
        :param fields: champs extraits.
        :return: empreinte hexadécimale.
        """
        return self.build_from_context(self.raw_context(tool_name, entry_type, fields))

    def build_from_context(self, context: Mapping[str, str]) -> str:
        """Calcule l'empreinte à partir d'un contexte mémorisé.

        Un attribut absent du contexte (fichiers anciens) vaut chaîne vide.

        :param context: attribut → valeur brute.
        :return: empreinte hexadécimale.
        """
        values = self.comparable_values(context)
        parts = [f"{key}={values[key]}" for key in self._options.keys]
        digest = hashlib.sha1(FINGERPRINT_SEPARATOR.join(parts).encode("utf-8")).hexdigest()
        return digest[:FINGERPRINT_HASH_LENGTH]

    def comparable_values(self, context: Mapping[str, str]) -> Dict[str, str]:
        """Retourne les valeurs telles qu'elles sont réellement comparées.

        Sert aussi à montrer à l'utilisateur ce qui est ignoré (ex. la
        description « le fichier ‹…› est introuvable »).

        :param context: attribut → valeur brute.
        :return: attribut → valeur après tolérances.
        """
        return {key: self._normalize(key, str(context.get(key, "")))
                for key in ALLOWED_MATCH_KEYS}

    def _normalize(self, key: str, value: str) -> str:
        """Applique les tolérances configurées à une valeur.

        :param key: attribut concerné (les masques ne visent que la description).
        :param value: valeur brute.
        :return: valeur comparée.
        """
        result = value.strip()
        if key == MATCH_KEY_DESCRIPTION:
            if self._options.mask_quoted:
                result = QUOTED_PATTERN.sub(MASK_TOKEN, result)
            if self._options.mask_paths:
                result = PATH_PATTERN.sub(MASK_TOKEN, result)
            if self._options.mask_numbers:
                result = NUMBER_PATTERN.sub(MASK_TOKEN, result)
        if self._options.normalize_whitespace:
            result = WHITESPACE_PATTERN.sub(" ", result)
        if self._options.ignore_case:
            result = result.casefold()
        return result
