"""Tests de la session : justification, annulation, projet, héritage."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from logwaver.constants import CATEGORY_UNCLASSIFIED, SOURCE_IMPORTED
from logwaver.model.entry_filter import FilterCriteria
from logwaver.model.exceptions import LogWaverError
from logwaver.model.session import WaverSession
from tests.helpers import LOG_A_PATH, LOG_B_PATH, create_session, load_config


class JustificationTests(unittest.TestCase):
    """Classement, retrait et annulation."""

    def setUp(self) -> None:
        """Ouvre le log du concepteur A."""
        self.session = create_session()
        self.cl245 = [e.entry_id for e in self.session.entries if e.code == "CL245"]

    def unclassified_count(self) -> int:
        """Retourne le nombre d'éléments non justifiés.

        :return: nombre d'éléments sans justification.
        """
        return len(self.session.filter_entries(FilterCriteria(category=CATEGORY_UNCLASSIFIED)))

    def test_classify_moves_entries_out_of_unclassified(self) -> None:
        """Un élément justifié quitte la liste des non justifiés."""
        before = self.unclassified_count()
        self.session.classify(self.cl245, "justified", "Fichiers optionnels")
        self.assertEqual(self.unclassified_count(), before - len(self.cl245))
        justified = self.session.filter_entries(FilterCriteria(category="justified"))
        self.assertEqual({e.entry_id for e in justified}, set(self.cl245))

    def test_justification_records_author(self) -> None:
        """La justification mémorise l'auteur."""
        self.session.classify(self.cl245[:1], "justified", "ok")
        entry = self.session.entry_by_id(self.cl245[0])
        self.assertEqual(self.session.justification_of(entry).author, "Alice")

    def test_classify_requires_user_and_text(self) -> None:
        """Nom d'utilisateur et texte sont obligatoires."""
        anonymous = create_session(user_name="")
        with self.assertRaises(LogWaverError):
            anonymous.classify([anonymous.entries[0].entry_id], "justified", "x")
        with self.assertRaises(LogWaverError):
            self.session.classify(self.cl245, "justified", "   ")

    def test_unclassify_and_undo_redo(self) -> None:
        """Retrait, annulation et rétablissement sont cohérents."""
        initial = self.unclassified_count()
        self.session.classify(self.cl245, "rejected", "À corriger")
        self.session.unclassify(self.cl245)
        self.assertEqual(self.unclassified_count(), initial)
        self.session.undo()  # annule le retrait
        self.assertEqual(self.unclassified_count(), initial - len(self.cl245))
        self.session.undo()  # annule le classement
        self.assertEqual(self.unclassified_count(), initial)
        self.session.redo()
        self.assertEqual(self.unclassified_count(), initial - len(self.cl245))

    def test_dirty_flag_follows_history(self) -> None:
        """L'état « modifié » suit l'enregistrement et l'historique."""
        with tempfile.TemporaryDirectory() as directory:
            self.session.save_project(Path(directory) / "p.lwp")
            self.assertFalse(self.session.is_dirty)
            self.session.classify(self.cl245, "justified", "ok")
            self.assertTrue(self.session.is_dirty)
            self.session.undo()
            self.assertFalse(self.session.is_dirty)


class ProjectAndInheritanceTests(unittest.TestCase):
    """Persistance et réutilisation des justifications entre concepteurs."""

    def test_project_reapplies_justifications_to_new_log(self) -> None:
        """Projet de A + log de B : les éléments communs sont justifiés."""
        session_a = create_session()
        session_a.classify([e.entry_id for e in session_a.entries if e.code == "CL245"],
                           "justified", "Fichiers optionnels")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "a.lwp"
            session_a.save_project(project)
            session = WaverSession(load_config())
            session.open_project(project)
            report = session.open_log(LOG_B_PATH)
        self.assertEqual(report.auto_justified_count, 2)

    def test_rules_file_transfers_to_designer_b(self) -> None:
        """Le fichier de justifications de A justifie automatiquement B."""
        session_a = create_session()
        session_a.classify([e.entry_id for e in session_a.entries
                            if e.code in ("CL245", "CL300")], "justified", "ok")
        session_b = create_session(LOG_B_PATH, user_name="Bob")
        with tempfile.TemporaryDirectory() as directory:
            rules = Path(directory) / "a.lwj"
            session_a.export_rules(rules)
            report = session_b.import_rules(rules)
        self.assertEqual(report.imported, 4)
        self.assertEqual(report.matched_entries, 3)
        sources = {j.source for j in session_b.justifications}
        self.assertEqual(sources, {SOURCE_IMPORTED})
        session_b.undo()
        self.assertEqual(len(session_b.justifications), 0)

    def test_project_round_trip_keeps_user_and_logs(self) -> None:
        """Le projet restaure utilisateur, logs et justifications."""
        session = create_session()
        session.classify([session.entries[0].entry_id], "todo", "à voir")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "p.lwp"
            session.save_project(project)
            reopened = WaverSession(load_config())
            report = reopened.open_project(project)
        self.assertEqual(report.missing_files, ())
        self.assertEqual(reopened.user_name, "Alice")
        self.assertEqual(reopened.log_paths, (str(LOG_A_PATH.resolve()),))
        self.assertEqual(len(reopened.justifications), 1)


class ExportTests(unittest.TestCase):
    """Exports Excel et Word."""

    def test_excel_export_is_valid_archive(self) -> None:
        """L'export Excel produit un classeur à trois feuilles."""
        session = create_session()
        session.classify([session.entries[0].entry_id], "justified", "ok <&> \"test\"")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "r.xlsx"
            session.export_excel(target)
            with zipfile.ZipFile(target) as archive:
                names = archive.namelist()
                self.assertIn("xl/worksheets/sheet3.xml", names)
                self.assertIn("&lt;&amp;&gt;", archive.read("xl/worksheets/sheet2.xml")
                              .decode("utf-8"))

    def test_docx_export(self) -> None:
        """L'export Word produit un fichier non vide."""
        session = create_session()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "r.docx"
            session.export_docx(target)
            self.assertGreater(target.stat().st_size, 0)

    def test_summary_counts(self) -> None:
        """Le tableau de synthèse compte tous les éléments."""
        session = create_session(LOG_A_PATH)
        self.assertEqual(session.summary().total, len(session.entries))
        self.assertAlmostEqual(session.summary().justified_ratio(), 0.0)


if __name__ == "__main__":
    unittest.main()
