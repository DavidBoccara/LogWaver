"""Objets de transfert (DTO) immuables échangés entre Présentateurs et Vues.

Les vues ne connaissent que ces structures simples : elles ignorent tout du
Modèle, ce qui garantit leur passivité (patron MVP « Passive View »).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# Réponses possibles à la question « enregistrer les modifications ? »
ANSWER_SAVE: str = "save"
ANSWER_DISCARD: str = "discard"
ANSWER_CANCEL: str = "cancel"


@dataclass(frozen=True)
class EntryRow:
    """Ligne affichée dans la table principale.

    :param entry_id: identifiant de l'élément.
    :param entry_type: type (Note, Warning...).
    :param code: code de l'élément.
    :param file_name: fichier source cité.
    :param line: ligne dans le fichier source (texte).
    :param description: description.
    :param status_label: libellé de la catégorie (vide si non classé).
    :param status_color: couleur de la catégorie (vide si non classé).
    :param author: auteur de la justification.
    :param log_name: nom court du log d'origine.
    """

    entry_id: int
    entry_type: str
    code: str
    file_name: str
    line: str
    description: str
    status_label: str
    status_color: str
    author: str
    log_name: str


@dataclass(frozen=True)
class EntryGroupView:
    """Groupe d'éléments affiché comme une ligne repliable.

    :param value: valeur commune du groupe (identifie le groupe).
    :param rows: éléments du groupe.
    :param unclassified: nombre d'éléments non justifiés du groupe.
    """

    value: str
    rows: Tuple[EntryRow, ...]
    unclassified: int


@dataclass(frozen=True)
class GroupingChoice:
    """Critère de regroupement proposé dans la barre de filtres.

    :param key: identifiant du critère.
    :param label: libellé affiché.
    """

    key: str
    label: str


@dataclass(frozen=True)
class CategoryItem:
    """Entrée du panneau des catégories.

    :param key: identifiant de catégorie (ou catégorie spéciale).
    :param label: libellé affiché.
    :param count: nombre d'éléments.
    :param color: couleur associée (vide = neutre).
    :param tooltip: description de la catégorie.
    """

    key: str
    label: str
    count: int
    color: str = ""
    tooltip: str = ""


@dataclass(frozen=True)
class StatusChoice:
    """Catégorie proposée dans les dialogues de justification.

    :param status_id: identifiant.
    :param label: libellé.
    :param description: description (infobulle).
    """

    status_id: str
    label: str
    description: str


@dataclass(frozen=True)
class EntryDetails:
    """Contenu du panneau de détails pour la sélection courante.

    :param title: titre du panneau.
    :param fields: couples (libellé, valeur) à afficher.
    :param raw_text: ligne brute du log.
    :param status_label: catégorie (vide si non classé).
    :param status_color: couleur de la catégorie.
    :param justification_text: texte de justification.
    :param author: auteur.
    :param timestamp: date.
    :param source: origine.
    """

    title: str
    fields: Tuple[Tuple[str, str], ...]
    raw_text: str
    status_label: str = ""
    status_color: str = ""
    justification_text: str = ""
    author: str = ""
    timestamp: str = ""
    source: str = ""


@dataclass(frozen=True)
class ActionsState:
    """Disponibilité des actions selon la sélection et la session.

    :param has_plugin: un plugin est chargé.
    :param has_entries: des éléments sont chargés.
    :param has_selection: au moins un élément est sélectionné.
    :param single_selection: exactement un élément est sélectionné.
    :param selection_classified: la sélection contient un élément classé.
    :param can_open_documentation: la documentation est disponible.
    :param can_open_source: le fichier source de l'élément est trouvé.
    :param has_justifications: des justifications existent.
    """

    has_plugin: bool = False
    has_entries: bool = False
    has_selection: bool = False
    single_selection: bool = False
    selection_classified: bool = False
    can_open_documentation: bool = False
    can_open_source: bool = False
    has_justifications: bool = False


@dataclass(frozen=True)
class JustificationRequest:
    """Saisie renvoyée par le dialogue de justification.

    :param status_id: catégorie choisie.
    :param text: justification.
    :param apply_to_same_code: étendre à tous les éléments du même code.
    """

    status_id: str
    text: str
    apply_to_same_code: bool


@dataclass(frozen=True)
class StatusBarInfo:
    """Informations de la barre d'état.

    :param user_name: utilisateur courant.
    :param tool_name: outil du plugin chargé.
    :param total: nombre total d'éléments.
    :param unclassified: éléments non justifiés.
    :param ratio_text: taux de classement formaté.
    """

    user_name: str
    tool_name: str
    total: int
    unclassified: int
    ratio_text: str


@dataclass(frozen=True)
class RegexTestRow:
    """Ligne de résultat du testeur de regex.

    :param line_number: ligne de l'exemple.
    :param extracted: valeur extraite.
    :param start: début de la correspondance.
    :param end: fin de la correspondance.
    """

    line_number: int
    extracted: str
    start: int
    end: int


@dataclass(frozen=True)
class PluginTypeData:
    """Données éditables d'un type d'élément dans l'éditeur de plugin.

    :param name: nom du type.
    :param detect_regex: regex de détection.
    :param field_regexes: couples (champ, regex).
    """

    name: str
    detect_regex: str
    field_regexes: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class PluginFormData:
    """Contenu complet du formulaire de l'éditeur de plugin.

    :param tool_name: nom de l'outil.
    :param pdf_documentation: chemin du PDF.
    :param pdf_page_index: chemin de l'index des pages.
    :param types: types d'éléments.
    :param file_extensions: extensions des logs, telles que saisies (ex. « .log, .mx »).
    """

    tool_name: str
    pdf_documentation: str
    pdf_page_index: str
    types: Tuple[PluginTypeData, ...]
    file_extensions: str = ""


@dataclass(frozen=True)
class WizardMarkView:
    """Zone sélectionnée dans l'assistant regex.

    :param label: « Code », « Fichier »… ou « Partie variable ignorée ».
    :param text: texte sélectionné.
    :param start: début dans la ligne.
    :param end: fin dans la ligne.
    :param ignored: ``True`` pour une partie variable sans intérêt.
    """

    label: str
    text: str
    start: int
    end: int
    ignored: bool


@dataclass(frozen=True)
class WizardCheckRow:
    """Ligne du tableau de vérification de l'assistant regex.

    :param line_number: ligne de l'exemple.
    :param values: valeurs extraites, dans l'ordre des champs.
    """

    line_number: int
    values: Tuple[str, ...]


@dataclass(frozen=True)
class AiHelpData:
    """Données initiales du dialogue d'aide IA.

    :param title: titre (type + code).
    :param prompt: prompt généré.
    :param response: réponse de l'IA (vide si aucune IA n'est branchée).
    :param statuses: catégories proposées.
    :param same_code_count: nombre d'éléments du même code.
    """

    title: str
    prompt: str
    response: str
    statuses: Tuple[StatusChoice, ...]
    same_code_count: int


@dataclass(frozen=True)
class AiSuggestionData:
    """Proposition affichée après analyse de la réponse IA.

    :param explanation: explication.
    :param assessment: analyse de gravité.
    :param status_id: statut suggéré (peut être vide).
    :param justification: justification proposée.
    """

    explanation: str
    assessment: str
    status_id: Optional[str]
    justification: str


@dataclass(frozen=True)
class MatchingSettings:
    """Règles de correspondance telles qu'affichées dans le dialogue.

    :param keys: attributs devant être identiques.
    :param ignore_case: ignorer majuscules et minuscules.
    :param mask_numbers: ignorer les nombres de la description.
    :param mask_quoted: ignorer le texte entre guillemets de la description.
    :param mask_paths: ignorer les noms de fichiers et chemins de la description.
    """

    keys: Tuple[str, ...]
    ignore_case: bool
    mask_numbers: bool
    mask_quoted: bool
    mask_paths: bool


@dataclass(frozen=True)
class MatchingKeyView:
    """Critère de comparaison proposé à l'utilisateur.

    :param key: identifiant de l'attribut.
    :param label: libellé.
    :param hint: conséquence de cocher/décocher, en une phrase.
    :param example: valeur de l'élément d'exemple.
    """

    key: str
    label: str
    hint: str
    example: str


@dataclass(frozen=True)
class MatchingPresetView:
    """Préréglage proposé dans le dialogue.

    :param key: identifiant.
    :param label: libellé.
    :param description: explication.
    """

    key: str
    label: str
    description: str


@dataclass(frozen=True)
class MatchingPreviewView:
    """Effet des règles envisagées, affiché en direct.

    :param preset_key: préréglage correspondant (vide = personnalisé).
    :param compared: couples (critère, valeur comparée) pour l'élément d'exemple.
    :param justified_before: éléments justifiés avec les règles actuelles.
    :param justified_after: éléments justifiés avec les règles envisagées.
    :param gained: couples (élément, justification qui lui serait appliquée).
    :param lost: éléments qui perdraient leur justification.
    """

    preset_key: str
    compared: Tuple[Tuple[str, str], ...]
    justified_before: int
    justified_after: int
    gained: Tuple[Tuple[str, str], ...]
    lost: Tuple[str, ...]
