"""Test d'interface hors écran : la fenêtre se construit et le flux principal fonctionne.

Ignoré automatiquement si PyQt5 n'est pas installé. La CI l'exécute avec
``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
except ImportError:  # pragma: no cover - dépend de l'environnement
    QApplication = None  # type: ignore[assignment,misc]


@unittest.skipIf(QApplication is None, "PyQt5 non installé")
class MainWindowSmokeTests(unittest.TestCase):
    """Construit la fenêtre réelle et pilote le présentateur via ses signaux."""

    @classmethod
    def setUpClass(cls) -> None:
        """Crée l'application Qt partagée par les tests."""
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        """Assemble les couches MVP avec le plugin et le log d'exemple."""
        from logwaver.model.ai_assistant import TerminalPromptProvider
        from logwaver.model.app_config import ApplicationPaths
        from logwaver.model.preferences import UserPreferences
        from logwaver.model.session import WaverSession
        from logwaver.presenter.main_presenter import MainPresenter
        from logwaver.view.main_window import MainWindow
        from tests.helpers import LOG_A_PATH, PLUGIN_PATH, PROJECT_ROOT, load_config

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session = WaverSession(load_config())
        self.window = MainWindow()
        self.window.show_error = self.fail  # aucune erreur attendue
        self.presenter = MainPresenter(
            self.window, self.session, TerminalPromptProvider(io.StringIO()),
            UserPreferences(Path(self.temp_dir.name) / "prefs.json"),
            ApplicationPaths.from_root(PROJECT_ROOT),
        )
        self.window.show()
        self.presenter.startup(PLUGIN_PATH, [LOG_A_PATH], None)
        self.application.processEvents()

    def tearDown(self) -> None:
        """Ferme la fenêtre sans demande de confirmation."""
        self.window.set_close_guard(lambda: True)
        self.window.close()
        self.temp_dir.cleanup()

    def visible_rows(self) -> int:
        """Retourne le nombre de lignes affichées.

        :return: nombre de lignes de la table.
        """
        return self.window._tree.row_count  # noqa: SLF001 - test de vue

    def test_classify_then_undo(self) -> None:
        """Classer retire l'élément de la vue ; Ctrl+Z le restaure."""
        from logwaver.view_models import JustificationRequest

        initial = self.visible_rows()
        self.assertEqual(initial, len(self.session.entries))
        self.window.ask_user_name = lambda _current: "Testeur"
        self.window.ask_justification = (
            lambda *args, **kwargs: JustificationRequest("justified", "ok", False))
        self.window.select_first_row()
        self.application.processEvents()
        self.window.classify_requested.emit()
        self.application.processEvents()
        self.assertEqual(self.visible_rows(), initial - 1)
        self.window.undo_requested.emit()
        self.application.processEvents()
        self.assertEqual(self.visible_rows(), initial)

    def test_justify_whole_group(self) -> None:
        """Sélectionner un groupe « code » justifie tous ses éléments d'un coup."""
        from logwaver.view_models import JustificationRequest

        self.window.ask_user_name = lambda _current: "Testeur"
        self.window.ask_justification = (
            lambda *args, **kwargs: JustificationRequest("justified", "ok", False))
        self.window.select_grouping("field:code")
        self.window.select_first_row()
        self.application.processEvents()
        selected = self.window.selected_entry_ids()
        self.assertGreater(len(selected), 1)
        self.window.classify_requested.emit()
        self.application.processEvents()
        entries = self.session.entries_by_ids(selected)
        self.assertTrue(all(self.session.justification_of(e) for e in entries))

    def test_tutorial_runs_to_the_end(self) -> None:
        """Le didacticiel se déroule jusqu'au bout, actions comprises, sans erreur."""
        from logwaver.view_models import JustificationRequest

        self.window.ask_user_name = lambda _current: "Testeur"
        self.window.ask_justification = (
            lambda *args, **kwargs: JustificationRequest("justified", "ok", False))
        self.window.ask_unsaved_changes = lambda: "discard"
        tutorial = self.presenter._tutorial  # noqa: SLF001 - test de présentateur
        self.assertIsNotNone(tutorial)
        self.window.tutorial_requested.emit()
        self.assertTrue(tutorial.is_running)
        steps = 0
        while tutorial.is_running and steps < 50:
            self.window.tutorial_action_requested.emit()
            self.window.tutorial_next_requested.emit()
            self.application.processEvents()
            steps += 1
        self.assertFalse(tutorial.is_running)
        self.assertGreaterEqual(steps, 10)


if __name__ == "__main__":
    unittest.main()
