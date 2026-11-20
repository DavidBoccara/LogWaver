"""Index « code d'élément → page » de la documentation PDF d'un outil."""

from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from logwaver.constants import FILE_ENCODING, PDF_INDEX_SECTION
from logwaver.model.exceptions import DocumentationError
from logwaver.model.plugin import PluginDefinition

LOGGER = logging.getLogger(__name__)

DEFAULT_PAGE_KEY: str = "default_page"


@dataclass(frozen=True)
class PdfLocation:
    """Emplacement à ouvrir dans la documentation.

    :param pdf_path: fichier PDF.
    :param page: numéro de page (1 = première page).
    """

    pdf_path: Path
    page: int


class PdfPageIndex:
    """Associe un code d'élément à une page du PDF de documentation."""

    def __init__(self, pages: Dict[str, int], default_page: int = 1) -> None:
        """Initialise l'index.

        :param pages: correspondance code → page.
        :param default_page: page ouverte pour un code inconnu.
        """
        self._pages: Dict[str, int] = dict(pages)
        self._default_page: int = default_page

    def page_for(self, code: str) -> Optional[int]:
        """Retourne la page associée à un code.

        :param code: code de l'élément.
        :return: page trouvée, ou ``None`` si le code est inconnu.
        """
        return self._pages.get(code.strip())

    @property
    def default_page(self) -> int:
        """Retourne la page par défaut."""
        return self._default_page

    @classmethod
    def load(cls, path: Path) -> "PdfPageIndex":
        """Charge un index au format INI (section ``[pages]``).

        :param path: fichier d'index.
        :return: index chargé.
        :raises DocumentationError: si le fichier est illisible.
        """
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # type: ignore[assignment]
        try:
            with path.open("r", encoding=FILE_ENCODING) as handle:
                parser.read_file(handle)
        except (OSError, configparser.Error) as error:
            raise DocumentationError(
                f"Index PDF illisible « {path} » : {error}"
            ) from error
        pages: Dict[str, int] = {}
        default_page = 1
        if parser.has_section(PDF_INDEX_SECTION):
            for code, raw_page in parser.items(PDF_INDEX_SECTION):
                try:
                    page = int(raw_page)
                except ValueError:
                    LOGGER.warning("Page invalide pour %s : %s", code, raw_page)
                    continue
                if code == DEFAULT_PAGE_KEY:
                    default_page = page
                else:
                    pages[code] = page
        return cls(pages, default_page)


class DocumentationLocator:
    """Détermine le PDF et la page à ouvrir pour un code donné."""

    def __init__(self, plugin: PluginDefinition) -> None:
        """Prépare le localisateur à partir du plugin.

        :param plugin: plugin courant (chemins du PDF et de l'index).
        """
        self._pdf_path: Optional[Path] = plugin.resolve_path(
            plugin.pdf_documentation
        )
        self._index_path: Optional[Path] = plugin.resolve_path(
            plugin.pdf_page_index
        )
        self._index: Optional[PdfPageIndex] = None

    @property
    def is_available(self) -> bool:
        """Indique si une documentation PDF est déclarée dans le plugin."""
        return self._pdf_path is not None

    def locate(self, code: str) -> PdfLocation:
        """Retourne l'emplacement de la documentation d'un code.

        :param code: code de l'élément.
        :return: PDF et page à ouvrir.
        :raises DocumentationError: si le PDF est absent.
        """
        if self._pdf_path is None:
            raise DocumentationError(
                "Aucune documentation PDF n'est déclarée dans le plugin."
            )
        if not self._pdf_path.is_file():
            raise DocumentationError(
                f"Documentation PDF introuvable : {self._pdf_path}"
            )
        index = self._get_index()
        page = index.page_for(code) if index else None
        if page is None:
            LOGGER.info("Code « %s » absent de l'index PDF.", code)
            page = index.default_page if index else 1
        return PdfLocation(self._pdf_path, page)

    def _get_index(self) -> Optional[PdfPageIndex]:
        """Charge l'index des pages à la première utilisation.

        :return: index, ou ``None`` si aucun index n'est déclaré.
        """
        if self._index is None and self._index_path is not None:
            self._index = PdfPageIndex.load(self._index_path)
        return self._index
