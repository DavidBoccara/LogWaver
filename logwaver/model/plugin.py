"""Définition, lecture et écriture des fichiers plugin (format INI).

Un plugin décrit, pour un outil donné, les types d'éléments à rechercher et,
pour chacun, une regex de détection ainsi qu'une regex par champ à extraire.

Exemple minimal ::

    [plugin]
    tool_name = TINTIN
    element_types = Warning, Error

    [type:Warning]
    detect = \\bWARNING\\b
    fields = file, line, code, description
    regex.code = WARNING\\s+(\\S+)
    ...

Règle d'extraction d'un champ : si la regex contient un groupe nommé
``value`` il est utilisé, sinon le premier groupe capturant, sinon la
correspondance complète.
"""

from __future__ import annotations

import configparser
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Tuple

from logwaver.constants import (
    FILE_ENCODING,
    PLUGIN_REGEX_KEY_PREFIX,
    PLUGIN_SECTION,
    PLUGIN_TYPE_SECTION_PREFIX,
)
from logwaver.model.exceptions import PluginError

LOGGER = logging.getLogger(__name__)

VALUE_GROUP_NAME: str = "value"


def value_group(pattern: Pattern[str]) -> int | str:
    """Retourne le groupe portant la valeur selon la convention des plugins.

    :param pattern: regex compilée.
    :return: ``"value"`` si ce groupe nommé existe, sinon 1 s'il existe un
        groupe capturant, sinon 0 (correspondance complète).
    """
    if VALUE_GROUP_NAME in pattern.groupindex:
        return VALUE_GROUP_NAME
    return 1 if pattern.groups >= 1 else 0


def extract_with_pattern(pattern: Pattern[str], text: str) -> Optional[str]:
    """Extrait une valeur d'un texte selon la convention des plugins.

    :param pattern: regex compilée.
    :param text: texte analysé.
    :return: valeur extraite, ou ``None`` si aucune correspondance.
    """
    match = pattern.search(text)
    if match is None:
        return None
    return (match.group(value_group(pattern)) or "").strip()


def normalize_extensions(raw: str) -> Tuple[str, ...]:
    """Normalise une liste d'extensions de fichiers saisie par l'utilisateur.

    « log, .MX ;txt » devient ``(".log", ".mx", ".txt")``.

    :param raw: extensions séparées par des virgules, points-virgules ou espaces.
    :return: extensions en minuscules, préfixées d'un point, sans doublon.
    """
    result: List[str] = []
    for item in re.split(r"[,;\s]+", raw):
        item = item.strip().lower().lstrip("*")
        if not item:
            continue
        extension = item if item.startswith(".") else f".{item}"
        if extension not in result:
            result.append(extension)
    return tuple(result)


def compile_regex(pattern_text: str, context: str) -> Pattern[str]:
    """Compile une regex en produisant un message d'erreur contextualisé.

    :param pattern_text: texte de la regex.
    :param context: description de l'emplacement (pour le message).
    :return: regex compilée.
    :raises PluginError: si la regex est invalide.
    """
    try:
        return re.compile(pattern_text)
    except re.error as error:
        raise PluginError(
            f"Regex invalide pour {context} : « {pattern_text} » ({error})"
        ) from error


@dataclass(frozen=True)
class ElementTypeDefinition:
    """Description d'un type d'élément (Note, Warning, Error...).

    :param name: nom du type.
    :param detect_regex: regex identifiant une ligne de ce type.
    :param field_regexes: regex d'extraction par champ, dans l'ordre.
    """

    name: str
    detect_regex: str
    field_regexes: Tuple[Tuple[str, str], ...]

    @property
    def field_names(self) -> Tuple[str, ...]:
        """Retourne les noms des champs extraits, dans l'ordre déclaré."""
        return tuple(name for name, _ in self.field_regexes)


@dataclass(frozen=True)
class CompiledElementType:
    """Version compilée (prête à l'emploi) d'un type d'élément.

    :param definition: définition textuelle d'origine.
    :param detect_pattern: regex de détection compilée.
    :param field_patterns: regex de champs compilées.
    """

    definition: ElementTypeDefinition
    detect_pattern: Pattern[str]
    field_patterns: Tuple[Tuple[str, Pattern[str]], ...]

    def matches(self, line: str) -> bool:
        """Indique si une ligne de log correspond à ce type.

        :param line: ligne de log.
        :return: ``True`` si la regex de détection correspond.
        """
        return self.detect_pattern.search(line) is not None

    def extract_fields(self, line: str) -> Dict[str, str]:
        """Extrait tous les champs d'une ligne.

        :param line: ligne de log déjà détectée comme de ce type.
        :return: dictionnaire champ → valeur (vide si non trouvée).
        """
        values: Dict[str, str] = {}
        for field_name, pattern in self.field_patterns:
            values[field_name] = extract_with_pattern(pattern, line) or ""
        return values


