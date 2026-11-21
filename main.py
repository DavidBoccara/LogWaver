"""Point d'entrée de LogWaver.

Exemples ::

    python main.py
    python main.py --plugin plugins/tintin.ini --log samples/tintin_designer_a.log
    python main.py --project mon_projet.lwp --log nouveau.log
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

# QtWebEngine impose d'être importé AVANT la création de QApplication.
from logwaver.view.dialogs import pdf_viewer_dialog  # noqa: F401  (import anticipé)

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox

from logwaver.constants import APP_NAME, APP_ORGANIZATION
from logwaver.logging_setup import configure_logging
from logwaver.model.ai_assistant import TerminalPromptProvider
from logwaver.model.app_config import AppConfigLoader, ApplicationPaths
from logwaver.model.exceptions import LogWaverError
from logwaver.model.preferences import UserPreferences
from logwaver.model.session import WaverSession
from logwaver.presenter.main_presenter import MainPresenter
from logwaver.view.main_window import MainWindow
from logwaver.view.style_loader import StyleLoader

APPLICATION_ROOT: Path = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH: Path = APPLICATION_ROOT / "config" / "app_config.ini"
STYLESHEET_PATH: Path = APPLICATION_ROOT / "resources" / "styles" / "main.qss"
EXIT_CONFIGURATION_ERROR: int = 2

LOGGER = logging.getLogger(APP_NAME)


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Analyse les arguments de la ligne de commande.

    :param argv: arguments (``None`` = ``sys.argv``).
    :return: arguments analysés.
    """
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - suivi des messages de logs")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH,
                        help="fichier de configuration (catégories, correspondance)")
    parser.add_argument("--plugin", type=Path, help="fichier plugin à charger")
    parser.add_argument("--log", type=Path, action="append", default=[],
                        help="fichier de log à ouvrir (option répétable)")
    parser.add_argument("--project", type=Path, help="fichier projet à ouvrir")
    parser.add_argument("--debug", action="store_true", help="journalisation détaillée")
    return parser.parse_known_args(argv)[0]


def main(argv: Optional[List[str]] = None) -> int:
    """Construit les couches MVP et lance la boucle d'événements Qt.

    :param argv: arguments de la ligne de commande.
    :return: code de sortie du processus.
    """
    arguments = parse_arguments(argv)
    log_file = configure_logging(logging.DEBUG if arguments.debug else logging.INFO)
    LOGGER.info("Démarrage de %s (journal : %s)", APP_NAME, log_file)

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setOrganizationName(APP_ORGANIZATION)
    StyleLoader().apply(application, STYLESHEET_PATH)

    try:
        config = AppConfigLoader().load(arguments.config)
    except LogWaverError as error:
        LOGGER.critical("Configuration invalide : %s", error)
        QMessageBox.critical(None, APP_NAME, str(error))
        return EXIT_CONFIGURATION_ERROR

    session = WaverSession(config)
    window = MainWindow()
    presenter = MainPresenter(window, session, TerminalPromptProvider(), UserPreferences(),
                              ApplicationPaths.from_root(APPLICATION_ROOT))
    window.show()
    presenter.startup(arguments.plugin, arguments.log, arguments.project)
    exit_code = application.exec_()
    LOGGER.info("Arrêt de %s (code %d)", APP_NAME, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
