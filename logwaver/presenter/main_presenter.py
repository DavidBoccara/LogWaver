"""Présentateur principal : orchestre la fenêtre principale et la session."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Sequence

from logwaver.constants import (
    CATEGORY_ALL,
    CATEGORY_ALL_LABEL,
    CATEGORY_UNCLASSIFIED,
    CATEGORY_UNCLASSIFIED_LABEL,
    FIELD_LABELS,
    PROJECT_FILE_EXTENSION,
    RULES_FILE_EXTENSION,
    SOURCE_AI,
    SOURCE_MANUAL,
)
from logwaver.model.ai_assistant import AiProvider, AiResponseParser, PromptBuilder
from logwaver.model.app_config import ApplicationPaths
from logwaver.model.entities import LogEntry
from logwaver.model.entry_filter import FilterCriteria
from logwaver.model.events import (
    EVENT_ENTRIES_CHANGED,
    EVENT_HISTORY_CHANGED,
    EVENT_JUSTIFICATIONS_CHANGED,
    EVENT_PROJECT_CHANGED,
)
from logwaver.model.exceptions import LogWaverError
from logwaver.model.grouping import GROUP_NONE, EntryGrouper, GroupingOption
from logwaver.model.plugin_detector import PluginDetector
from logwaver.model.preferences import UserPreferences
from logwaver.model.session import WaverSession
from logwaver.model.source_files import ExternalEditorLauncher, SourceFileReader
from logwaver.model.tutorial import TutorialLoader
from logwaver.presenter.ai_assistant_presenter import AiAssistantPresenter
from logwaver.presenter.error_handling import guarded
from logwaver.presenter.plugin_editor_presenter import PluginEditorPresenter
from logwaver.presenter.tutorial_presenter import TutorialPresenter
from logwaver.view_models import (
    ANSWER_CANCEL,
    ANSWER_SAVE,
    ActionsState,
    AiHelpData,
    CategoryItem,
    EntryDetails,
    EntryGroupView,
    EntryRow,
    GroupingChoice,
    StatusBarInfo,
    StatusChoice,
)

if TYPE_CHECKING:
    from logwaver.view.main_window import MainWindow

LOGGER = logging.getLogger(__name__)

PROJECT_FILTER: str = f"Projets LogWaver (*{PROJECT_FILE_EXTENSION});;Tous les fichiers (*)"
RULES_FILTER: str = (
    f"Justifications LogWaver (*{RULES_FILE_EXTENSION});;"
    f"Projets LogWaver (*{PROJECT_FILE_EXTENSION});;Tous les fichiers (*)"
)
PLUGIN_FILTER: str = "Plugins LogWaver (*.ini);;Tous les fichiers (*)"
LOG_FILTER: str = "Fichiers de log (*.log *.txt *.out);;Tous les fichiers (*)"
EXCEL_FILTER: str = "Classeur Excel (*.xlsx)"
WORD_FILTER: str = "Document Word (*.docx)"
UNTITLED_PROJECT: str = "Sans titre"
MAX_CODES_IN_SUMMARY: int = 10
MAX_GROUPS_IN_LABEL: int = 3

# Conseils « que faire maintenant ? » affichés au-dessus de la liste.
GUIDE_TO_JUSTIFY: str = (
    "<b>À faire :</b> {pending} élément(s) restent à justifier. Sélectionnez une ligne "
    "(ou un groupe entier) puis cliquez sur <b>✔ Justifier</b>. "
    "Astuce : « Regrouper par » rassemble les éléments identiques."
)
GUIDE_ALL_DONE: str = (
    "<b>Bravo, tout est justifié !</b> Pensez à <b>Enregistrer</b> le projet, puis "
    "à <b>Exporter vers Excel</b> ou à partager vos justifications (menu Fichier)."
)
GUIDE_CATEGORY_VIEW: str = (
    "Vous consultez la catégorie <b>{category}</b>. Pour retirer une justification, "
    "sélectionnez l'élément puis « Retirer la justification »."
)
GUIDE_EMPTY_FILTER: str = (
    "Aucun élément ne correspond aux filtres. Cliquez sur une autre catégorie à "
    "gauche ou effacez la recherche."
)
TUTORIAL_OFFER: str = (
    "Première utilisation de LogWaver ?\n\nUn didacticiel de 5 minutes vous montre, "
    "sur un exemple, comment justifier vos warnings. Le lancer maintenant ?\n\n"
    "(Il reste disponible à tout moment : menu Aide > Didacticiel.)"
)


class MainPresenter:
    """Relie :class:`MainWindow` à :class:`WaverSession`."""

    def __init__(
        self,
        view: "MainWindow",
        session: WaverSession,
        ai_provider: AiProvider,
        preferences: UserPreferences,
        paths: ApplicationPaths,
    ) -> None:
        """Initialise le présentateur et s'abonne à la vue et au modèle.

        :param view: fenêtre principale.
        :param session: session métier.
        :param ai_provider: fournisseur d'IA (terminal par défaut).
        :param preferences: préférences persistantes.
        :param paths: ressources livrées (plugins, didacticiel, exemple).
        """
        self._view = view
        self._session = session
        self._ai_provider = ai_provider
        self._preferences = preferences
        self._prompt_builder = PromptBuilder(session.config.ai_language)
        self._ai_parser = AiResponseParser()
        self._source_reader = SourceFileReader()
        self._editor = ExternalEditorLauncher(session.config.editor_command)
        self._paths = paths
        self._detector = PluginDetector([paths.plugins_directory])
        self._grouper = EntryGrouper(session.justification_of, session.config.status_label)
        self._grouping_key: str = GROUP_NONE
        self._grouping_options: List[GroupingOption] = []
        self._criteria = FilterCriteria(category=CATEGORY_UNCLASSIFIED)
        self._selected_ids: List[int] = []
        self._tutorial = self._create_tutorial()
        self._connect_view()
        self._connect_model()
        self._view.set_close_guard(self._can_close)
        self._refresh_everything()

    # ============================================================== démarrage
    @guarded
    def startup(self, plugin_path: Optional[Path], log_paths: Sequence[Path],
                project_path: Optional[Path]) -> None:
        """Applique les arguments de la ligne de commande.

        :param plugin_path: plugin à charger.
        :param log_paths: logs à ouvrir.
        :param project_path: projet à ouvrir (avant plugin et logs).
        """
        if project_path is not None:
            self._open_project_file(project_path)
        if plugin_path is not None:
            self._session.load_plugin(plugin_path)
        for log_path in log_paths:
            self._open_log_file(log_path)
        nothing_requested = project_path is None and plugin_path is None and not log_paths
        if nothing_requested and self._tutorial is not None \
                and not self._preferences.tutorial_offered:
            self._preferences.tutorial_offered = True
            if self._view.ask_yes_no(TUTORIAL_OFFER):
                self._tutorial.start()

    def _report_error(self, message: str) -> None:
        """Affiche une erreur (utilisé par ``guarded``).

        :param message: texte de l'erreur.
        """
        self._view.show_error(message)

    # ============================================================ abonnements
    def _connect_view(self) -> None:
        """Abonne le présentateur aux intentions de l'utilisateur."""
        view = self._view
        view.new_project_requested.connect(self._on_new_project)
        view.open_project_requested.connect(self._on_open_project)
        view.save_project_requested.connect(self._on_save_project)
        view.save_project_as_requested.connect(self._on_save_project_as)
        view.load_plugin_requested.connect(self._on_load_plugin)
        view.open_log_requested.connect(self._on_open_log)
        view.close_logs_requested.connect(self._on_close_logs)
        view.import_rules_requested.connect(self._on_import_rules)
        view.export_rules_requested.connect(self._on_export_rules)
        view.export_excel_requested.connect(self._on_export_excel)
        view.export_docx_requested.connect(self._on_export_docx)
        view.undo_requested.connect(self._on_undo)
        view.redo_requested.connect(self._on_redo)
        view.classify_requested.connect(self._on_classify)
        view.unclassify_requested.connect(self._on_unclassify)
        view.ai_help_requested.connect(self._on_ai_help)
        view.documentation_requested.connect(self._on_documentation)
        view.goto_source_requested.connect(self._on_goto_source)
        view.change_user_requested.connect(self._on_change_user)
        view.plugin_editor_requested.connect(self._on_plugin_editor)
        view.try_sample_requested.connect(self._on_try_sample)
        view.tutorial_requested.connect(self._on_tutorial)
        view.grouping_changed.connect(self._on_grouping_changed)
        view.category_selected.connect(self._on_category_selected)
        view.filter_changed.connect(self._on_filter_changed)
        view.selection_changed.connect(self._on_selection_changed)

    def _connect_model(self) -> None:
        """Abonne le présentateur aux événements du modèle."""
        events = self._session.events
        events.subscribe(EVENT_ENTRIES_CHANGED, self._refresh_entries)
        events.subscribe(EVENT_JUSTIFICATIONS_CHANGED, self._refresh_entries)
        events.subscribe(EVENT_HISTORY_CHANGED, self._refresh_history)
        events.subscribe(EVENT_PROJECT_CHANGED, self._refresh_project)

    # ============================================================== projet
    @guarded
    def _on_new_project(self) -> None:
        """Démarre un nouveau projet (après confirmation si nécessaire)."""
        if self._confirm_discard():
            self._session.new_project()
            self._view.show_status_message("Nouveau projet créé.")

    @guarded
    def _on_open_project(self) -> None:
        """Ouvre un fichier projet."""
        if not self._confirm_discard():
            return
        path = self._view.ask_open_file("Ouvrir un projet", PROJECT_FILTER)
        if path is not None:
            self._open_project_file(path)

    def _open_project_file(self, path: Path) -> None:
        """Ouvre un projet et rapporte les fichiers manquants.

        :param path: fichier projet.
        :raises LogWaverError: si le projet est invalide.
        """
        report = self._session.open_project(path)
        if self._session.plugin is not None:
            self._view.set_type_filter_options(self._session.plugin.type_names)
        if report.missing_files:
            self._view.show_warning(
                "Fichiers introuvables (déplacés ou supprimés) :\n- "
                + "\n- ".join(report.missing_files)
                + "\n\nLes justifications sont conservées : rouvrez les logs pour "
                "les appliquer."
            )
        auto = sum(item.auto_justified_count for item in report.load_reports)
        self._view.show_status_message(
            f"Projet ouvert : {len(self._session.justifications)} justification(s), "
            f"{auto} élément(s) justifié(s) automatiquement."
        )

    @guarded
    def _on_save_project(self) -> None:
        """Enregistre le projet (demande un fichier si nécessaire)."""
        self._save_project()

    @guarded
    def _on_save_project_as(self) -> None:
        """Enregistre le projet dans un nouveau fichier."""
        self._save_project(force_new_path=True)

    def _save_project(self, force_new_path: bool = False) -> bool:
        """Enregistre le projet.

        :param force_new_path: toujours demander un fichier.
        :return: ``True`` si l'enregistrement a eu lieu.
        :raises LogWaverError: si l'écriture échoue.
        """
        path = None if force_new_path else self._session.project_path
        if path is None:
            path = self._view.ask_save_file("Enregistrer le projet", PROJECT_FILTER,
                                            f"projet{PROJECT_FILE_EXTENSION}",
                                            PROJECT_FILE_EXTENSION)
            if path is None:
                return False
        saved = self._session.save_project(path)
        self._view.show_status_message(f"Projet enregistré : {saved}")
        return True

    def _confirm_discard(self) -> bool:
        """Propose d'enregistrer les modifications en cours.

        :return: ``True`` si l'action destructrice peut continuer.
        """
        if not self._session.is_dirty:
            return True
        answer = self._view.ask_unsaved_changes()
        if answer == ANSWER_CANCEL:
            return False
        if answer == ANSWER_SAVE:
            try:
                return self._save_project()
            except LogWaverError as error:
                self._view.show_error(str(error))
                return False
        return True

    def _can_close(self) -> bool:
        """Autorise la fermeture de la fenêtre.

        :return: ``True`` si la fenêtre peut se fermer.
        """
        return self._confirm_discard()

    # ============================================================ plugin/log
    @guarded
    def _on_load_plugin(self) -> None:
        """Charge un fichier plugin."""
        path = self._view.ask_open_file("Charger un plugin", PLUGIN_FILTER)
        if path is None:
            return
        plugin = self._session.load_plugin(path)
        self._view.set_type_filter_options(plugin.type_names)
        self._view.show_status_message(
            f"Plugin « {plugin.tool_name} » chargé ({', '.join(plugin.type_names)})."
        )

    @guarded
    def _on_open_log(self) -> None:
        """Ouvre un fichier de log (le plugin est détecté automatiquement)."""
        path = self._view.ask_open_file("Ouvrir un fichier de log", LOG_FILTER)
        if path is not None:
            self._open_log_file(path)

    def _open_log_file(self, path: Path) -> None:
        """Ouvre un log et informe des justifications réappliquées.

        Si aucun plugin n'est chargé, ou si le plugin courant ne reconnaît
        rien dans ce log, le plugin adapté est recherché automatiquement.

        :param path: fichier de log.
        :raises LogWaverError: si le log est illisible ou qu'aucun plugin ne convient.
        """
        if self._session.plugin is None:
            self._load_detected_plugin(path, required=True)
        report = self._session.open_log(path)
        if report.entry_count == 0 and self._load_detected_plugin(path, required=False):
            report = self._session.open_log(path)
        self._view.show_status_message(
            f"{path.name} : {report.entry_count} élément(s) extrait(s), "
            f"{report.auto_justified_count} justifié(s) automatiquement."
        )
        if report.entry_count == 0:
            self._view.show_warning(
                f"Aucun élément reconnu dans « {path.name} ». Vérifiez que le plugin "
                "correspond à ce log (Outils > Éditeur de plugin pour tester les regex)."
            )

    def _load_detected_plugin(self, log_path: Path, required: bool) -> bool:
        """Charge le plugin qui reconnaît le mieux un log.

        :param log_path: log à analyser.
        :param required: lève une erreur si aucun plugin ne convient.
        :return: ``True`` si un nouveau plugin a été chargé.
        :raises LogWaverError: si ``required`` et qu'aucun plugin ne convient.
        """
        candidate = self._detector.detect(log_path)
        if candidate is None:
            if required:
                raise LogWaverError(
                    f"Aucun plugin connu ne reconnaît « {log_path.name} ».\n\n"
                    "Choisissez un plugin (Fichier > Choisir le plugin) ou créez-en un "
                    "avec l'éditeur de plugin (menu Outils)."
                )
            return False
        current = self._session.plugin
        if current is not None and current.source_path == candidate.path:
            return False
        plugin = self._session.load_plugin(candidate.path)
        self._view.set_type_filter_options(plugin.type_names)
        self._view.show_status_message(
            f"Outil reconnu automatiquement : {plugin.tool_name} "
            f"({candidate.matched_lines} ligne(s) reconnue(s))."
        )
        return True

    @guarded
    def _on_try_sample(self) -> None:
        """Ouvre l'exemple fourni (plugin TINTIN et log du concepteur A)."""
        self._load_sample()

    def _load_sample(self) -> None:
        """Charge l'exemple dans une session vierge (après confirmation si besoin).

        :raises LogWaverError: si l'exemple est introuvable.
        """
        if not self._confirm_discard():
            return
        self._session.new_project()
        plugin = self._session.load_plugin(self._paths.sample_plugin)
        self._view.set_type_filter_options(plugin.type_names)
        self._open_log_file(self._paths.sample_log)

    @guarded
    def _on_close_logs(self) -> None:
        """Ferme tous les logs (les justifications sont conservées)."""
        self._session.close_logs()

    # ======================================================== justification
    @guarded
    def _on_classify(self) -> None:
        """Ouvre le dialogue de classement pour la sélection."""
        entries = self._session.entries_by_ids(self._selected_ids)
        if not entries or not self._ensure_user_name():
            return
        same_code_ids = self._same_code_ids(entries)
        first = self._session.justification_of(entries[0])
        request = self._view.ask_justification(
            self._status_choices(),
            selection_label=self._selection_label(entries),
            selection_count=len(entries),
            same_code_count=len(same_code_ids),
            initial_status_id=(first.status_id if first
                               else self._session.config.default_status_id),
            initial_text=first.text if first else "",
        )
        if request is None:
            return
        targets = same_code_ids if request.apply_to_same_code else [e.entry_id for e in entries]
        count = self._session.classify(targets, request.status_id, request.text, SOURCE_MANUAL)
        self._view.show_status_message(
            f"{len(targets)} élément(s) classé(s) en « "
            f"{self._session.config.status_label(request.status_id)} » "
            f"({count} justification(s)). Ctrl+Z pour annuler."
        )

    @guarded
    def _on_unclassify(self) -> None:
        """Retire la justification des éléments sélectionnés."""
        count = self._session.unclassify(self._selected_ids)
        if count:
            self._view.show_status_message(
                f"{count} justification(s) retirée(s) : les éléments repassent en "
                "« non justifiés ». Ctrl+Z pour annuler."
            )

    @guarded
    def _on_undo(self) -> None:
        """Annule la dernière action."""
        description = self._session.undo()
        if description:
            self._view.show_status_message(f"Annulé : {description}")

    @guarded
    def _on_redo(self) -> None:
        """Rétablit la dernière action annulée."""
        description = self._session.redo()
        if description:
            self._view.show_status_message(f"Rétabli : {description}")

    @guarded
    def _on_change_user(self) -> None:
        """Change le nom de l'utilisateur courant."""
        name = self._view.ask_user_name(self._session.user_name
                                        or self._preferences.last_user_name)
        if name:
            self._set_user(name)

    def _ensure_user_name(self) -> bool:
        """Demande le nom de l'utilisateur lors de la première justification.

        :return: ``True`` si un utilisateur est défini.
        """
        if self._session.user_name:
            return True
        name = self._view.ask_user_name(self._preferences.last_user_name)
        if not name:
            return False
        self._set_user(name)
        return True

    def _set_user(self, name: str) -> None:
        """Définit l'utilisateur dans la session et les préférences.

        :param name: nom saisi.
        :raises LogWaverError: si le nom est vide.
        """
        self._session.set_user_name(name)
        self._preferences.last_user_name = self._session.user_name

    def _selection_label(self, entries: Sequence[LogEntry]) -> str:
        """Décrit en clair ce que l'utilisateur s'apprête à justifier.

        :param entries: éléments sélectionnés.
        :return: description (élément, groupe ou nombre d'éléments).
        """
        if len(entries) == 1:
            entry = entries[0]
            return f"{entry.entry_type} {entry.code} : {entry.description or entry.raw_text}"
        groups = self._view.selected_group_values()
        if groups and self._grouping_key != GROUP_NONE:
            shown = ", ".join(f"« {value} »" for value in groups[:MAX_GROUPS_IN_LABEL])
            if len(groups) > MAX_GROUPS_IN_LABEL:
                shown += "…"
            return (f"{self._grouping_label()} {shown} : {len(entries)} élément(s) "
                    "seront justifiés ensemble")
        return f"{len(entries)} éléments sélectionnés seront justifiés ensemble"

    def _grouping_label(self) -> str:
        """Retourne le libellé du critère de regroupement actif.

        :return: libellé (vide si aucun regroupement).
        """
        for option in self._grouping_options:
            if option.key == self._grouping_key:
                return option.label
        return ""

    def _same_code_ids(self, entries: Sequence[LogEntry]) -> List[int]:
        """Retourne les éléments partageant le code d'au moins un élément donné.

        :param entries: éléments de référence.
        :return: identifiants (références comprises), sans doublon, ordonnés.
        """
        result: dict = {}
        for entry in entries:
            for other in self._session.entries_with_same_code(entry):
                result[other.entry_id] = True
        return list(result)

    # ====================================================== import / export
    @guarded
    def _on_import_rules(self) -> None:
        """Importe les justifications d'un autre concepteur."""
        path = self._view.ask_open_file("Importer des justifications", RULES_FILTER)
        if path is None:
            return
        overwrite = bool(self._session.justifications) and self._view.ask_yes_no(
            "Des justifications existent déjà. Remplacer celles qui portent sur les "
            "mêmes éléments par celles du fichier importé ?"
        )
        report = self._session.import_rules(path, overwrite)
        message = (
            f"{report.imported} justification(s) importée(s), {report.skipped} ignorée(s) "
            f"(déjà présentes).\n{report.matched_entries} élément(s) des logs ouverts "
            "sont désormais justifiés automatiquement."
        )
        if report.warning:
            message += f"\n\nAttention : {report.warning}"
        self._view.show_info(message)

    @guarded
    def _on_export_rules(self) -> None:
        """Exporte les justifications pour un autre concepteur."""
        tool = self._session.plugin.tool_name.lower() if self._session.plugin else "logwaver"
        path = self._view.ask_save_file("Exporter les justifications", RULES_FILTER,
                                        f"justifications_{tool}{RULES_FILE_EXTENSION}",
                                        RULES_FILE_EXTENSION)
        if path is not None:
            count = self._session.export_rules(path)
            self._view.show_status_message(f"{count} justification(s) exportée(s) : {path}")

    @guarded
    def _on_export_excel(self) -> None:
        """Exporte le travail au format Excel."""
        path = self._view.ask_save_file("Exporter vers Excel", EXCEL_FILTER,
                                        "rapport_logwaver.xlsx", ".xlsx")
        if path is not None:
            self._session.export_excel(path)
            self._view.show_status_message(f"Export Excel réalisé : {path}")

    @guarded
    def _on_export_docx(self) -> None:
        """Exporte un rapport Word."""
        path = self._view.ask_save_file("Exporter un rapport Word", WORD_FILTER,
                                        "rapport_logwaver.docx", ".docx")
        if path is not None:
            self._session.export_docx(path)
            self._view.show_status_message(f"Rapport Word réalisé : {path}")

    # ============================================================== élément
    @guarded
    def _on_ai_help(self) -> None:
        """Génère le prompt d'aide IA et ouvre le dialogue associé."""
        entry = self._single_selected_entry()
        if entry is None:
            return
        same_code = self._session.entries_with_same_code(entry)
        prompt = self._prompt_builder.build(entry, self._session.config.statuses, same_code)
        response = self._ai_provider.ask(prompt) or ""
        dialog = self._view.create_ai_help_dialog(AiHelpData(
            title=f"{entry.entry_type} {entry.code}",
            prompt=prompt,
            response=response,
            statuses=tuple(self._status_choices()),
            same_code_count=len(same_code),
        ))

        def apply(status_id: str, text: str, apply_to_same_code: bool) -> bool:
            """Applique la justification proposée par l'IA.

            :param status_id: catégorie choisie.
            :param text: justification.
            :param apply_to_same_code: étendre au même code.
            :return: ``True`` si la justification a été appliquée.
            """
            if not self._ensure_user_name():
                return False
            targets = ([e.entry_id for e in same_code] if apply_to_same_code
                       else [entry.entry_id])
            self._session.classify(targets, status_id, text, SOURCE_AI)
            self._view.show_status_message(
                f"{len(targets)} élément(s) justifié(s) avec la proposition de l'IA."
            )
            return True

        AiAssistantPresenter(dialog, self._ai_provider, self._ai_parser, apply).run(response)

    @guarded
    def _on_documentation(self) -> None:
        """Ouvre la documentation PDF à la page du code de l'élément."""
        entry = self._single_selected_entry()
        if entry is None:
            return
        location = self._session.documentation_location(entry)
        if not self._view.show_pdf(location.pdf_path, location.page):
            self._view.show_info(
                f"La visionneuse intégrée est indisponible : le PDF a été ouvert avec "
                f"l'application système. Rendez-vous à la page {location.page}."
            )

    @guarded
    def _on_goto_source(self) -> None:
        """Ouvre le fichier source à la ligne citée par l'élément."""
        entry = self._single_selected_entry()
        if entry is None:
            return
        path = self._session.resolve_source_file(entry)
        if path is None:
            raise LogWaverError(f"Fichier source introuvable : {entry.file_path}")
        line = entry.source_line or 1
        viewer = self._view.create_source_viewer(
            str(path), self._source_reader.read(path), line, self._editor.is_configured
        )
        viewer.external_editor_requested.connect(
            lambda: self._launch_external_editor(path, line)
        )
        viewer.exec_()

    @guarded
    def _launch_external_editor(self, path: Path, line: int) -> None:
        """Lance l'éditeur externe configuré.

        :param path: fichier à ouvrir.
        :param line: ligne à atteindre.
        """
        self._editor.open(path, line)

    @guarded
    def _on_plugin_editor(self) -> None:
        """Ouvre l'éditeur de plugin sur le plugin courant."""
        current = self._session.plugin.source_path if self._session.plugin else None
        PluginEditorPresenter(
            self._view.create_plugin_editor(), on_saved=self._on_plugin_saved
        ).run(current)

    @guarded
    def _on_plugin_saved(self, path: Path) -> None:
        """Propose de recharger le plugin enregistré depuis l'éditeur.

        :param path: plugin enregistré.
        """
        if self._view.ask_yes_no(
            "Plugin enregistré. Le charger maintenant (les logs ouverts seront "
            "ré-analysés, les justifications sont conservées) ?"
        ):
            plugin = self._session.load_plugin(path)
            self._view.set_type_filter_options(plugin.type_names)

    def _single_selected_entry(self) -> Optional[LogEntry]:
        """Retourne l'élément sélectionné s'il est unique.

        :return: élément, ou ``None`` si la sélection n'est pas unique.
        """
        if len(self._selected_ids) != 1:
            return None
        return self._session.entry_by_id(self._selected_ids[0])

    # ======================================================== didacticiel
    def _create_tutorial(self) -> Optional[TutorialPresenter]:
        """Charge le didacticiel (absent ou invalide : fonction désactivée).

        :return: présentateur du didacticiel, ou ``None``.
        """
        try:
            tutorial = TutorialLoader().load(self._paths.tutorial_file)
        except LogWaverError as error:
            LOGGER.warning("Didacticiel indisponible : %s", error)
            return None
        return TutorialPresenter(self._view, tutorial, self._tutorial_actions())

    def _tutorial_actions(self) -> Dict[str, Callable[[], None]]:
        """Associe les noms d'actions du didacticiel à leur réalisation.

        :return: nom d'action → fonction sans argument.
        """
        return {
            "load_sample": self._load_sample,
            "show_unclassified": lambda: self._select_category(CATEGORY_UNCLASSIFIED),
            "show_all": lambda: self._select_category(CATEGORY_ALL),
            "group_by_code": lambda: self._view.select_grouping("field:code"),
            "group_by_file": lambda: self._view.select_grouping("field:file"),
            "ungroup": lambda: self._view.select_grouping(GROUP_NONE),
            "select_first": self._view.select_first_row,
            "justify": self._on_classify,
            "undo": self._on_undo,
        }

    @guarded
    def _on_tutorial(self) -> None:
        """Lance le didacticiel."""
        if self._tutorial is None:
            raise LogWaverError("Le didacticiel est introuvable "
                                f"({self._paths.tutorial_file}).")
        self._tutorial.start()

    def _select_category(self, category: str) -> None:
        """Affiche une catégorie comme si l'utilisateur l'avait choisie.

        :param category: clé de catégorie.
        """
        self._on_category_selected(category)
        self._refresh_categories()

    # ======================================================= vue : filtres
    @guarded
    def _on_grouping_changed(self, key: str) -> None:
        """Change le critère de regroupement.

        :param key: critère choisi.
        """
        self._grouping_key = key or GROUP_NONE
        self._refresh_table()
        if self._grouping_key != GROUP_NONE:
            self._view.show_status_message(
                f"Regroupement par {self._grouping_label().lower()} : sélectionnez un "
                "groupe puis « Justifier » pour traiter tous ses éléments en une fois.")

    @guarded
    def _on_category_selected(self, category: str) -> None:
        """Change la catégorie affichée.

        :param category: clé de catégorie.
        """
        self._criteria = FilterCriteria(category, self._criteria.entry_type,
                                        self._criteria.code_text, self._criteria.file_text,
                                        self._criteria.free_text)
        self._refresh_table()

    @guarded
    def _on_filter_changed(self, free_text: str, entry_type: str, code_text: str,
                           file_text: str) -> None:
        """Applique les filtres saisis.

        :param free_text: texte libre.
        :param entry_type: type exigé.
        :param code_text: fragment de code.
        :param file_text: fragment de fichier.
        """
        self._criteria = FilterCriteria(self._criteria.category, entry_type, code_text,
                                        file_text, free_text)
        self._refresh_table()

    @guarded
    def _on_selection_changed(self, entry_ids: list) -> None:
        """Met à jour détails et actions selon la sélection.

        :param entry_ids: éléments sélectionnés.
        """
        self._selected_ids = [int(i) for i in entry_ids]
        self._refresh_selection()

    # ============================================================ rafraîchir
    def _refresh_everything(self) -> None:
        """Rafraîchit toute la fenêtre."""
        self._refresh_entries()
        self._refresh_history()
        self._refresh_project()

    def _refresh_entries(self) -> None:
        """Rafraîchit catégories, table et détails après un changement."""
        self._refresh_categories()
        self._refresh_table()

    def _refresh_categories(self) -> None:
        """Recalcule les effectifs de chaque catégorie."""
        summary = self._session.summary()
        items = [
            CategoryItem(CATEGORY_UNCLASSIFIED, CATEGORY_UNCLASSIFIED_LABEL,
                         summary.count_for_category(CATEGORY_UNCLASSIFIED),
                         tooltip="Éléments sans justification"),
        ]
        items += [
            CategoryItem(status.status_id, status.label,
                         summary.count_for_category(status.status_id),
                         status.color, status.description)
            for status in self._session.config.statuses
        ]
        items.append(CategoryItem(CATEGORY_ALL, CATEGORY_ALL_LABEL, summary.total,
                                  tooltip="Tous les éléments, classés ou non"))
        self._view.set_categories(items, self._criteria.category)
        self._view.set_status_info(StatusBarInfo(
            user_name=self._session.user_name,
            tool_name=self._session.plugin.tool_name if self._session.plugin else "",
            total=summary.total,
            unclassified=summary.count_for_category(CATEGORY_UNCLASSIFIED),
            ratio_text=f"{summary.justified_ratio() * 100:.0f} %",
        ))

    def _refresh_table(self) -> None:
        """Affiche les éléments correspondant aux filtres, groupés ou non."""
        entries = self._session.filter_entries(self._criteria)
        total = len(self._session.entries)
        self._view.show_welcome(not self._session.entries)
        if self._grouping_key == GROUP_NONE:
            self._view.set_flat_entries([self._to_row(e) for e in entries], total)
        else:
            self._view.set_grouped_entries([
                EntryGroupView(
                    value=group.value,
                    rows=tuple(self._to_row(e) for e in group.entries),
                    unclassified=sum(1 for e in group.entries
                                     if self._session.justification_of(e) is None),
                )
                for group in self._grouper.group(entries, self._grouping_key)
            ], total)
        self._refresh_guide(bool(entries))

    def _refresh_guide(self, has_visible_entries: bool) -> None:
        """Met à jour le conseil « que faire maintenant ? ».

        :param has_visible_entries: des éléments sont affichés.
        """
        pending = self._session.summary().count_for_category(CATEGORY_UNCLASSIFIED)
        category = self._criteria.category
        if not has_visible_entries and category == CATEGORY_UNCLASSIFIED and not pending:
            text = GUIDE_ALL_DONE
        elif not has_visible_entries:
            text = GUIDE_EMPTY_FILTER
        elif category in (CATEGORY_UNCLASSIFIED, CATEGORY_ALL):
            text = GUIDE_TO_JUSTIFY.format(pending=pending) if pending else GUIDE_ALL_DONE
        else:
            text = GUIDE_CATEGORY_VIEW.format(
                category=self._session.config.status_label(category))
        self._view.set_guide(text)

    def _refresh_grouping_options(self) -> None:
        """Propose les critères de regroupement adaptés au plugin chargé."""
        plugin = self._session.plugin
        fields: List[str] = []
        if plugin is not None:
            for element in plugin.element_types:
                fields.extend(element.field_names)
        options = EntryGrouper.available_options(fields)
        if [o.key for o in options] == [o.key for o in self._grouping_options]:
            return
        self._grouping_options = options
        if self._grouping_key not in {o.key for o in options}:
            self._grouping_key = GROUP_NONE
        self._view.set_grouping_options(
            [GroupingChoice(o.key, o.label) for o in options], self._grouping_key)

    def _refresh_selection(self) -> None:
        """Met à jour le panneau de détails et l'état des actions."""
        entries = self._session.entries_by_ids(self._selected_ids)
        self._view.show_details(self._to_details(entries))
        single = entries[0] if len(entries) == 1 else None
        self._view.set_actions_state(ActionsState(
            has_plugin=self._session.plugin is not None,
            has_entries=bool(self._session.entries),
            has_selection=bool(entries),
            single_selection=single is not None,
            selection_classified=any(self._session.justification_of(e) for e in entries),
            can_open_documentation=self._session.has_documentation,
            can_open_source=single is not None
            and self._session.resolve_source_file(single) is not None,
            has_justifications=bool(self._session.justifications),
        ))

    def _refresh_history(self) -> None:
        """Met à jour les actions Annuler / Rétablir."""
        session = self._session
        self._view.set_history_state(session.can_undo, session.undo_text,
                                     session.can_redo, session.redo_text)

    def _refresh_project(self) -> None:
        """Met à jour le titre, la barre d'état et les actions."""
        path = self._session.project_path
        self._view.set_title(path.name if path else UNTITLED_PROJECT, self._session.is_dirty)
        plugin = self._session.plugin
        self._view.set_welcome_plugin(plugin.tool_name if plugin else "")
        self._refresh_grouping_options()
        self._refresh_categories()
        self._refresh_selection()

    # ============================================================ conversion
    def _status_choices(self) -> List[StatusChoice]:
        """Retourne les catégories configurées sous forme de DTO.

        :return: catégories proposées à l'utilisateur.
        """
        return [StatusChoice(s.status_id, s.label, s.description)
                for s in self._session.config.statuses]

    def _to_row(self, entry: LogEntry) -> EntryRow:
        """Convertit un élément en ligne de table.

        :param entry: élément.
        :return: ligne affichable.
        """
        justification = self._session.justification_of(entry)
        status = (self._session.config.find_status(justification.status_id)
                  if justification else None)
        return EntryRow(
            entry_id=entry.entry_id,
            entry_type=entry.entry_type,
            code=entry.code,
            file_name=entry.file_path,
            line="" if entry.source_line is None else str(entry.source_line),
            description=entry.description or entry.raw_text,
            status_label=status.label if status else (
                justification.status_id if justification else ""),
            status_color=status.color if status else "",
            author=justification.author if justification else "",
            log_name=Path(entry.log_path).name,
        )

    def _to_details(self, entries: Sequence[LogEntry]) -> Optional[EntryDetails]:
        """Construit le contenu du panneau de détails.

        :param entries: éléments sélectionnés.
        :return: détails, ou ``None`` si la sélection est vide.
        """
        if not entries:
            return None
        if len(entries) > 1:
            codes = sorted({e.code for e in entries if e.code})
            shown = ", ".join(codes[:MAX_CODES_IN_SUMMARY])
            if len(codes) > MAX_CODES_IN_SUMMARY:
                shown += "…"
            classified = sum(1 for e in entries if self._session.justification_of(e))
            return EntryDetails(
                title=self._selection_label(entries),
                fields=(("Codes", shown), ("Déjà classés", str(classified))),
                raw_text="\n".join(e.raw_text for e in entries[:MAX_CODES_IN_SUMMARY]),
            )
        entry = entries[0]
        justification = self._session.justification_of(entry)
        status = (self._session.config.find_status(justification.status_id)
                  if justification else None)
        fields = tuple((FIELD_LABELS.get(name, name), value)
                       for name, value in entry.fields.items())
        fields += (("Log", f"{Path(entry.log_path).name} (ligne {entry.log_line_number})"),)
        return EntryDetails(
            title=f"{entry.entry_type} {entry.code}".strip(),
            fields=fields,
            raw_text=entry.raw_text,
            status_label=(status.label if status else justification.status_id)
            if justification else "",
            status_color=status.color if status else "",
            justification_text=justification.text if justification else "",
            author=justification.author if justification else "",
            timestamp=justification.timestamp if justification else "",
            source=justification.source if justification else "",
        )
