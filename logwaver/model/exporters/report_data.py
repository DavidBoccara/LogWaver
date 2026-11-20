"""Données de rapport communes aux exports Excel et Word."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from logwaver.model.statistics import SummaryTable


@dataclass(frozen=True)
class EntryReportRow:
    """Ligne de rapport décrivant un élément du log.

    :param entry_id: identifiant de l'élément.
    :param entry_type: type d'élément.
    :param code: code de l'élément.
    :param file_path: fichier source cité.
    :param line: ligne dans le fichier source.
    :param description: description.
    :param status_label: catégorie (libellé) ou « Non justifié ».
    :param justification: texte de justification.
    :param author: auteur de la justification.
    :param timestamp: date de la justification.
    :param source: origine de la justification.
    :param log_path: log d'origine.
    :param log_line_number: ligne dans le log.
    """

    entry_id: int
    entry_type: str
    code: str
    file_path: str
    line: Optional[int]
    description: str
    status_label: str
    justification: str
    author: str
    timestamp: str
    source: str
    log_path: str
    log_line_number: int


@dataclass(frozen=True)
class RuleReportRow:
    """Ligne de rapport décrivant une règle de justification.

    :param fingerprint: empreinte.
    :param entry_type: type d'élément d'origine.
    :param code: code d'origine.
    :param description: description d'origine.
    :param file_name: fichier d'origine.
    :param status_label: catégorie.
    :param justification: texte.
    :param author: auteur.
    :param timestamp: date.
    :param source: origine.
    :param occurrences: nombre d'occurrences dans les logs ouverts.
    """

    fingerprint: str
    entry_type: str
    code: str
    description: str
    file_name: str
    status_label: str
    justification: str
    author: str
    timestamp: str
    source: str
    occurrences: int


@dataclass(frozen=True)
class ReportData:
    """Ensemble des informations exportées.

    :param tool_name: outil analysé.
    :param generated_at: date de génération.
    :param user_name: utilisateur courant.
    :param log_paths: logs analysés.
    :param summary: tableau croisé types × catégories.
    :param category_labels: identifiant → libellé des catégories.
    :param entries: lignes des éléments.
    :param rules: lignes des règles.
    """

    tool_name: str
    generated_at: str
    user_name: str
    log_paths: Tuple[str, ...]
    summary: SummaryTable
    category_labels: Dict[str, str]
    entries: Tuple[EntryReportRow, ...]
    rules: Tuple[RuleReportRow, ...]
