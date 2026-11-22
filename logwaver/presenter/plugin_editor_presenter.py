"""Présentateur de l'éditeur de plugin et du testeur/générateur de regex."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from logwaver.constants import FILE_ENCODING, LOG_FALLBACK_ENCODING, STANDARD_FIELDS
from logwaver.model.exceptions import LogWaverError, PluginError
from logwaver.model.plugin import (
    ElementTypeDefinition,
    PluginDefinition,
    PluginLoader,
    PluginWriter,
    normalize_extensions,
)
from logwaver.model.regex_tools import RegexTester
from logwaver.presenter.error_handling import guarded
from logwaver.presenter.regex_wizard_presenter import RegexWizardPresenter
from logwaver.view_models import PluginFormData, PluginTypeData, RegexTestRow

if TYPE_CHECKING:
    from logwaver.view.dialogs.plugin_editor_dialog import PluginEditorDialog

LOGGER = logging.getLogger(__name__)

PLUGIN_FILTER: str = "Plugins LogWaver (*.ini);;Tous les fichiers (*)"
LOG_FILTER: str = "Fichiers de log (*.log *.txt *.out);;Tous les fichiers (*)"
MAX_SAMPLE_LINES: int = 500
NEW_PLUGIN_LABEL: str = "Nouveau plugin (non enregistré)"
DEFAULT_NEW_TYPES: Tuple[str, ...] = ("Note", "Warning", "Error")

SavedCallback = Callable[[Path], None]


class PluginEditorPresenter:
    """Pilote :class:`PluginEditorDialog`."""

    def __init__(
        self,
        dialog: "PluginEditorDialog",
        on_saved: Optional[SavedCallback] = None,
        default_directory: Optional[Path] = None,
    ) -> None:
        """Relie le dialogue aux outils de regex et de plugin.

        :param dialog: vue pilotée.
        :param on_saved: appelé avec le chemin après chaque enregistrement.
        :param default_directory: dossier proposé pour un nouveau plugin
            (celui où les plugins sont détectés automatiquement).
        """
        self._dialog = dialog
        self._on_saved = on_saved
        self._loader = PluginLoader()
        self._writer = PluginWriter()
        self._tester = RegexTester()
        self._default_directory = default_directory
        self._current_path: Optional[Path] = None
        self._connect()

    def run(self, plugin_path: Optional[Path]) -> None:
        """Ouvre l'éditeur sur un plugin existant ou un modèle vierge.

        :param plugin_path: plugin à éditer (``None`` = nouveau plugin).
        """
        if plugin_path is not None:
            self._open_path(plugin_path)
        else:
            self._start_blank()
        self._dialog.exec_()

    def _connect(self) -> None:
        """Abonne le présentateur aux signaux du dialogue."""
        dialog = self._dialog
        dialog.new_requested.connect(self._on_new)
        dialog.wizard_requested.connect(self._on_wizard)
        dialog.open_requested.connect(self._on_open)
        dialog.save_requested.connect(self._on_save)
        dialog.save_as_requested.connect(self._on_save_as)
        dialog.validate_requested.connect(self._on_validate)
        dialog.load_sample_requested.connect(self._on_load_sample)
        dialog.test_requested.connect(self._on_test)

    def _report_error(self, message: str) -> None:
        """Affiche une erreur (utilisé par ``guarded``).

        :param message: texte de l'erreur.
        """
        self._dialog.show_error(message)

    # ======================================================= fichiers plugin
    @guarded
    def _on_new(self) -> None:
        """Repart d'un plugin vierge (les plugins existants ne sont pas modifiés)."""
        self._start_blank()

    def _start_blank(self) -> None:
        """Affiche un formulaire vierge, non associé à un fichier."""
        self._current_path = None
        self._dialog.set_form_data(self._blank_form())
        self._dialog.set_file_label(NEW_PLUGIN_LABEL)

    @guarded
    def _on_open(self) -> None:
        """Ouvre un plugin existant."""
        path = self._dialog.ask_open_path("Ouvrir un plugin", PLUGIN_FILTER)
        if path:
            self._open_path(Path(path))

    def _open_path(self, path: Path) -> None:
        """Charge un plugin dans le formulaire.

        :param path: fichier plugin.
        :raises PluginError: si le plugin est invalide.
        """
        definition = self._loader.load(path)
        self._dialog.set_form_data(self._to_form(definition))
        self._current_path = path.resolve()
        self._dialog.set_file_label(str(self._current_path))

    @guarded
    def _on_save(self) -> None:
        """Enregistre dans le fichier courant (ou demande un fichier)."""
        if self._current_path is None:
            self._on_save_as()
        else:
            self._save_to(self._current_path)

    @guarded
    def _on_save_as(self) -> None:
        """Enregistre dans un nouveau fichier."""
        default = self._dialog.form_data().tool_name.lower() or "plugin"
        directory = (self._current_path.parent if self._current_path
                     else self._default_directory)
        default_path = str(directory / f"{default}.ini") if directory else f"{default}.ini"
        path = self._dialog.ask_save_path("Enregistrer le plugin", PLUGIN_FILTER, default_path)
        if path:
            target = Path(path)
            self._save_to(target if target.suffix else target.with_suffix(".ini"))

    def _save_to(self, path: Path) -> None:
        """Valide puis écrit le plugin.

        :param path: fichier de destination.
        :raises PluginError: si le plugin est invalide ou non écrit.
        """
        definition = self._validated_definition()
        self._writer.save(definition, path)
        self._current_path = path.resolve()
        self._dialog.set_file_label(str(self._current_path))
        if self._on_saved is not None:
            self._on_saved(self._current_path)

    @guarded
    def _on_validate(self) -> None:
        """Vérifie le plugin et rapporte son efficacité sur l'exemple."""
        definition = self._validated_definition()
        self._dialog.show_info(
            f"Plugin valide : outil « {definition.tool_name} », "
            f"{len(definition.element_types)} type(s) d'éléments."
        )

    def _validated_definition(self) -> PluginDefinition:
        """Construit et valide la définition issue du formulaire.

        :return: définition valide (regex compilables, champs complets).
        :raises PluginError: si le formulaire est incomplet ou invalide.
        """
        definition = self._from_form(self._dialog.form_data())
        return self._loader.load_from_text(self._writer.to_text(definition))

    # ========================================================== exemple/test
    @guarded
    def _on_load_sample(self) -> None:
        """Charge les premières lignes d'un log comme exemple."""
        self._ask_sample_lines()

    def _ask_sample_lines(self) -> Optional[List[str]]:
        """Demande un log d'exemple et l'affiche dans l'éditeur.

        :return: lignes chargées, ou ``None`` si l'utilisateur annule.
        :raises LogWaverError: si le fichier est illisible.
        """
        path = self._dialog.ask_open_path("Charger un log d'exemple", LOG_FILTER)
        if not path:
            return None
        try:
            try:
                text = Path(path).read_text(encoding=FILE_ENCODING)
            except UnicodeDecodeError:
                text = Path(path).read_text(encoding=LOG_FALLBACK_ENCODING)
        except OSError as error:
            raise LogWaverError(f"Lecture impossible de « {path} » : {error}") from error
        lines = text.splitlines()[:MAX_SAMPLE_LINES]
        self._dialog.set_sample_text("\n".join(lines))
        if not self._dialog.form_data().file_extensions and Path(path).suffix:
            form = self._dialog.form_data()
            self._dialog.set_form_data(PluginFormData(
                form.tool_name, form.pdf_documentation, form.pdf_page_index, form.types,
                Path(path).suffix.lower()))
        return lines

    @guarded
    def _on_wizard(self) -> None:
        """Ouvre l'assistant regex et applique son résultat au type choisi."""
        wizard = self._dialog.create_regex_wizard(self._dialog.current_type_name())
        result = RegexWizardPresenter(
            wizard,
            self._dialog.sample_text().splitlines(),
            self._dialog.type_field_names,
            self._ask_sample_lines,
        ).run()
        if result is None:
            return
        self._dialog.select_or_create_type(result.type_name)
        self._dialog.apply_generated(result.regexes.detect_regex, result.regexes.field_regexes)
        self._dialog.show_info(
            f"Les regex du type « {result.type_name} » ont été mises à jour. Pensez à "
            "enregistrer le plugin.")

    @guarded
    def _on_test(self, pattern: str, sample: str) -> None:
        """Teste la regex active sur l'exemple.

        :param pattern: regex à tester.
        :param sample: texte d'exemple.
        """
        if not pattern.strip() or not sample.strip():
            self._dialog.show_test_result([], "", False)
            return
        report = self._tester.test(pattern, sample)
        rows = [RegexTestRow(m.line_number, m.extracted, m.start, m.end)
                for m in report.matches]
        self._dialog.show_test_result(rows, report.error, report.truncated)

    # ============================================================ conversion
    @staticmethod
    def _to_form(definition: PluginDefinition) -> PluginFormData:
        """Convertit une définition en données de formulaire.

        :param definition: plugin chargé.
        :return: données de formulaire.
        """
        return PluginFormData(
            tool_name=definition.tool_name,
            pdf_documentation=definition.pdf_documentation,
            pdf_page_index=definition.pdf_page_index,
            types=tuple(
                PluginTypeData(t.name, t.detect_regex, t.field_regexes)
                for t in definition.element_types
            ),
            file_extensions=", ".join(definition.file_extensions),
        )

    @staticmethod
    def _from_form(form: PluginFormData) -> PluginDefinition:
        """Convertit les données de formulaire en définition.

        :param form: données saisies.
        :return: définition (non encore validée).
        :raises PluginError: si une information obligatoire manque.
        """
        if not form.tool_name:
            raise PluginError("Le nom de l'outil est obligatoire.")
        if not form.types:
            raise PluginError("Déclarez au moins un type d'élément.")
        element_types: List[ElementTypeDefinition] = []
        for item in form.types:
            if not item.detect_regex:
                raise PluginError(f"La regex de détection du type « {item.name} » est vide.")
            empty = [name for name, regex in item.field_regexes if not regex]
            if empty:
                raise PluginError(
                    f"Type « {item.name} » : regex manquante pour {', '.join(empty)}."
                )
            element_types.append(
                ElementTypeDefinition(item.name, item.detect_regex, item.field_regexes)
            )
        return PluginDefinition(
            tool_name=form.tool_name,
            element_types=tuple(element_types),
            pdf_documentation=form.pdf_documentation,
            pdf_page_index=form.pdf_page_index,
            file_extensions=normalize_extensions(form.file_extensions),
        )

    @staticmethod
    def _blank_form() -> PluginFormData:
        """Crée un formulaire vierge avec les types et champs standards.

        :return: données de formulaire initiales.
        """
        return PluginFormData(
            tool_name="",
            pdf_documentation="",
            pdf_page_index="",
            types=tuple(
                PluginTypeData(name, "", tuple((field, "") for field in STANDARD_FIELDS))
                for name in DEFAULT_NEW_TYPES
            ),
        )
