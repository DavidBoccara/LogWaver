"""Génère les captures d'écran de la documentation (docs/images/*.png).

Utilise uniquement PyQt5 et l'exemple TINTIN fourni ; peut tourner sans écran ::

    QT_QPA_PLATFORM=offscreen python tools/doc/captures_ecran.py
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

from logwaver.model.ai_assistant import PromptBuilder, TerminalPromptProvider  # noqa: E402
from logwaver.model.app_config import AppConfigLoader, ApplicationPaths  # noqa: E402
from logwaver.model.preferences import UserPreferences  # noqa: E402
from logwaver.model.session import WaverSession  # noqa: E402
from logwaver.presenter.main_presenter import MainPresenter  # noqa: E402
from logwaver.presenter.matching_rules_presenter import (  # noqa: E402
    MatchingRulesPresenter,
    to_settings,
)
from logwaver.presenter.plugin_editor_presenter import PluginEditorPresenter  # noqa: E402
from logwaver.presenter.regex_wizard_presenter import RegexWizardPresenter  # noqa: E402
from logwaver.view.dialogs.ai_help_dialog import AiHelpDialog  # noqa: E402
from logwaver.view.dialogs.justification_dialog import JustificationDialog  # noqa: E402
from logwaver.view.dialogs.matching_rules_dialog import MatchingRulesDialog  # noqa: E402
from logwaver.view.dialogs.plugin_editor_dialog import PluginEditorDialog  # noqa: E402
from logwaver.view.dialogs.regex_wizard_dialog import RegexWizardDialog  # noqa: E402
from logwaver.view.main_window import MainWindow  # noqa: E402
from logwaver.view.style_loader import StyleLoader  # noqa: E402
from logwaver.view_models import AiHelpData, StatusChoice  # noqa: E402

OUTPUT: Path = ROOT / "docs" / "images"
LOG_A: Path = ROOT / "samples" / "tintin_designer_a.log"
LOG_B: Path = ROOT / "samples" / "tintin_designer_b.log"
WARNING_LINE: str = ("[2026-11-20 10:01:02] WARNING CL245 src/io/loader.c:42 - le fichier "
                     "dada.txt est introuvable")


def save(widget: QWidget, name: str, application: QApplication) -> None:
    """Affiche un widget, attend le rendu et enregistre sa capture.

    :param widget: widget à capturer.
    :param name: nom du fichier (sans extension).
    :param application: application Qt.
    """
    widget.show()
    for _ in range(5):
        application.processEvents()
    widget.grab().save(str(OUTPUT / f"{name}.png"))
    print(f"capture : {name}.png")


def build_main(application: QApplication) -> tuple:
    """Crée la fenêtre principale branchée sur une session vierge.

    :param application: application Qt.
    :return: (fenêtre, session, présentateur).
    """
    session = WaverSession(AppConfigLoader().load(ROOT / "config" / "app_config.ini"))
    window = MainWindow()
    window.resize(1500, 880)
    presenter = MainPresenter(window, session, TerminalPromptProvider(io.StringIO()),
                              UserPreferences(Path(tempfile.mkdtemp()) / "p.json"),
                              ApplicationPaths.from_root(ROOT))
    return window, session, presenter


def main() -> int:
    """Produit toutes les captures.

    :return: code de sortie.
    """
    OUTPUT.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication(sys.argv)
    StyleLoader().apply(application, ROOT / "resources" / "styles" / "main.qss")

    window, session, presenter = build_main(application)
    save(window, "01_accueil", application)

    presenter.startup(None, [LOG_A], None)
    session.set_user_name("Alice")
    session.classify([e.entry_id for e in session.entries if e.code == "CL300"],
                     "justified", "Variables de mise au point, sans effet fonctionnel.")
    window.select_grouping("field:code")
    window.select_first_row()
    save(window, "02_liste_groupee", application)

    window.select_grouping("none")
    categories = window._category_panel._list  # noqa: SLF001 - clic simulé
    categories.setCurrentRow(categories.count() - 1)  # « Tous les éléments »
    window.select_first_row()
    save(window, "03_liste_details", application)

    statuses = [StatusChoice(s.status_id, s.label, s.description)
                for s in session.config.statuses]
    dialog: QWidget = JustificationDialog(
        statuses, "Code « CL245 » : 2 élément(s) seront justifiés ensemble", 2, 2,
        "justified", "Fichiers optionnels : leur absence est prévue.", window)
    save(dialog, "04_justifier", application)
    dialog.close()

    entry = next(e for e in session.entries if e.code == "CL245")
    prompt = PromptBuilder().build(entry, session.config.statuses,
                                   session.entries_with_same_code(entry))
    dialog = AiHelpDialog(AiHelpData("Warning CL245", prompt, "", tuple(statuses), 2), window)
    save(dialog, "05_aide_ia", application)
    dialog.close()

    categories.setCurrentRow(0)  # « Non justifiés »
    window.tutorial_requested.emit()
    for _ in range(4):
        window.tutorial_next_requested.emit()
    window.select_grouping("field:code")
    save(window, "06_didacticiel", application)
    window.tutorial_quit_requested.emit()

    editor = PluginEditorDialog(window)
    editor_presenter = PluginEditorPresenter(editor)
    editor_presenter._open_path(ROOT / "plugins" / "tintin.ini")  # noqa: SLF001
    editor.set_sample_text(LOG_A.read_text(encoding="utf-8"))
    editor.resize(1250, 820)
    save(editor, "07_editeur_plugin", application)

    lines = LOG_A.read_text(encoding="utf-8").splitlines()
    wizard = RegexWizardDialog(["Note", "Warning", "Error"], "Warning", window)
    # Garder une référence : un présentateur détruit ne reçoit plus les signaux.
    wizard_presenter = RegexWizardPresenter(
        wizard, lines, lambda _t: ["file", "line", "code", "description"], lambda: None)
    wizard.show()
    wizard.next()
    wizard._line_list.setCurrentRow(2)  # noqa: SLF001
    wizard.next()
    for value, name in (("CL245", "code"), ("src/io/loader.c", "file"), ("42", "line"),
                        ("le fichier dada.txt est introuvable", "description")):
        start = WARNING_LINE.index(value)
        wizard.mark_requested.emit(name, start, start + len(value))
    wizard.suggest_requested.emit()
    save(wizard, "08_assistant_elements", application)
    wizard.next()
    save(wizard, "09_assistant_verification", application)
    wizard.close()
    del wizard_presenter

    session_b = WaverSession(session.config)
    session_b.load_plugin(ROOT / "plugins" / "tintin.ini")
    session_b.open_log(LOG_B)
    session_b.set_user_name("Bob")
    session.classify([e.entry_id for e in session.entries if e.code == "CL245"],
                     "justified", "Fichiers optionnels")
    rules = Path(tempfile.mkdtemp()) / "a.lwj"
    session.export_rules(rules)
    session_b.import_rules(rules)
    example = next(e for e in session_b.entries if "theme" in e.description)
    matching = MatchingRulesDialog(MatchingRulesPresenter.key_views(example, session_b),
                                   MatchingRulesPresenter.preset_views(),
                                   MatchingRulesPresenter.example_title(example), window)
    matching_presenter = MatchingRulesPresenter(matching, session_b)
    matching_presenter._example = example  # noqa: SLF001
    matching.set_settings(to_settings(session_b.matching_options))
    matching.preset_selected.emit("tolerant")
    matching.settings_changed.emit(matching.settings())
    save(matching, "10_regles_correspondance", application)

    window.set_close_guard(lambda: True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
