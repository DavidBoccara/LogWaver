"""Détection automatique du plugin adapté à un fichier de log.

L'utilisateur n'a plus besoin de savoir quel plugin choisir : chaque plugin
du dossier des plugins est essayé sur les premières lignes du log et celui
qui reconnaît le plus de lignes est retenu.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from logwaver.constants import FILE_ENCODING, LOG_FALLBACK_ENCODING, PLUGIN_FILE_EXTENSION
from logwaver.model.exceptions import LogWaverError, PluginError
from logwaver.model.plugin import PluginDefinition, PluginLoader

LOGGER = logging.getLogger(__name__)

MAX_SAMPLE_LINES: int = 2000


@dataclass(frozen=True)
class PluginCandidate:
    """Plugin testé sur un log.

    :param path: fichier plugin.
    :param definition: plugin chargé.
    :param matched_lines: nombre de lignes reconnues dans l'échantillon.
    """

    path: Path
    definition: PluginDefinition
    matched_lines: int


class PluginDetector:
    """Choisit, parmi un dossier de plugins, celui qui reconnaît un log."""

    def __init__(self, plugin_directories: Sequence[Path]) -> None:
        """Initialise le détecteur.

        :param plugin_directories: dossiers contenant des plugins ``.ini``.
        """
        self._directories: List[Path] = [Path(d) for d in plugin_directories]
        self._loader = PluginLoader()

    def detect(self, log_path: Path) -> Optional[PluginCandidate]:
        """Retourne le plugin reconnaissant le plus de lignes du log.

        Les fichiers ``.ini`` qui ne sont pas des plugins valides (index de
        pages PDF, plugins incomplets...) sont ignorés.

        :param log_path: log à analyser.
        :return: meilleur candidat, ou ``None`` si aucun ne reconnaît le log.
        :raises LogWaverError: si le log est illisible.
        """
        lines = self._read_sample(log_path)
        best: Optional[PluginCandidate] = None
        for candidate in self._candidates(lines):
            if candidate.matched_lines and (best is None
                                            or candidate.matched_lines > best.matched_lines):
                best = candidate
        if best is not None:
            LOGGER.info("Plugin détecté pour %s : %s (%d lignes reconnues)",
                        log_path.name, best.definition.tool_name, best.matched_lines)
        return best

    def _candidates(self, lines: Sequence[str]) -> List[PluginCandidate]:
        """Évalue chaque plugin du ou des dossiers.

        :param lines: échantillon de lignes du log.
        :return: plugins valides avec leur score.
        """
        candidates: List[PluginCandidate] = []
        for directory in self._directories:
            for path in sorted(directory.glob(f"*{PLUGIN_FILE_EXTENSION}")):
                try:
                    definition = self._loader.load(path)
                except PluginError:
                    LOGGER.debug("Ignoré (pas un plugin valide) : %s", path)
                    continue
                compiled = definition.compile()
                matched = sum(1 for line in lines
                              if any(element.matches(line) for element in compiled))
                candidates.append(PluginCandidate(path.resolve(), definition, matched))
        return candidates

    @staticmethod
    def _read_sample(log_path: Path) -> List[str]:
        """Lit les premières lignes d'un log.

        :param log_path: log à lire.
        :return: lignes de l'échantillon.
        :raises LogWaverError: si le log est illisible.
        """
        try:
            try:
                text = log_path.read_text(encoding=FILE_ENCODING)
            except UnicodeDecodeError:
                text = log_path.read_text(encoding=LOG_FALLBACK_ENCODING)
        except OSError as error:
            raise LogWaverError(f"Impossible de lire le log « {log_path} » : {error}") from error
        return text.splitlines()[:MAX_SAMPLE_LINES]
