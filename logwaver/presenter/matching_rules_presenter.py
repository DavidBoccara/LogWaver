"""Présentateur du dialogue « Règles de correspondance »."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from logwaver.constants import (
    ALLOWED_MATCH_KEYS,
    MATCH_KEY_DESCRIPTION,
    MATCH_KEY_FILE_NAME,
    MATCH_KEY_LINE,
)
from logwaver.model.app_config import MatchingOptions
from logwaver.model.entities import Justification, LogEntry
from logwaver.model.matching_presets import (
    MATCH_KEY_HINTS,
    MATCH_KEY_LABELS,
    PRESETS,
    find_preset,
)
from logwaver.model.session import WaverSession
from logwaver.presenter.error_handling import guarded
from logwaver.view_models import (
    MatchingKeyView,
    MatchingPresetView,
    MatchingPreviewView,
    MatchingSettings,
)

if TYPE_CHECKING:
    from logwaver.view.dialogs.matching_rules_dialog import MatchingRulesDialog

LOGGER = logging.getLogger(__name__)

MAX_PREVIEW_ITEMS: int = 200
NO_EXAMPLE_TITLE: str = "(ouvrez un log pour voir un exemple)"


def describe_entry(entry: LogEntry) -> str:
    """Décrit un élément en une ligne.

    :param entry: élément.
    :return: « Type Code — description (fichier:ligne) ».
    """
    location = f"{entry.file_name}:{entry.source_line}" if entry.source_line else entry.file_name
    return f"{entry.entry_type} {entry.code} — {entry.description} ({location})"


def describe_justification(justification: Justification, status_label: str) -> str:
    """Décrit une justification et l'élément qui l'a reçue.

    :param justification: justification.
    :param status_label: libellé de sa catégorie.
    :return: description en une ligne.
    """
    context = justification.context
    origin = f"{context.get(MATCH_KEY_DESCRIPTION, '')} ({context.get(MATCH_KEY_FILE_NAME, '')}"
    line = context.get(MATCH_KEY_LINE, "")
    origin += f":{line})" if line else ")"
    return f"{status_label} par {justification.author} : « {justification.text} » — sur {origin}"


def to_options(settings: MatchingSettings, base: MatchingOptions) -> MatchingOptions:
    """Convertit le réglage du dialogue en règles du modèle.

    :param settings: réglage affiché.
    :param base: règles actuelles (options non exposées conservées).
    :return: règles de correspondance.
    """
    keys = tuple(key for key in ALLOWED_MATCH_KEYS if key in settings.keys)
    return MatchingOptions(keys, base.normalize_whitespace, settings.ignore_case,
                           settings.mask_numbers, settings.mask_quoted, settings.mask_paths)


def to_settings(options: MatchingOptions) -> MatchingSettings:
    """Convertit des règles du modèle en réglage affichable.

    :param options: règles de correspondance.
    :return: réglage du dialogue.
    """
    return MatchingSettings(options.keys, options.ignore_case, options.mask_numbers,
                            options.mask_quoted, options.mask_paths)


class MatchingRulesPresenter:
    """Calcule l'aperçu en direct et applique les règles validées."""

    def __init__(self, dialog: "MatchingRulesDialog", session: WaverSession) -> None:
        """Relie le dialogue à la session.

        :param dialog: vue pilotée.
        :param session: session dont on règle la correspondance.
        """
        self._dialog = dialog
        self._session = session
        self._example: Optional[LogEntry] = None
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.preset_selected.connect(self._on_preset_selected)

    @staticmethod
    def key_views(example: Optional[LogEntry], session: WaverSession) -> list:
        """Prépare les critères proposés, illustrés par l'élément d'exemple.

        :param example: élément d'exemple (ou ``None``).
        :param session: session courante.
        :return: liste de :class:`MatchingKeyView`.
        """
        values = session.comparable_values(example, MatchingOptions()) if example else {}
        return [MatchingKeyView(key, MATCH_KEY_LABELS[key], MATCH_KEY_HINTS[key],
                                values.get(key, "")) for key in ALLOWED_MATCH_KEYS]

    @staticmethod
    def preset_views() -> list:
        """Prépare les préréglages proposés.

        :return: liste de :class:`MatchingPresetView`.
        """
        return [MatchingPresetView(p.key, p.label, p.description) for p in PRESETS]

    @staticmethod
    def example_title(example: Optional[LogEntry]) -> str:
        """Décrit l'élément d'exemple.

        :param example: élément d'exemple (ou ``None``).
        :return: description en une ligne.
        """
        return describe_entry(example) if example else NO_EXAMPLE_TITLE

    def run(self, example: Optional[LogEntry]) -> bool:
        """Affiche le dialogue et applique les règles si l'utilisateur valide.

        :param example: élément servant d'illustration (sélection courante).
        :return: ``True`` si de nouvelles règles ont été appliquées.
        """
        self._example = example
        self._dialog.set_settings(to_settings(self._session.matching_options))
        self._on_settings_changed(self._dialog.settings())
        if not self._dialog.exec_():
            return False
        options = to_options(self._dialog.settings(), self._session.matching_options)
        if options == self._session.matching_options:
            return False
        self._session.set_matching_options(options)
        return True

    def _report_error(self, message: str) -> None:
        """Journalise une erreur d'aperçu (utilisé par ``guarded``).

        :param message: texte de l'erreur.
        """
        LOGGER.error("Aperçu des règles de correspondance : %s", message)

    @guarded
    def _on_preset_selected(self, key: str) -> None:
        """Applique un préréglage aux cases du dialogue.

        :param key: préréglage choisi.
        """
        for preset in PRESETS:
            if preset.key == key:
                self._dialog.set_settings(to_settings(preset.options))
                return

    @guarded
    def _on_settings_changed(self, settings: MatchingSettings) -> None:
        """Recalcule l'aperçu pour le réglage affiché.

        :param settings: réglage affiché.
        """
        options = to_options(settings, self._session.matching_options)
        preview = self._session.preview_matching(options)
        compared = ()
        if self._example is not None:
            values = self._session.comparable_values(self._example, options)
            compared = tuple((MATCH_KEY_LABELS[key], values[key]) for key in options.keys)
        elif options.keys:
            compared = tuple((MATCH_KEY_LABELS[key], "—") for key in options.keys)
        label_of = self._session.config.status_label
        preset = find_preset(options)
        self._dialog.show_preview(MatchingPreviewView(
            preset_key=preset.key if preset else "",
            compared=compared,
            justified_before=preview.justified_before,
            justified_after=preview.justified_after,
            gained=tuple((describe_entry(entry),
                          describe_justification(j, label_of(j.status_id)))
                         for entry, j in preview.gained[:MAX_PREVIEW_ITEMS]),
            lost=tuple(describe_entry(entry) for entry in preview.lost[:MAX_PREVIEW_ITEMS]),
        ))
