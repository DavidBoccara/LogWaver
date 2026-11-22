"""Préréglages de règles de correspondance, du plus strict au plus tolérant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from logwaver.constants import (
    MATCH_KEY_CODE,
    MATCH_KEY_DESCRIPTION,
    MATCH_KEY_FILE_NAME,
    MATCH_KEY_FILE_PATH,
    MATCH_KEY_LINE,
    MATCH_KEY_TOOL,
    MATCH_KEY_TYPE,
)
from logwaver.model.app_config import MatchingOptions

MATCH_KEY_LABELS: dict = {
    MATCH_KEY_TOOL: "Outil",
    MATCH_KEY_TYPE: "Type d'élément",
    MATCH_KEY_CODE: "Code",
    MATCH_KEY_DESCRIPTION: "Description (message)",
    MATCH_KEY_FILE_NAME: "Nom du fichier",
    MATCH_KEY_FILE_PATH: "Chemin complet du fichier",
    MATCH_KEY_LINE: "Numéro de ligne",
}
MATCH_KEY_HINTS: dict = {
    MATCH_KEY_TOOL: "Décocher : une justification d'un outil s'appliquerait à un autre.",
    MATCH_KEY_TYPE: "Décocher : un warning et une erreur de même code seraient confondus.",
    MATCH_KEY_CODE: "Le code identifie le problème : à garder presque toujours.",
    MATCH_KEY_DESCRIPTION: "Décocher : tous les messages d'un même code seraient confondus.",
    MATCH_KEY_FILE_NAME: "Décocher : la justification vaut quel que soit le fichier.",
    MATCH_KEY_FILE_PATH: "Cocher : le fichier doit être au même endroit (rarement utile "
                         "si le code change de dossier ou de concepteur).",
    MATCH_KEY_LINE: "Cocher : la moindre ligne ajoutée au-dessus ferait perdre la "
                    "justification.",
}


@dataclass(frozen=True)
class MatchingPreset:
    """Réglage prédéfini proposé à l'utilisateur.

    :param key: identifiant.
    :param label: libellé court.
    :param description: explication en une phrase.
    :param options: règles correspondantes.
    """

    key: str
    label: str
    description: str
    options: MatchingOptions


PRESETS: Tuple[MatchingPreset, ...] = (
    MatchingPreset(
        "strict", "Strict",
        "Tout doit être identique, y compris le chemin et le numéro de ligne.",
        MatchingOptions(keys=(MATCH_KEY_TOOL, MATCH_KEY_TYPE, MATCH_KEY_CODE,
                              MATCH_KEY_DESCRIPTION, MATCH_KEY_FILE_PATH, MATCH_KEY_LINE)),
    ),
    MatchingPreset(
        "recommended", "Recommandé",
        "Même code, même message, même fichier ; la ligne et le dossier peuvent changer.",
        MatchingOptions(keys=(MATCH_KEY_TOOL, MATCH_KEY_TYPE, MATCH_KEY_CODE,
                              MATCH_KEY_DESCRIPTION, MATCH_KEY_FILE_NAME)),
    ),
    MatchingPreset(
        "tolerant", "Tolérant",
        "Même code et même message, quels que soient le fichier, la ligne, les nombres "
        "et les noms cités dans le message.",
        MatchingOptions(keys=(MATCH_KEY_TOOL, MATCH_KEY_TYPE, MATCH_KEY_CODE,
                              MATCH_KEY_DESCRIPTION),
                        mask_numbers=True, mask_quoted=True, mask_paths=True),
    ),
    MatchingPreset(
        "by_code", "Par code seulement",
        "Une justification vaut pour toutes les occurrences d'un même code.",
        MatchingOptions(keys=(MATCH_KEY_TOOL, MATCH_KEY_TYPE, MATCH_KEY_CODE)),
    ),
)


def find_preset(options: MatchingOptions) -> Optional[MatchingPreset]:
    """Retrouve le préréglage correspondant exactement à des règles.

    :param options: règles à comparer.
    :return: préréglage, ou ``None`` (réglage personnalisé).
    """
    for preset in PRESETS:
        if set(preset.options.keys) == set(options.keys) and \
                preset.options.mask_numbers == options.mask_numbers and \
                preset.options.mask_quoted == options.mask_quoted and \
                preset.options.mask_paths == options.mask_paths and \
                preset.options.ignore_case == options.ignore_case:
            return preset
    return None
