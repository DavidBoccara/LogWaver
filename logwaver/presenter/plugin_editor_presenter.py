"""Présentateur de l'éditeur de plugin et du testeur/générateur de regex."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from logwaver.constants import FILE_ENCODING, LOG_FALLBACK_ENCODING, STANDARD_FIELDS
from logwaver.model.exceptions import LogWaverError, PluginError
from logwaver.model.plugin import (
    ElementTypeDefinition,
    PluginDefinition,
    PluginLoader,
    PluginWriter,
)
from logwaver.model.regex_tools import RegexGenerator, RegexTester
from logwaver.presenter.error_handling import guarded
from logwaver.view_models import PluginFormData, PluginTypeData, RegexTestRow, SelectionMark

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
    ) -> None:
        """Relie le dialogue aux outils de regex et de plugin.

        :param dialog: vue pilotée.
        :param on_saved: appelé avec le chemin après chaque enregistrement.
        """
        self._dialog = dialog
        self._on_saved = on_saved
        self._loader = PluginLoader()
        self._writer = PluginWriter()
        self._tester = RegexTester()
        self._generator = RegexGenerator()
        self._current_path: Optional[Path] = None
        self._marks: Dict[str, SelectionMark] = {}
        self._connect()

    def run(self, plugin_path: Optional[Path]) -> None:
        """Ouvre l'éditeur sur un plugin existant ou un modèle vierge.

        :param plugin_path: plugin à éditer (``None`` = nouveau plugin).
        """
        if plugin_path is not None:
            self._open_path(plugin_path)
        else:
            self._dialog.set_form_data(self._blank_form())
            self._dialog.set_file_label(NEW_PLUGIN_LABEL)
        self._dialog.exec_()

    def _connect(self) -> None:
        """Abonne le présentateur aux signaux du dialogue."""
        dialog = self._dialog
        dialog.open_requested.connect(self._on_open)
        dialog.save_requested.connect(self._on_save)
        dialog.save_as_requested.connect(self._on_save_as)
        dialog.validate_requested.connect(self._on_validate)
        dialog.load_sample_requested.connect(self._on_load_sample)
        dialog.test_requested.connect(self._on_test)
        dialog.mark_requested.connect(self._on_mark)
        dialog.clear_marks_requested.connect(self._on_clear_marks)
        dialog.generate_requested.connect(self._on_generate)

    def _report_error(self, message: str) -> None:
        """Affiche une erreur (utilisé par ``guarded``).

        :param message: texte de l'erreur.
        """
        self._dialog.show_error(message)

    # ======================================================= fichiers plugin
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
        path = self._dialog.ask_save_path("Enregistrer le plugin", PLUGIN_FILTER,
                                          f"{default}.ini")
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
        path = self._dialog.ask_open_path("Charger un log d'exemple", LOG_FILTER)
        if not path:
            return
        try:
            try:
                text = Path(path).read_text(encoding=FILE_ENCODING)
            except UnicodeDecodeError:
                text = Path(path).read_text(encoding=LOG_FALLBACK_ENCODING)
        except OSError as error:
            raise LogWaverError(f"Lecture impossible de « {path} » : {error}") from error
        self._dialog.set_sample_text("\n".join(text.splitlines()[:MAX_SAMPLE_LINES]))
        self._on_clear_marks()

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

    # ============================================================ génération
    @guarded
    def _on_mark(self, mark: SelectionMark) -> None:
        """Mémorise une sélection associée à un champ.

        :param mark: sélection émise par la vue.
        """
        if any(existing.line_number != mark.line_number for existing in self._marks.values()):
            self._marks.clear()
            self._dialog.show_info(
                "La sélection est sur une autre ligne : les marques précédentes "
                "ont été réinitialisées (toutes les marques doivent être sur la même ligne)."
            )
        self._marks[mark.field_name] = mark
        self._dialog.set_marks(list(self._marks.values()))

    @guarded
    def _on_clear_marks(self) -> None:
        """Efface les sélections marquées."""
        self._marks.clear()
        self._dialog.set_marks([])

    @guarded
    def _on_generate(self) -> None:
        """Génère les regex du type courant à partir des marques."""
        if not self._dialog.current_type_name():
            raise LogWaverError("Sélectionnez d'abord un type d'élément.")
        if not self._marks:
            raise LogWaverError("Marquez au moins un champ dans l'exemple.")
        line_text = next(iter(self._marks.values())).line_text
        spans = {name: (mark.start, mark.end) for name, mark in self._marks.items()}
        generated = self._generator.generate(line_text, spans)
        self._dialog.apply_generated(generated.detect_regex, generated.field_regexes)
        self._dialog.show_info(
            "Regex générées et vérifiées sur la ligne d'exemple. Contrôlez le "
            "résultat du test sur l'ensemble de l'exemple, puis ajustez si besoin "
            "(par exemple en remplaçant un mot fixe par \\S+)."
        )

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
