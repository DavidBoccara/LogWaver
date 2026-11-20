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
        from logwaver.model.preferences import UserPreferences
        from logwaver.model.session import WaverSession
        from logwaver.presenter.main_presenter import MainPresenter
        from logwaver.view.main_window import MainWindow
        from tests.helpers import LOG_A_PATH, PLUGIN_PATH, load_config

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session = WaverSession(load_config())
        self.window = MainWindow()
        self.window.show_error = self.fail  # aucune erreur attendue
        self.presenter = MainPresenter(
            self.window, self.session, TerminalPromptProvider(io.StringIO()),
            UserPreferences(Path(self.temp_dir.name) / "prefs.json"),
        )
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
        return self.window._table_model.rowCount()  # noqa: SLF001 - test de vue

    def test_classify_then_undo(self) -> None:
        """Classer retire l'élément de la vue ; Ctrl+Z le restaure."""
        from logwaver.view_models import JustificationRequest

        initial = self.visible_rows()
        self.assertEqual(initial, len(self.session.entries))
        self.window.ask_user_name = lambda _current: "Testeur"
        self.window.ask_justification = (
            lambda *args, **kwargs: JustificationRequest("justified", "ok", False))
        self.window._table.selectRow(0)  # noqa: SLF001 - test de vue
        self.application.processEvents()
        self.window.classify_requested.emit()
        self.application.processEvents()
        self.assertEqual(self.visible_rows(), initial - 1)
        self.window.undo_requested.emit()
        self.application.processEvents()
        self.assertEqual(self.visible_rows(), initial)


if __name__ == "__main__":
    unittest.main()
