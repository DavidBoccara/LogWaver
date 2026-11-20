"""Hiérarchie d'exceptions métier de LogWaver.

Le présentateur intercepte ``LogWaverError`` pour afficher un message clair à
l'utilisateur ; toute autre exception est considérée comme un bug.
"""

from __future__ import annotations


class LogWaverError(Exception):
    """Classe de base de toutes les erreurs métier de l'application."""


class ConfigurationError(LogWaverError):
    """Le fichier de configuration de l'application est invalide."""


class PluginError(LogWaverError):
    """Le fichier plugin est absent, illisible ou invalide."""


class LogParsingError(LogWaverError):
    """Le fichier de log n'a pas pu être lu ou analysé."""


class ProjectFileError(LogWaverError):
    """Le fichier projet ou de justifications est invalide."""


class ExportError(LogWaverError):
    """L'export (Excel, Word...) a échoué."""


class RegexGenerationError(LogWaverError):
    """La génération automatique d'expressions régulières a échoué."""


class DocumentationError(LogWaverError):
    """La documentation PDF ou son index de pages est inaccessible."""
