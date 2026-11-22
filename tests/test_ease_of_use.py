"""Tests du regroupement, de la détection automatique du plugin et du didacticiel."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from logwaver.constants import FIELD_FILE
from logwaver.model.exceptions import LogWaverError
from logwaver.model.grouping import (
    EMPTY_GROUP_LABEL,
    GROUP_BY_FILE_NAME,
    GROUP_BY_STATUS,
    GROUP_NONE,
    UNCLASSIFIED_GROUP_LABEL,
    EntryGrouper,
    field_grouping_key,
)
from logwaver.model.plugin_detector import PluginDetector
from logwaver.model.tutorial import TutorialLoader, TutorialProgress
from tests.helpers import LOG_B_PATH, PROJECT_ROOT, create_session

TUTORIAL_PATH: Path = PROJECT_ROOT / "resources" / "tutorial" / "didacticiel.ini"
KNOWN_TUTORIAL_ACTIONS: frozenset = frozenset({
    "load_sample", "show_unclassified", "show_all", "group_by_code", "group_by_file",
    "ungroup", "select_first", "justify", "undo",
})


class GroupingTests(unittest.TestCase):
    """Regroupement des éléments par valeur commune."""

    def setUp(self) -> None:
        """Ouvre le log du concepteur A."""
        self.session = create_session()
        self.grouper = EntryGrouper(self.session.justification_of,
                                    self.session.config.status_label)

    def test_group_by_code_counts_occurrences(self) -> None:
        """Chaque code forme un groupe ; les plus fréquents viennent en premier."""
        groups = self.grouper.group(self.session.entries, field_grouping_key("code"))
        sizes = {group.value: group.size for group in groups}
        self.assertEqual(sizes["CL245"], 2)
        self.assertEqual(sizes["CL300"], 2)
        self.assertEqual(sum(sizes.values()), len(self.session.entries))
        self.assertGreaterEqual(groups[0].size, groups[-1].size)

    def test_group_by_file_name(self) -> None:
        """Le regroupement par nom court rassemble tous les éléments d'un fichier."""
        groups = self.grouper.group(self.session.entries, GROUP_BY_FILE_NAME)
        loader = next(group for group in groups if group.value == "loader.c")
        self.assertEqual({e.file_name for e in loader.entries}, {"loader.c"})
        self.assertEqual(loader.size, 3)

    def test_justifying_a_group_justifies_all_its_entries(self) -> None:
        """Classer les éléments d'un groupe « fichier » les justifie tous."""
        groups = self.grouper.group(self.session.entries, field_grouping_key(FIELD_FILE))
        engine = next(group for group in groups if group.value == "src/core/engine.c")
        self.session.classify([e.entry_id for e in engine.entries], "justified", "ok")
        self.assertTrue(all(self.session.justification_of(e) for e in engine.entries))

    def test_group_by_status_and_empty_values(self) -> None:
        """Catégorie : « Non justifié » par défaut ; valeur absente : « (vide) »."""
        groups = self.grouper.group(self.session.entries, GROUP_BY_STATUS)
        self.assertEqual([g.value for g in groups], [UNCLASSIFIED_GROUP_LABEL])
        author_groups = self.grouper.group(self.session.entries, "author")
        self.assertEqual([g.value for g in author_groups], [EMPTY_GROUP_LABEL])

    def test_no_grouping_returns_nothing(self) -> None:
        """« Aucun regroupement » ne produit aucun groupe."""
        self.assertEqual(self.grouper.group(self.session.entries, GROUP_NONE), [])

    def test_custom_plugin_fields_are_offered(self) -> None:
        """Un champ propre au plugin devient un critère de regroupement."""
        options = EntryGrouper.available_options(["code", "file", "line", "module"])
        keys = [option.key for option in options]
        self.assertIn(field_grouping_key("module"), keys)
        self.assertNotIn(field_grouping_key("line"), keys)
        self.assertEqual(keys[0], GROUP_NONE)


class PluginDetectionTests(unittest.TestCase):
    """Détection automatique du plugin."""

    def test_detects_tintin(self) -> None:
        """Le plugin TINTIN est reconnu ; l'index de pages PDF est ignoré."""
        candidate = PluginDetector([PROJECT_ROOT / "plugins"]).detect(LOG_B_PATH)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.definition.tool_name, "TINTIN")
        self.assertEqual(candidate.matched_lines, 9)

    def test_unknown_log_is_not_matched(self) -> None:
        """Un log qu'aucun plugin ne reconnaît ne renvoie aucun candidat."""
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "autre.txt"
            log.write_text("rien de reconnaissable\n", encoding="utf-8")
            self.assertIsNone(PluginDetector([PROJECT_ROOT / "plugins"]).detect(log))

    def test_missing_log_raises(self) -> None:
        """Un log introuvable produit une erreur métier claire."""
        with self.assertRaises(LogWaverError):
            PluginDetector([PROJECT_ROOT / "plugins"]).detect(Path("introuvable.log"))


class TutorialTests(unittest.TestCase):
    """Contenu et progression du didacticiel."""

    def setUp(self) -> None:
        """Charge le didacticiel livré."""
        self.tutorial = TutorialLoader().load(TUTORIAL_PATH)

    def test_tutorial_is_complete(self) -> None:
        """Chaque étape a un titre, un texte et une action connue."""
        self.assertGreaterEqual(len(self.tutorial.steps), 10)
        for step in self.tutorial.steps:
            self.assertTrue(step.title and step.text, step.step_id)
            if step.action:
                self.assertIn(step.action, KNOWN_TUTORIAL_ACTIONS, step.step_id)

    def test_progress_navigation(self) -> None:
        """Navigation suivante/précédente bornée au début et à la fin."""
        progress = TutorialProgress(self.tutorial)
        self.assertTrue(progress.is_first)
        self.assertIsNone(progress.previous())
        while progress.next() is not None:
            pass
        self.assertTrue(progress.is_last)
        self.assertEqual(progress.index, progress.count - 1)


if __name__ == "__main__":
    unittest.main()
