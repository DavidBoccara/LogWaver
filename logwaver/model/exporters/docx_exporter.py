"""Export Word (python-docx) : rapport de revue des messages de log."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from logwaver.constants import CATEGORY_UNCLASSIFIED
from logwaver.model.exceptions import ExportError
from logwaver.model.exporters.report_data import ReportData

LOGGER = logging.getLogger(__name__)

TABLE_STYLE: str = "Light Grid Accent 1"
UNCLASSIFIED_COLUMNS: tuple = ("Type", "Code", "Fichier", "Ligne", "Description")
CLASSIFIED_COLUMNS: tuple = ("Type", "Code", "Description", "Catégorie",
                             "Justification", "Auteur")


class DocxReportExporter:
    """Produit un rapport Word lisible par un relecteur."""

    def export(self, report: ReportData, path: Path) -> None:
        """Écrit le rapport.

        :param report: données à exporter.
        :param path: fichier .docx de destination.
        :raises ExportError: si python-docx est absent ou si l'écriture échoue.
        """
        try:
            import docx  # import local : dépendance optionnelle à l'exécution
        except ImportError as error:
            raise ExportError(
                "La bibliothèque python-docx n'est pas installée."
            ) from error
        document = docx.Document()
        document.add_heading(f"Rapport LogWaver - {report.tool_name}", level=0)
        document.add_paragraph(
            f"Généré le {report.generated_at} par {report.user_name or 'N/A'}."
        )
        self._add_summary(document, report)
        unclassified_label = report.category_labels.get(CATEGORY_UNCLASSIFIED)
        unclassified = [row for row in report.entries
                        if row.status_label == unclassified_label]
        classified = [row for row in report.entries
                      if row.status_label != unclassified_label]
        document.add_heading(f"Éléments non justifiés ({len(unclassified)})",
                             level=1)
        self._add_table(document, UNCLASSIFIED_COLUMNS, [
            (r.entry_type, r.code, r.file_path,
             "" if r.line is None else str(r.line), r.description)
            for r in unclassified
        ])
        document.add_heading(f"Éléments classés ({len(classified)})", level=1)
        self._add_table(document, CLASSIFIED_COLUMNS, [
            (r.entry_type, r.code, r.description, r.status_label,
             r.justification, r.author)
            for r in classified
        ])
        try:
            document.save(str(path))
        except OSError as error:
            raise ExportError(
                f"Impossible d'écrire le rapport « {path} » : {error}"
            ) from error
        LOGGER.info("Rapport Word réalisé : %s", path)

    @staticmethod
    def _add_summary(document: object, report: ReportData) -> None:
        """Ajoute le tableau de synthèse.

        :param document: document python-docx.
        :param report: données du rapport.
        """
        summary = report.summary
        document.add_heading("Synthèse", level=1)  # type: ignore[attr-defined]
        header = ["Type", *[report.category_labels.get(cid, cid)
                            for cid in summary.category_ids], "Total"]
        rows = []
        for index, type_name in enumerate(summary.type_names):
            counts = [str(int(v)) for v in summary.counts[index]]
            rows.append((type_name, *counts, str(int(summary.row_totals()[index]))))
        rows.append(("TOTAL", *[str(int(v)) for v in summary.column_totals()],
                     str(summary.total)))
        DocxReportExporter._add_table(document, header, rows)

    @staticmethod
    def _add_table(document: object, header: Sequence[str],
                   rows: Sequence[Sequence[str]]) -> None:
        """Ajoute un tableau (ou une mention « aucun élément »).

        :param document: document python-docx.
        :param header: titres de colonnes.
        :param rows: lignes du tableau.
        """
        if not rows:
            document.add_paragraph("Aucun élément.")  # type: ignore[attr-defined]
            return
        table = document.add_table(rows=1, cols=len(header))  # type: ignore[attr-defined]
        try:
            table.style = TABLE_STYLE
        except (KeyError, ValueError):
            LOGGER.debug("Style de tableau « %s » indisponible.", TABLE_STYLE)
        for cell, title in zip(table.rows[0].cells, header):
            cell.text = title
        for row in rows:
            cells = table.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = value