@dataclass(frozen=True)
class PluginDefinition:
    """Contenu complet d'un fichier plugin.

    :param tool_name: nom de l'outil (ex. ``TINTIN``).
    :param element_types: types d'éléments, par ordre de priorité.
    :param pdf_documentation: chemin du PDF de documentation (optionnel).
    :param pdf_page_index: chemin du fichier d'index des pages (optionnel).
    :param source_path: fichier d'origine (pour résoudre les chemins).
    :param file_extensions: extensions des logs produits par l'outil
        (ex. ``.log``, ``.mx``) : elles désignent ce plugin automatiquement.
    """

    tool_name: str
    element_types: Tuple[ElementTypeDefinition, ...]
    pdf_documentation: str = ""
    pdf_page_index: str = ""
    source_path: Optional[Path] = field(default=None, compare=False)
    file_extensions: Tuple[str, ...] = ()

    def handles_extension(self, path: Path) -> bool:
        """Indique si l'extension d'un fichier est déclarée par ce plugin.

        :param path: fichier de log.
        :return: ``True`` si l'extension est déclarée.
        """
        return path.suffix.lower() in self.file_extensions

    @property
    def type_names(self) -> Tuple[str, ...]:
        """Retourne les noms des types d'éléments."""
        return tuple(element.name for element in self.element_types)

    def resolve_path(self, raw_path: str) -> Optional[Path]:
        """Résout un chemin relatif par rapport au répertoire du plugin.

        :param raw_path: chemin tel qu'écrit dans le plugin.
        :return: chemin absolu, ou ``None`` si ``raw_path`` est vide.
        """
        if not raw_path:
            return None
        path = Path(raw_path).expanduser()
        if not path.is_absolute() and self.source_path is not None:
            path = self.source_path.parent / path
        return path.resolve()

    def compile(self) -> Tuple[CompiledElementType, ...]:
        """Compile toutes les regex du plugin.

        :return: types compilés, dans l'ordre de priorité.
        :raises PluginError: si une regex est invalide.
        """
        compiled: List[CompiledElementType] = []
        for element in self.element_types:
            detect = compile_regex(
                element.detect_regex, f"la détection du type {element.name}"
            )
            fields_compiled = tuple(
                (
                    name,
                    compile_regex(
                        regex, f"le champ « {name} » du type {element.name}"
                    ),
                )
                for name, regex in element.field_regexes
            )
            compiled.append(
                CompiledElementType(element, detect, fields_compiled)
            )
        return tuple(compiled)


