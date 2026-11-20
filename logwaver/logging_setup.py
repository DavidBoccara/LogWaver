"""Configuration centralisée du système de journalisation (logging)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from logwaver.constants import LOG_DIRECTORY_NAME, LOG_FILE_NAME

LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
MAX_LOG_BYTES: int = 1_000_000
LOG_BACKUP_COUNT: int = 3


def configure_logging(level: int = logging.INFO) -> Path | None:
    """Configure les journaux de l'application (console + fichier tournant).

    :param level: niveau minimal de journalisation.
    :return: chemin du fichier journal, ou ``None`` si sa création a échoué.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    log_file: Path | None = Path.home() / LOG_DIRECTORY_NAME / LOG_FILE_NAME
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError as error:
        root_logger.warning("Journal fichier indisponible : %s", error)
        log_file = None
    return log_file
