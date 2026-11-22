"""Détection automatique du plugin adapté à un fichier de log.

L'utilisateur n'a pas besoin de savoir quel plugin choisir :

1. **par l'extension** : un plugin qui déclare l'extension du log
   (``file_extensions = .log, .mx``) est choisi ; si plusieurs la déclarent,
   celui qui reconnaît le plus de lignes l'emporte ;
2. **par le contenu** : si les plugins de cette extension ne reconnaissent
   aucune ligne alors qu'un autre plugin en reconnaît, ce dernier est retenu
   (une extension courante comme ``.log`` ne doit pas masquer le bon plugin) ;
3. si rien ne reconnaît le contenu, le plugin de l'extension reste choisi :
   l'utilisateur l'a explicitement déclaré.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from logwaver.constants import FILE_ENCODING, LOG_FALLBACK_ENCODING, PLUGIN_FILE_EXTENSION
from logwaver.model.exceptions import LogWaverError, PluginError
from logwaver.model.plugin import PluginDefinition, PluginLoader, normalize_extensions

LOGGER = logging.getLogger(__name__)

MAX_SAMPLE_LINES: int = 2000
REASON_EXTENSION: str = "extension"
REASON_CONTENT: str = "contenu"
EXTENSIONS_LINE = re.compile(r"^\s*file_extensions\s*=.*$", re.MULTILINE)
TOOL_NAME_LINE = re.compile(r"^\s*tool_name\s*=.*$", re.MULTILINE)


@dataclass(frozen=True)
class PluginCandidate:
    """Plugin testé sur un log.

    :param path: fichier plugin.
    :param definition: plugin chargé.
    :param matched_lines: nombre de lignes reconnues dans l'échantillon.
    :param reason: ``REASON_EXTENSION`` ou ``REASON_CONTENT``.
    """

    path: Path
    definition: PluginDefinition
    matched_lines: int
    reason: str = REASON_CONTENT


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
        candidates = self._candidates(lines)
        by_extension = [c for c in candidates if c.definition.handles_extension(log_path)]
        by_content = [c for c in candidates if c.matched_lines]
        best_extension = max(by_extension, key=lambda c: c.matched_lines, default=None)
        best_content = max(by_content, key=lambda c: c.matched_lines, default=None)
        if best_extension is not None and (best_extension.matched_lines or best_content is None):
            best: Optional[PluginCandidate] = PluginCandidate(
                best_extension.path, best_extension.definition,
                best_extension.matched_lines, REASON_EXTENSION)
        else:
            best = best_content
        if best is not None:
            LOGGER.info("Plugin choisi pour %s : %s (%s, %d lignes reconnues)",
                        log_path.name, best.definition.tool_name, best.reason,
                        best.matched_lines)
        return best

    def available_plugins(self) -> List[PluginCandidate]:
        """Liste les plugins valides des dossiers (pour un choix manuel).

        :return: plugins disponibles (score nul).
        """
        return self._candidates([])

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


class PluginExtensionRegistrar:
    """Ajoute une extension de fichier à un plugin en préservant le fichier.

    Seule la ligne ``file_extensions`` est modifiée (ou insérée après
    ``tool_name``) : les commentaires et la mise en forme écrits à la main
    sont conservés.
    """

    def add_extension(self, plugin_path: Path, extension: str) -> Tuple[str, ...]:
        """Déclare une extension supplémentaire dans un plugin.

        :param plugin_path: fichier plugin à modifier.
        :param extension: extension à ajouter (ex. ``.mx``).
        :return: extensions déclarées après modification.
        :raises LogWaverError: si l'extension est vide ou le fichier non modifiable.
        """
        new = normalize_extensions(extension)
        if not new:
            raise LogWaverError("Le fichier n'a pas d'extension à mémoriser.")
        try:
            text = plugin_path.read_text(encoding=FILE_ENCODING)
        except OSError as error:
            raise LogWaverError(f"Plugin illisible « {plugin_path} » : {error}") from error
        definition = PluginLoader().load(plugin_path)
        extensions = tuple(dict.fromkeys(definition.file_extensions + new))
        line = f"file_extensions = {', '.join(extensions)}"
        if EXTENSIONS_LINE.search(text):
            text = EXTENSIONS_LINE.sub(line, text, count=1)
        elif TOOL_NAME_LINE.search(text):
            text = TOOL_NAME_LINE.sub(lambda m: f"{m.group(0)}\n{line}", text, count=1)
        else:
            raise LogWaverError(f"« tool_name » introuvable dans {plugin_path}.")
        try:
            plugin_path.write_text(text, encoding=FILE_ENCODING)
        except OSError as error:
            raise LogWaverError(
                f"Impossible de modifier le plugin « {plugin_path} » : {error}") from error
        PluginLoader().load(plugin_path)  # vérifie que le plugin reste valide
        LOGGER.info("Extension %s associée au plugin %s", new[0], plugin_path.name)
        return extensions