class PluginLoader:
    """Lit un fichier plugin INI et le valide."""

    def load(self, path: Path) -> PluginDefinition:
        """Charge et valide un plugin.

        :param path: chemin du fichier plugin.
        :return: définition validée (regex compilables).
        :raises PluginError: si le fichier est absent ou invalide.
        """
        parser = self._create_parser()
        try:
            with path.open("r", encoding=FILE_ENCODING) as handle:
                parser.read_file(handle)
        except (OSError, configparser.Error) as error:
            raise PluginError(
                f"Impossible de lire le plugin « {path} » : {error}"
            ) from error
        definition = self.parse(parser, source_path=path.resolve())
        definition.compile()  # valide toutes les regex dès le chargement
        LOGGER.info(
            "Plugin « %s » chargé (%s)",
            definition.tool_name,
            ", ".join(definition.type_names),
        )
        return definition

    def load_from_text(self, text: str) -> PluginDefinition:
        """Charge un plugin depuis son contenu textuel (éditeur intégré).

        :param text: contenu INI.
        :return: définition validée.
        :raises PluginError: si le contenu est invalide.
        """
        parser = self._create_parser()
        try:
            parser.read_string(text)
        except configparser.Error as error:
            raise PluginError(f"Contenu de plugin invalide : {error}") from error
        definition = self.parse(parser, source_path=None)
        definition.compile()
        return definition

    def parse(
        self, parser: configparser.ConfigParser, source_path: Optional[Path]
    ) -> PluginDefinition:
        """Construit la définition à partir d'une configuration INI.

        :param parser: configuration déjà lue.
        :param source_path: fichier d'origine, si connu.
        :return: définition du plugin.
        :raises PluginError: si une information obligatoire manque.
        """
        if not parser.has_section(PLUGIN_SECTION):
            raise PluginError(f"Section [{PLUGIN_SECTION}] manquante.")
        tool_name = parser.get(PLUGIN_SECTION, "tool_name", fallback="").strip()
        if not tool_name:
            raise PluginError("« tool_name » est obligatoire dans [plugin].")
        type_names = [
            name.strip()
            for name in parser.get(PLUGIN_SECTION, "element_types",
                                   fallback="").split(",")
            if name.strip()
        ]
        if not type_names:
            raise PluginError("« element_types » doit lister au moins un type.")
        element_types = tuple(
            self._parse_element_type(parser, name) for name in type_names
        )
        return PluginDefinition(
            tool_name=tool_name,
            element_types=element_types,
            pdf_documentation=parser.get(
                PLUGIN_SECTION, "pdf_documentation", fallback=""
            ).strip(),
            pdf_page_index=parser.get(
                PLUGIN_SECTION, "pdf_page_index", fallback=""
            ).strip(),
            source_path=source_path,
            file_extensions=normalize_extensions(
                parser.get(PLUGIN_SECTION, "file_extensions", fallback="")),
        )

    @staticmethod
    def _create_parser() -> configparser.ConfigParser:
        """Crée un lecteur INI adapté aux regex (sans interpolation).

        :return: lecteur configuré (clés sensibles à la casse).
        """
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # type: ignore[assignment]
        return parser

    @staticmethod
    def _parse_element_type(
        parser: configparser.ConfigParser, type_name: str
    ) -> ElementTypeDefinition:
        """Lit la section d'un type d'élément.

        :param parser: configuration déjà lue.
        :param type_name: nom du type.
        :return: définition du type.
        :raises PluginError: si la section ou une regex manque.
        """
        section = f"{PLUGIN_TYPE_SECTION_PREFIX}{type_name}"
        if not parser.has_section(section):
            raise PluginError(f"Section [{section}] manquante.")
        detect = parser.get(section, "detect", fallback="").strip()
        if not detect:
            raise PluginError(f"« detect » est obligatoire dans [{section}].")
        field_names = [
            name.strip()
            for name in parser.get(section, "fields", fallback="").split(",")
            if name.strip()
        ]
        field_regexes: List[Tuple[str, str]] = []
        for field_name in field_names:
            key = f"{PLUGIN_REGEX_KEY_PREFIX}{field_name}"
            regex = parser.get(section, key, fallback="").strip()
            if not regex:
                raise PluginError(
                    f"« {key} » manquant dans [{section}] alors que le champ "
                    f"« {field_name} » est déclaré."
                )
            field_regexes.append((field_name, regex))
        return ElementTypeDefinition(type_name, detect, tuple(field_regexes))


class PluginWriter:
    """Sérialise une définition de plugin au format INI lisible."""

    HEADER: str = (
        "# Fichier plugin LogWaver - modifiable à la main.\n"
        "# Pour chaque champ : groupe nommé (?P<value>...) sinon premier\n"
        "# groupe capturant, sinon correspondance complète.\n\n"
    )

    def to_text(self, definition: PluginDefinition) -> str:
        """Produit le texte INI d'un plugin.

        :param definition: définition à sérialiser.
        :return: contenu INI.
        """
        lines: List[str] = [self.HEADER, f"[{PLUGIN_SECTION}]"]
        lines.append(f"tool_name = {definition.tool_name}")
        lines.append(f"element_types = {', '.join(definition.type_names)}")
        lines.append(f"file_extensions = {', '.join(definition.file_extensions)}")
        lines.append(f"pdf_documentation = {definition.pdf_documentation}")
        lines.append(f"pdf_page_index = {definition.pdf_page_index}")
        for element in definition.element_types:
            lines.append("")
            lines.append(f"[{PLUGIN_TYPE_SECTION_PREFIX}{element.name}]")
            lines.append(f"detect = {element.detect_regex}")
            lines.append(f"fields = {', '.join(element.field_names)}")
            for field_name, regex in element.field_regexes:
                lines.append(f"{PLUGIN_REGEX_KEY_PREFIX}{field_name} = {regex}")
        return "\n".join(lines) + "\n"

    def save(self, definition: PluginDefinition, path: Path) -> None:
        """Écrit un plugin sur disque.

        :param definition: définition à écrire.
        :param path: fichier de destination.
        :raises PluginError: si l'écriture échoue.
        """
        try:
            path.write_text(self.to_text(definition), encoding=FILE_ENCODING)
        except OSError as error:
            raise PluginError(
                f"Impossible d'écrire le plugin « {path} » : {error}"
            ) from error
        LOGGER.info("Plugin enregistré : %s", path)
