"""Tests du plugin, de l'analyse des logs et des empreintes."""

from __future__ import annotations

import itertools
import unittest

from logwaver.model.app_config import MatchingOptions
from logwaver.model.exceptions import PluginError
from logwaver.model.fingerprint import FingerprintBuilder
from logwaver.model.log_parser import LogParser
from logwaver.model.plugin import PluginLoader, PluginWriter
from tests.helpers import PLUGIN_PATH, SAMPLE_WARNING_LINE


class PluginTests(unittest.TestCase):
    """Lecture, validation et réécriture des plugins."""

    def test_load_sample_plugin(self) -> None:
        """Le plugin TINTIN déclare trois types avec quatre champs."""
        plugin = PluginLoader().load(PLUGIN_PATH)
        self.assertEqual(plugin.tool_name, "TINTIN")
        self.assertEqual(plugin.type_names, ("Note", "Warning", "Error"))
        self.assertEqual(plugin.element_types[1].field_names,
                         ("file", "line", "code", "description"))

    def test_invalid_regex_is_reported(self) -> None:
        """Une regex invalide produit une PluginError explicite."""
        text = (
            "[plugin]\ntool_name = X\nelement_types = Warning\n"
            "[type:Warning]\ndetect = (\nfields = code\nregex.code = (\\S+)\n"
        )
        with self.assertRaises(PluginError):
            PluginLoader().load_from_text(text)

    def test_round_trip_through_writer(self) -> None:
        """Écrire puis relire un plugin conserve son contenu."""
        plugin = PluginLoader().load(PLUGIN_PATH)
        reloaded = PluginLoader().load_from_text(PluginWriter().to_text(plugin))
        self.assertEqual(reloaded.element_types, plugin.element_types)


class ParserTests(unittest.TestCase):
    """Extraction des champs et calcul des empreintes."""

    def setUp(self) -> None:
        """Prépare un analyseur TINTIN."""
        self.builder = FingerprintBuilder(MatchingOptions())
        self.parser = LogParser(PluginLoader().load(PLUGIN_PATH), self.builder,
                                itertools.count(1))

    def test_extracts_all_fields(self) -> None:
        """Les quatre champs d'un warning sont extraits."""
        entries = list(self.parser.parse_lines([SAMPLE_WARNING_LINE], "log.txt"))
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.entry_type, "Warning")
        self.assertEqual(entry.code, "CL245")
        self.assertEqual(entry.file_path, "src/io/loader.c")
        self.assertEqual(entry.source_line, 42)
        self.assertEqual(entry.description, "le fichier dada.txt est introuvable")

    def test_ignores_unrelated_lines(self) -> None:
        """Les lignes ne correspondant à aucun type sont ignorées."""
        entries = list(self.parser.parse_lines(["texte quelconque", ""], "log.txt"))
        self.assertEqual(entries, [])

    def test_fingerprint_ignores_line_and_directory(self) -> None:
        """L'empreinte survit au déplacement du code (ligne, répertoire)."""
        moved = SAMPLE_WARNING_LINE.replace("src/io/loader.c:42", "lib/loader.c:99")
        first, second = self.parser.parse_lines([SAMPLE_WARNING_LINE, moved], "log.txt")
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_fingerprint_depends_on_description(self) -> None:
        """Deux messages différents ont des empreintes différentes."""
        other = SAMPLE_WARNING_LINE.replace("dada.txt", "autre.txt")
        first, second = self.parser.parse_lines([SAMPLE_WARNING_LINE, other], "log.txt")
        self.assertNotEqual(first.fingerprint, second.fingerprint)


if __name__ == "__main__":
    unittest.main()
