"""Entités métier immuables manipulées par toute l'application."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Dict, Mapping, Optional

from logwaver.constants import (
    FIELD_CODE,
    FIELD_DESCRIPTION,
    FIELD_FILE,
    FIELD_LINE,
    SOURCE_MANUAL,
)


@dataclass(frozen=True)
class StatusDefinition:
    """Catégorie de classement définie dans le fichier de configuration.

    :param status_id: identifiant technique stable (ex. ``justified``).
    :param label: libellé affiché à l'utilisateur.
    :param description: explication du sens de la catégorie.
    :param color: couleur d'affichage au format ``#RRGGBB``.
    """

    status_id: str
    label: str
    description: str = ""
    color: str = "#9e9e9e"


@dataclass(frozen=True)
class LogEntry:
    """Élément (note, warning, erreur...) extrait d'un fichier de log.

    :param entry_id: identifiant unique dans la session courante.
    :param tool_name: nom de l'outil ayant produit le log.
    :param entry_type: type d'élément (``Warning``, ``Error``...).
    :param fields: valeurs extraites par les regex du plugin.
    :param raw_text: ligne brute du log.
    :param log_path: chemin du fichier de log d'origine.
    :param log_line_number: numéro de ligne dans le fichier de log.
    :param fingerprint: empreinte utilisée pour retrouver les justifications.
    """

    entry_id: int
    tool_name: str
    entry_type: str
    fields: Mapping[str, str]
    raw_text: str
    log_path: str
    log_line_number: int
    fingerprint: str

    @property
    def code(self) -> str:
        """Retourne le code de l'élément (chaîne vide si non extrait)."""
        return self.fields.get(FIELD_CODE, "")

    @property
    def description(self) -> str:
        """Retourne la description de l'élément (chaîne vide si absente)."""
        return self.fields.get(FIELD_DESCRIPTION, "")

    @property
    def file_path(self) -> str:
        """Retourne le chemin du fichier source cité par l'élément."""
        return self.fields.get(FIELD_FILE, "")

    @property
    def file_name(self) -> str:
        """Retourne le nom court (sans répertoire) du fichier source."""
        path = self.file_path
        return Path(path.replace("\\", "/")).name if path else ""

    @property
    def source_line(self) -> Optional[int]:
        """Retourne la ligne du fichier source, ou ``None`` si inconnue."""
        value = self.fields.get(FIELD_LINE, "").strip()
        return int(value) if value.isdigit() else None


@dataclass(frozen=True)
class Justification:
    """Règle de justification associée à une empreinte d'élément.

    Une justification est indépendante d'un log précis : elle s'applique à
    tout élément présent ou futur partageant la même empreinte. C'est le
    mécanisme qui permet l'héritage des justifications entre concepteurs.

    :param fingerprint: empreinte des éléments concernés.
    :param status_id: catégorie choisie.
    :param text: texte de justification.
    :param author: nom de l'utilisateur ayant justifié.
    :param timestamp: date ISO 8601 de la justification.
    :param source: origine (manuelle, IA, importée).
    :param context: informations descriptives (outil, type, code...) pour
        l'affichage et l'export lorsque l'élément n'est plus présent.
    """

    fingerprint: str
    status_id: str
    text: str
    author: str
    timestamp: str
    source: str = SOURCE_MANUAL
    context: Mapping[str, str] = field(default_factory=dict)

    @staticmethod
    def now_iso() -> str:
        """Retourne l'horodatage courant au format ISO 8601 (secondes)."""
        return datetime.now().isoformat(timespec="seconds")

    def with_source(self, source: str) -> "Justification":
        """Retourne une copie de la justification avec une nouvelle origine.

        :param source: nouvelle origine.
        :return: justification modifiée.
        """
        return replace(self, source=source)

    def to_dict(self) -> Dict[str, object]:
        """Sérialise la justification en dictionnaire JSON-compatible.

        :return: dictionnaire des attributs.
        """
        return {
            "fingerprint": self.fingerprint,
            "status_id": self.status_id,
            "text": self.text,
            "author": self.author,
            "timestamp": self.timestamp,
            "source": self.source,
            "context": dict(self.context),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Justification":
        """Reconstruit une justification depuis un dictionnaire.

        :param data: dictionnaire issu de :meth:`to_dict`.
        :return: justification reconstruite.
        :raises KeyError: si un attribut obligatoire est absent.
        """
        context = data.get("context", {}) or {}
        return cls(
            fingerprint=str(data["fingerprint"]),
            status_id=str(data["status_id"]),
            text=str(data["text"]),
            author=str(data.get("author", "")),
            timestamp=str(data.get("timestamp", "")),
            source=str(data.get("source", SOURCE_MANUAL)),
            context={str(k): str(v) for k, v in dict(context).items()},
        )
