"""Export Excel du travail de justification."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Sequence

from logwaver.model.exporters.report_data import ReportData
from logwaver.model.exporters.xlsx_writer import CellValue, Worksheet, XlsxWriter

LOGGER = logging.getLogger(__name__)

ENTRY_HEADER: tuple = (
    "ID", "Type", "Code", "Fichier", "Ligne", "Description", "Catégorie",
    "Justification", "Auteur", "Date", "Origine", "Log", "Ligne du log",
)
RULE_HEADER: tuple = (
    "Empreinte", "Type", "Code", "Description", "Fichier", "Catégorie",
    "Justification", "Auteur", "Date", "Origine", "Occurrences",
)
ENTRY_WRAP_COLUMNS: tuple = (5, 7)
RULE_WRAP_COLUMNS: tuple = (3, 6)


class ExcelReportExporter:
    """Exporte un :class:`ReportData` en classeur à trois feuilles."""

    def __init__(self, writer: XlsxWriter | None = None) -> None:
        """Initialise l'exporteur.

        :param writer: écrivain xlsx (injectable pour les tests).
        """
        self._writer: XlsxWriter = writer or XlsxWriter()

    def export(self, report: ReportData, path: Path) -> None:
        """Écrit le classeur.

        :param report: données à exporter.
        :param path: fichier .xlsx de destination.
        :raises ExportError: si l'écriture échoue.
        """
        sheets = [
            self._summary_sheet(report),
            self._entries_sheet(report),
            self._rules_sheet(report),
        ]
        self._writer.write(sheets, path)
        LOGGER.info("Export Excel réalisé : %s", path)

    @staticmethod
    def _summary_sheet(report: ReportData) -> Worksheet:
        """Construit la feuille de synthèse (types × catégories).

        :param report: données du rapport.
        :return: feuille de synthèse.
        """
        summary = report.summary
        labels = [report.category_labels.get(cid, cid)
                  for cid in summary.category_ids]
        rows: List[Sequence[CellValue]] = []
        for row_index, type_name in enumerate(summary.type_names):
            counts = [int(value) for value in summary.counts[row_index]]
            rows.append([type_name, *counts, int(sum(counts))])
        totals = [int(value) for value in summary.column_totals()]
        rows.append(["TOTAL", *totals, summary.total])
        rows.append([])
        rows.append(["Outil", report.tool_name])
        rows.append(["Généré le", report.generated_at])
        rows.append(["Utilisateur", report.user_name])
        rows.append(["Taux de classement",
                     f"{summary.justified_ratio() * 100:.1f} %"])
        for log_path in report.log_paths:
            rows.append(["Log analysé", log_path])
        return Worksheet("Synthèse", ["Type", *labels, "Total"], rows)

    @staticmethod
    def _entries_sheet(report: ReportData) -> Worksheet:
        """Construit la feuille détaillant chaque élément.

        :param report: données du rapport.
        :return: feuille des éléments.
        """
        rows: List[Sequence[CellValue]] = [
            [row.entry_id, row.entry_type, row.code, row.file_path, row.line,
             row.description, row.status_label, row.justification, row.author,
             row.timestamp, row.source, row.log_path, row.log_line_number]
            for row in report.entries
        ]
        return Worksheet("Éléments", ENTRY_HEADER, rows, ENTRY_WRAP_COLUMNS)

    @staticmethod
    def _rules_sheet(report: ReportData) -> Worksheet:
        """Construit la feuille des règles de justification.

        :param report: données du rapport.
        :return: feuille des justifications.
        """
        rows: List[Sequence[CellValue]] = [
            [row.fingerprint, row.entry_type, row.code, row.description,
             row.file_name, row.status_label, row.justification, row.author,
             row.timestamp, row.source, row.occurrences]
            for row in report.rules
        ]
        return Worksheet("Justifications", RULE_HEADER, rows, RULE_WRAP_COLUMNS)
