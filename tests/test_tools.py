"""Tests des outils : génération de regex, prompts IA, index PDF."""

from __future__ import annotations

import io
import re
import unittest

from logwaver.model.ai_assistant import AiResponseParser, PromptBuilder, TerminalPromptProvider
from logwaver.model.exceptions import RegexGenerationError
from logwaver.model.plugin import extract_with_pattern
from logwaver.model.regex_tools import RegexGenerator, RegexTester
from tests.helpers import SAMPLE_WARNING_LINE, create_session


def spans_for(line: str, values: dict) -> dict:
    """Calcule les positions de valeurs dans une ligne.

    :param line: ligne d'exemple.
    :param values: champ → valeur attendue.
    :return: champ → (début, fin).
    """
    result = {}
    for name, value in values.items():
        start = line.index(value)
        result[name] = (start, start + len(value))
    return result


class RegexGeneratorTests(unittest.TestCase):
    """Génération automatique de regex."""

    VALUES = {"code": "CL245", "file": "src/io/loader.c", "line": "42",
              "description": "le fichier dada.txt est introuvable"}

    def test_generated_regexes_extract_selection(self) -> None:
        """Chaque regex générée extrait exactement la valeur sélectionnée."""
        generated = RegexGenerator().generate(
            SAMPLE_WARNING_LINE, spans_for(SAMPLE_WARNING_LINE, self.VALUES))
        for name, regex in generated.field_regexes:
            self.assertEqual(extract_with_pattern(re.compile(regex), SAMPLE_WARNING_LINE),
                             self.VALUES[name])

    def test_generated_regexes_generalize_to_other_lines(self) -> None:
        """Les regex fonctionnent sur une autre ligne du même format."""
        generated = RegexGenerator().generate(
            SAMPLE_WARNING_LINE, spans_for(SAMPLE_WARNING_LINE, self.VALUES))
        other = "[2027-01-02 23:59:59] WARNING CL999 a/b/c.h:7 - autre message ici"
        extracted = {name: extract_with_pattern(re.compile(regex), other)
                     for name, regex in generated.field_regexes}
        self.assertEqual(extracted, {"code": "CL999", "file": "a/b/c.h", "line": "7",
                                     "description": "autre message ici"})
        self.assertIsNotNone(re.search(generated.detect_regex, other))
        self.assertIsNone(re.search(generated.detect_regex, other.replace("WARNING", "ERROR")))

    def test_overlapping_selection_is_rejected(self) -> None:
        """Des sélections qui se chevauchent sont refusées."""
        with self.assertRaises(RegexGenerationError):
            RegexGenerator().generate(SAMPLE_WARNING_LINE, {"a": (0, 10), "b": (5, 12)})

    def test_tester_reports_invalid_regex(self) -> None:
        """Le testeur signale une regex invalide sans lever d'exception."""
        report = RegexTester().test("(", SAMPLE_WARNING_LINE)
        self.assertFalse(report.is_valid)


class AiAssistantTests(unittest.TestCase):
    """Prompts et analyse des réponses."""

    def test_prompt_contains_context(self) -> None:
        """Le prompt cite l'outil, le code, le message et les statuts."""
        session = create_session()
        entry = next(e for e in session.entries if e.code == "CL245")
        prompt = PromptBuilder("fr").build(entry, session.config.statuses,
                                           session.entries_with_same_code(entry))
        for expected in ("TINTIN", "CL245", "dada.txt", "justified", "JUSTIFICATION:"):
            self.assertIn(expected, prompt)

    def test_terminal_provider_prints_prompt(self) -> None:
        """Le fournisseur par défaut affiche le prompt et ne répond rien."""
        stream = io.StringIO()
        self.assertIsNone(TerminalPromptProvider(stream).ask("bonjour"))
        self.assertIn("bonjour", stream.getvalue())

    def test_parser_extracts_sections(self) -> None:
        """Les sections attendues sont extraites, même en Markdown."""
        suggestion = AiResponseParser().parse(
            "**EXPLICATION**: fichier absent\n**ANALYSE**: mineur\n"
            "STATUT: justified\nJUSTIFICATION: le fichier est optionnel."
        )
        self.assertEqual(suggestion.status_id, "justified")
        self.assertEqual(suggestion.justification, "le fichier est optionnel.")

    def test_parser_falls_back_to_full_text(self) -> None:
        """Une réponse libre devient la justification proposée."""
        suggestion = AiResponseParser().parse("Réponse libre.")
        self.assertEqual(suggestion.justification, "Réponse libre.")


class DocumentationTests(unittest.TestCase):
    """Localisation de la documentation PDF."""

    def test_page_lookup(self) -> None:
        """Un code connu ouvre sa page, un code inconnu la page par défaut."""
        session = create_session()
        entry = next(e for e in session.entries if e.code == "CL512")
        self.assertEqual(session.documentation_location(entry).page, 4)
        unknown = next(e for e in session.entries if e.code == "NT010")
        self.assertEqual(session.documentation_location(unknown).page, 2)


if __name__ == "__main__":
    unittest.main()
