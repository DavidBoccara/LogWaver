"""Analyse d'un fichier de log à l'aide d'un plugin."""

from __future__ import annotations

import itertools
import logging
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

from logwaver.constants import FILE_ENCODING, LOG_FALLBACK_ENCODING
from logwaver.model.entities import LogEntry
from logwaver.model.exceptions import LogParsingError
from logwaver.model.fingerprint import FingerprintBuilder
from logwaver.model.plugin import CompiledElementType, PluginDefinition

LOGGER = logging.getLogger(__name__)


class LogParser:
    """Transforme les lignes d'un log en :class:`LogEntry`.

    Chaque ligne est testée contre les types du plugin dans leur ordre de
    déclaration : le premier type dont la regex de détection correspond
    l'emporte.
    """

    def __init__(
        self,
        plugin: PluginDefinition,
        fingerprint_builder: FingerprintBuilder,
        id_counter: "itertools.count[int]",
    ) -> None:
        """Initialise l'analyseur.

        :param plugin: plugin décrivant le format du log.
        :param fingerprint_builder: calculateur d'empreintes.
        :param id_counter: générateur partagé d'identifiants uniques.
        """
        self._plugin: PluginDefinition = plugin
        self._types: Tuple[CompiledElementType, ...] = plugin.compile()
        self._fingerprints: FingerprintBuilder = fingerprint_builder
        self._id_counter = id_counter

    def parse_file(self, path: Path) -> List[LogEntry]:
        """Analyse un fichier de log complet.

        :param path: fichier de log.
        :return: éléments extraits, dans l'ordre du fichier.
        :raises LogParsingError: si le fichier est illisible.
        """
        lines = self._read_lines(path)
        entries = list(self.parse_lines(lines, str(path.resolve())))
        LOGGER.info("%d éléments extraits de %s", len(entries), path)
        return entries

    def parse_lines(
        self, lines: Iterable[str], log_path: str
    ) -> Iterator[LogEntry]:
        """Analyse une suite de lignes.

        :param lines: lignes du log (sans contrainte de fin de ligne).
        :param log_path: chemin associé aux éléments produits.
        :return: itérateur d'éléments.
        """
        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            element_type = self._detect_type(line)
            if element_type is None:
                continue
            fields = element_type.extract_fields(line)
            type_name = element_type.definition.name
            yield LogEntry(
                entry_id=next(self._id_counter),
                tool_name=self._plugin.tool_name,
                entry_type=type_name,
                fields=fields,
                raw_text=line,
                log_path=log_path,
                log_line_number=line_number,
                fingerprint=self._fingerprints.build(
                    self._plugin.tool_name, type_name, fields
                ),
            )

    def _detect_type(self, line: str) -> CompiledElementType | None:
        """Trouve le premier type correspondant à une ligne.

        :param line: ligne de log.
        :return: type trouvé, ou ``None``.
        """
        for element_type in self._types:
            if element_type.matches(line):
                return element_type
        return None

    @staticmethod
    def _read_lines(path: Path) -> List[str]:
        """Lit un fichier texte en UTF-8, avec repli Latin-1.

        :param path: fichier à lire.
        :return: lignes du fichier.
        :raises LogParsingError: si le fichier est illisible.
        """
        try:
            try:
                return path.read_text(encoding=FILE_ENCODING).splitlines()
            except UnicodeDecodeError:
                LOGGER.warning(
                    "%s n'est pas en UTF-8, lecture en %s.",
                    path,
                    LOG_FALLBACK_ENCODING,
                )
                return path.read_text(
                    encoding=LOG_FALLBACK_ENCODING
                ).splitlines()
        except OSError as error:
            raise LogParsingError(
                f"Impossible de lire le log « {path} » : {error}"
            ) from error
