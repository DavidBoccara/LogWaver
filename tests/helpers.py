"""Utilitaires partagés par les tests."""

from __future__ import annotations

from pathlib import Path

from logwaver.model.app_config import AppConfig, AppConfigLoader
from logwaver.model.session import WaverSession

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = PROJECT_ROOT / "config" / "app_config.ini"
PLUGIN_PATH: Path = PROJECT_ROOT / "plugins" / "tintin.ini"
LOG_A_PATH: Path = PROJECT_ROOT / "samples" / "tintin_designer_a.log"
LOG_B_PATH: Path = PROJECT_ROOT / "samples" / "tintin_designer_b.log"
SAMPLE_WARNING_LINE: str = (
    "[2026-11-20 10:01:02] WARNING CL245 src/io/loader.c:42 - le fichier dada.txt est introuvable"
)


def load_config() -> AppConfig:
    """Charge la configuration d'exemple.

    :return: configuration de l'application.
    """
    return AppConfigLoader().load(CONFIG_PATH)


def create_session(log_path: Path | None = LOG_A_PATH, user_name: str = "Alice") -> WaverSession:
    """Crée une session avec le plugin TINTIN et, éventuellement, un log.

    :param log_path: log à ouvrir (``None`` = aucun).
    :param user_name: utilisateur courant (vide = aucun).
    :return: session prête à l'emploi.
    """
    session = WaverSession(load_config())
    session.load_plugin(PLUGIN_PATH)
    if log_path is not None:
        session.open_log(log_path)
    if user_name:
        session.set_user_name(user_name)
    return session
