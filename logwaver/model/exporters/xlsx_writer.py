"""Écriture minimale de classeurs Excel (.xlsx) avec la seule bibliothèque standard.

Les contraintes du projet interdisant ``openpyxl``, ce module génère
directement le format Office Open XML (archive ZIP de fichiers XML). Il gère :
plusieurs feuilles, textes et nombres, ligne d'en-tête en gras figée,
filtre automatique et largeurs de colonnes.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence, Union
from xml.sax.saxutils import escape

from logwaver.model.exceptions import ExportError

CellValue = Union[str, int, float, None]

MAX_SHEET_NAME_LENGTH: int = 31
MAX_COLUMN_WIDTH: int = 80
MIN_COLUMN_WIDTH: int = 8
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
ILLEGAL_XML_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
STYLE_HEADER: int = 1
STYLE_WRAP: int = 2

NS_CONTENT_TYPES: str = "http://schemas.openxmlformats.org/package/2006/content-types"
MIME_PREFIX: str = "application/vnd.openxmlformats-"
MIME_SHEET: str = MIME_PREFIX + "officedocument.spreadsheetml"
REL_TYPE_OFFICE_DOC: str = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
CONTENT_TYPES_TEMPLATE: str = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Types xmlns="{NS_CONTENT_TYPES}">'
    f'<Default Extension="rels" ContentType="{MIME_PREFIX}package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    f'<Override PartName="/xl/workbook.xml" ContentType="{MIME_SHEET}.sheet.main+xml"/>'
    f'<Override PartName="/xl/styles.xml" ContentType="{MIME_SHEET}.styles+xml"/>'
    "{sheets}</Types>"
)
SHEET_CONTENT_TYPE: str = (
    '<Override PartName="/xl/worksheets/sheet{index}.xml" '
    f'ContentType="{MIME_SHEET}.worksheet+xml"/>'
)
ROOT_RELS: str = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId1" Type="{REL_TYPE_OFFICE_DOC}" Target="xl/workbook.xml"/>'
    "</Relationships>"
)
STYLES_XML: str = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
    '<fills count="3"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FF2F4F6F"/></patternFill></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
    '<cellXfs count="3"><xf/>'
    '<xf fontId="1" fillId="2" applyFont="1" applyFill="1"/>'
    '<xf applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs>'
    "</styleSheet>"
)


@dataclass
class Worksheet:
    """Feuille de calcul à écrire.

    :param name: nom de la feuille (nettoyé automatiquement).
    :param header: ligne d'en-tête.
    :param rows: lignes de données.
    :param wrap_columns: index (0-based) des colonnes à retour à la ligne.
    """

    name: str
    header: Sequence[str]
    rows: List[Sequence[CellValue]] = field(default_factory=list)
    wrap_columns: Sequence[int] = ()


class XlsxWriter:
    """Produit un fichier .xlsx à partir de :class:`Worksheet`."""

    def write(self, sheets: Sequence[Worksheet], path: Path) -> None:
        """Écrit le classeur.

        :param sheets: feuilles, dans l'ordre d'affichage.
        :param path: fichier de destination.
        :raises ExportError: si aucune feuille n'est fournie ou si
            l'écriture échoue.
        """
        if not sheets:
            raise ExportError("Un classeur doit contenir au moins une feuille.")
        names = self._unique_sheet_names([sheet.name for sheet in sheets])
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("[Content_Types].xml",
                                 self._content_types(len(sheets)))
                archive.writestr("_rels/.rels", ROOT_RELS)
                archive.writestr("xl/workbook.xml", self._workbook(names))
                archive.writestr("xl/_rels/workbook.xml.rels",
                                 self._workbook_rels(len(sheets)))
                archive.writestr("xl/styles.xml", STYLES_XML)
                for index, sheet in enumerate(sheets, start=1):
                    archive.writestr(f"xl/worksheets/sheet{index}.xml",
                                     self._sheet_xml(sheet))
        except OSError as error:
            raise ExportError(
                f"Impossible d'écrire le classeur « {path} » : {error}"
            ) from error

    # ------------------------------------------------------------ parties
    @staticmethod
    def _content_types(sheet_count: int) -> str:
        """Construit ``[Content_Types].xml``.

        :param sheet_count: nombre de feuilles.
        :return: contenu XML.
        """
        sheets = "".join(SHEET_CONTENT_TYPE.format(index=i)
                         for i in range(1, sheet_count + 1))
        return CONTENT_TYPES_TEMPLATE.format(sheets=sheets)

    @staticmethod
    def _workbook(names: Sequence[str]) -> str:
        """Construit ``xl/workbook.xml``.

        :param names: noms (déjà nettoyés) des feuilles.
        :return: contenu XML.
        """
        sheets = "".join(
            f'<sheet name="{escape(name, {chr(34): "&quot;"})}" '
            f'sheetId="{i}" r:id="rId{i}"/>'
            for i, name in enumerate(names, start=1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{sheets}</sheets></workbook>"
        )

    @staticmethod
    def _workbook_rels(sheet_count: int) -> str:
        """Construit ``xl/_rels/workbook.xml.rels``.

        :param sheet_count: nombre de feuilles.
        :return: contenu XML.
        """
        relations = "".join(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, sheet_count + 1)
        )
        relations += (
            f'<Relationship Id="rId{sheet_count + 1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{relations}</Relationships>"
        )

    def _sheet_xml(self, sheet: Worksheet) -> str:
        """Construit le XML d'une feuille (en-tête figé + filtre automatique).

        :param sheet: feuille à sérialiser.
        :return: contenu XML.
        """
        column_count = max(len(sheet.header), 1)
        all_rows: List[Sequence[CellValue]] = [list(sheet.header), *sheet.rows]
        widths = self._column_widths(all_rows, column_count)
        cols_xml = "".join(
            f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
            for i, width in enumerate(widths, start=1)
        )
        rows_xml = "".join(
            self._row_xml(row_index, row, sheet)
            for row_index, row in enumerate(all_rows, start=1)
        )
        last_cell = f"{self._column_letter(column_count - 1)}{len(all_rows)}"
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0">'
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            "</sheetView></sheetViews>"
            f"<cols>{cols_xml}</cols>"
            f"<sheetData>{rows_xml}</sheetData>"
            f'<autoFilter ref="A1:{last_cell}"/>'
            "</worksheet>"
        )

    def _row_xml(self, row_index: int, row: Sequence[CellValue],
                 sheet: Worksheet) -> str:
        """Construit le XML d'une ligne.

        :param row_index: numéro de ligne (1 = en-tête).
        :param row: valeurs de la ligne.
        :param sheet: feuille (pour les styles de colonnes).
        :return: contenu XML.
        """
        cells = "".join(
            self._cell_xml(row_index, col_index, value,
                           self._style_for(row_index, col_index, sheet))
            for col_index, value in enumerate(row)
        )
        return f'<row r="{row_index}">{cells}</row>'

    @staticmethod
    def _style_for(row_index: int, col_index: int, sheet: Worksheet) -> int:
        """Choisit le style d'une cellule.

        :param row_index: numéro de ligne.
        :param col_index: index de colonne (0-based).
        :param sheet: feuille concernée.
        :return: index de style dans ``styles.xml``.
        """
        if row_index == 1:
            return STYLE_HEADER
        return STYLE_WRAP if col_index in sheet.wrap_columns else 0

    def _cell_xml(self, row: int, col: int, value: CellValue, style: int) -> str:
        """Construit le XML d'une cellule.

        :param row: numéro de ligne.
        :param col: index de colonne (0-based).
        :param value: valeur (texte, nombre ou ``None``).
        :param style: index de style.
        :return: contenu XML.
        """
        reference = f"{self._column_letter(col)}{row}"
        style_attr = f' s="{style}"' if style else ""
        if value is None or value == "":
            return f'<c r="{reference}"{style_attr}/>'
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c r="{reference}"{style_attr}><v>{value}</v></c>'
        text = escape(ILLEGAL_XML_CHARS.sub("", str(value)))
        return (f'<c r="{reference}" t="inlineStr"{style_attr}>'
                f'<is><t xml:space="preserve">{text}</t></is></c>')

    # ------------------------------------------------------------ utilitaires
    @staticmethod
    def _column_letter(index: int) -> str:
        """Convertit un index de colonne en lettres.

        :param index: index 0-based.
        :return: lettres Excel (A, B, ..., Z, AA...).
        """
        letters = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(ord("A") + remainder) + letters
        return letters

    @staticmethod
    def _column_widths(rows: Sequence[Sequence[CellValue]],
                       column_count: int) -> List[int]:
        """Estime la largeur de chaque colonne à partir de son contenu.

        :param rows: toutes les lignes (en-tête compris).
        :param column_count: nombre de colonnes.
        :return: largeurs en caractères.
        """
        widths = [MIN_COLUMN_WIDTH] * column_count
        for row in rows:
            for index, value in enumerate(row[:column_count]):
                longest_line = max((len(part) for part in str(value or "").split("\n")),
                                   default=0)
                widths[index] = min(MAX_COLUMN_WIDTH,
                                    max(widths[index], longest_line + 2))
        return widths

    @staticmethod
    def _unique_sheet_names(names: Sequence[str]) -> List[str]:
        """Nettoie les noms de feuilles et garantit leur unicité.

        :param names: noms souhaités.
        :return: noms valides pour Excel.
        """
        result: List[str] = []
        for name in names:
            clean = INVALID_SHEET_CHARS.sub("_", name).strip() or "Feuille"
            clean = clean[:MAX_SHEET_NAME_LENGTH]
            candidate, suffix = clean, 2
            while candidate in result:
                tail = f" ({suffix})"
                candidate = clean[:MAX_SHEET_NAME_LENGTH - len(tail)] + tail
                suffix += 1
            result.append(candidate)
        return result
