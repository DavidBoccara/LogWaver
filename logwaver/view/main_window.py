"""Fenêtre principale de LogWaver (vue passive du patron MVP).

La fenêtre n'exécute aucune logique métier : elle affiche ce que lui
transmet le présentateur et émet des signaux pour chaque intention de
l'utilisateur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from PyQt5.QtCore import QPoint, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from logwaver import __version__
from logwaver.constants import APP_NAME
from logwaver.view.dialogs.ai_help_dialog import AiHelpDialog
from logwaver.view.dialogs.justification_dialog import JustificationDialog
from logwaver.view.dialogs.matching_rules_dialog import MatchingRulesDialog
from logwaver.view.dialogs.pdf_viewer_dialog import PdfViewerDialog, is_web_engine_available
from logwaver.view.dialogs.plugin_editor_dialog import PluginEditorDialog
from logwaver.view.dialogs.source_viewer_dialog import SourceViewerDialog
from logwaver.view.widgets.category_panel import CategoryPanel
from logwaver.view.widgets.details_panel import DetailsPanel
from logwaver.view.widgets.entry_tree import EntryTree
from logwaver.view.widgets.filter_bar import FilterBar
from logwaver.view.widgets.tutorial_panel import TutorialPanel
from logwaver.view.widgets.welcome_page import WelcomePage
from logwaver.view_models import (
    ANSWER_CANCEL,
    ANSWER_DISCARD,
    ANSWER_SAVE,
    ActionsState,
    AiHelpData,
    CategoryItem,
    EntryDetails,
    EntryGroupView,
    EntryRow,
    GroupingChoice,
    JustificationRequest,
    MatchingKeyView,
    MatchingPresetView,
    StatusBarInfo,
    StatusChoice,
)

STATUS_MESSAGE_TIMEOUT_MS: int = 6000
TUTORIAL_TARGET_PROPERTY: str = "tutorialTarget"
TOOLBAR_BUTTON_PREFIX: str = "ToolbarButton_"
PAGE_WELCOME: int = 0
PAGE_WORK: int = 1

# Barre d'outils volontairement courte : les actions essentielles uniquement.
TOOLBAR_KEYS: tuple = ("open_log", None, "classify", "unclassify", "undo", None,
                       "save_project", "export_excel", None, "tutorial")
TOOLBAR_ICONS: Dict[str, QStyle.StandardPixmap] = {
    "open_log": QStyle.SP_DialogOpenButton,
    "classify": QStyle.SP_DialogApplyButton,
    "unclassify": QStyle.SP_DialogResetButton,
    "undo": QStyle.SP_ArrowBack,
    "save_project": QStyle.SP_DialogSaveButton,
    "export_excel": QStyle.SP_FileDialogDetailedView,
    "tutorial": QStyle.SP_DialogHelpButton,
}


class MainWindow(QMainWindow):
    """Fenêtre principale : accueil, ou catégories | arbre des éléments | détails."""

    new_project_requested = pyqtSignal()
    open_project_requested = pyqtSignal()
    save_project_requested = pyqtSignal()
    save_project_as_requested = pyqtSignal()
    load_plugin_requested = pyqtSignal()
    open_log_requested = pyqtSignal()
    close_logs_requested = pyqtSignal()
    import_rules_requested = pyqtSignal()
    export_rules_requested = pyqtSignal()
    export_excel_requested = pyqtSignal()
    export_docx_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    classify_requested = pyqtSignal()
    unclassify_requested = pyqtSignal()
    ai_help_requested = pyqtSignal()
    documentation_requested = pyqtSignal()
    goto_source_requested = pyqtSignal()
    change_user_requested = pyqtSignal()
    plugin_editor_requested = pyqtSignal()
    new_plugin_requested = pyqtSignal()
    matching_rules_requested = pyqtSignal()
    try_sample_requested = pyqtSignal()
    tutorial_requested = pyqtSignal()
    tutorial_next_requested = pyqtSignal()
    tutorial_previous_requested = pyqtSignal()
    tutorial_action_requested = pyqtSignal()
    tutorial_quit_requested = pyqtSignal()
    category_selected = pyqtSignal(str)
    filter_changed = pyqtSignal(str, str, str, str)
    grouping_changed = pyqtSignal(str)
    selection_changed = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit la fenêtre.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.resize(1500, 880)
        self._close_guard: Callable[[], bool] = lambda: True
        self._pdf_viewer: Optional[PdfViewerDialog] = None
        self._highlighted: Optional[QWidget] = None
        self._category_panel = CategoryPanel()
        self._filter_bar = FilterBar()
        self._details_panel = DetailsPanel()
        self._tree = EntryTree()
        self._welcome_page = WelcomePage()
        self._tutorial_panel = TutorialPanel(self)
        self._pages = QStackedWidget()
        self._guide_label = QLabel()
        self._guide_label.setObjectName("GuideBanner")
        self._guide_label.setWordWrap(True)
        self._count_label = QLabel()
        self._count_label.setObjectName("CountLabel")
        self._status_info_label = QLabel()
        self._actions: Dict[str, QAction] = {}
        self._create_actions()
        self._create_menus_and_toolbar()
        self._build_layout()
        self._connect_signals()
        self.show_welcome(True)

    # ======================================================= API présentateur
    def set_close_guard(self, guard: Callable[[], bool]) -> None:
        """Définit la fonction autorisant (ou non) la fermeture.

        :param guard: retourne ``True`` si la fenêtre peut se fermer.
        """
        self._close_guard = guard

    def show_welcome(self, visible: bool) -> None:
        """Affiche la page d'accueil ou l'espace de travail.

        :param visible: ``True`` pour la page d'accueil.
        """
        self._pages.setCurrentIndex(PAGE_WELCOME if visible else PAGE_WORK)

    def set_welcome_plugin(self, tool_name: str) -> None:
        """Indique sur l'accueil le plugin chargé.

        :param tool_name: outil du plugin (vide = détection automatique).
        """
        self._welcome_page.set_plugin_info(tool_name)

    def set_guide(self, text: str) -> None:
        """Affiche le conseil « que faire maintenant ? ».

        :param text: conseil (HTML simple).
        """
        self._guide_label.setText(text)

    def set_flat_entries(self, rows: Sequence[EntryRow], total: int) -> None:
        """Affiche les éléments à plat.

        :param rows: lignes à afficher.
        :param total: nombre total d'éléments (avant filtrage).
        """
        self._tree.set_flat_rows(rows)
        self._count_label.setText(f"{len(rows)} élément(s) affiché(s) sur {total}")

    def set_grouped_entries(self, groups: Sequence[EntryGroupView], total: int) -> None:
        """Affiche les éléments regroupés.

        :param groups: groupes à afficher.
        :param total: nombre total d'éléments (avant filtrage).
        """
        self._tree.set_groups(groups)
        shown = sum(len(group.rows) for group in groups)
        self._count_label.setText(
            f"{len(groups)} groupe(s), {shown} élément(s) affiché(s) sur {total} — "
            "sélectionnez un groupe pour le traiter en entier")

    def set_grouping_options(self, choices: Sequence[GroupingChoice], current: str) -> None:
        """Met à jour les critères de regroupement.

        :param choices: critères disponibles.
        :param current: critère actif.
        """
        self._filter_bar.set_grouping_options(choices, current)

    def select_grouping(self, key: str) -> None:
        """Active un critère de regroupement (utilisé par le didacticiel).

        :param key: critère à activer.
        """
        self._filter_bar.select_grouping(key)

    def select_first_row(self) -> None:
        """Sélectionne la première ligne de l'arbre."""
        self._tree.setFocus()
        self._tree.select_first_row()

    def set_categories(self, items: Sequence[CategoryItem], selected_key: str) -> None:
        """Met à jour le panneau des catégories.

        :param items: catégories et effectifs.
        :param selected_key: catégorie sélectionnée.
        """
        self._category_panel.set_categories(items, selected_key)

    def set_type_filter_options(self, type_names: Sequence[str]) -> None:
        """Met à jour la liste des types du filtre.

        :param type_names: types disponibles.
        """
        self._filter_bar.set_type_options(type_names)

    def show_details(self, details: Optional[EntryDetails]) -> None:
        """Affiche le détail de la sélection.

        :param details: contenu, ``None`` pour vider.
        """
        self._details_panel.show_details(details)

    def set_actions_state(self, state: ActionsState) -> None:
        """Active ou désactive actions et boutons.

        :param state: disponibilité des actions.
        """
        self._details_panel.set_actions_state(state)
        enable = {
            "close_logs": state.has_entries,
            "classify": state.has_selection,
            "unclassify": state.selection_classified,
            "ai_help": state.single_selection,
            "documentation": state.single_selection and state.can_open_documentation,
            "goto_source": state.single_selection and state.can_open_source,
            "export_rules": state.has_justifications,
            "export_excel": state.has_entries or state.has_justifications,
            "export_docx": state.has_entries or state.has_justifications,
        }
        for key, enabled in enable.items():
            self._actions[key].setEnabled(enabled)

    def set_history_state(self, can_undo: bool, undo_text: str,
                          can_redo: bool, redo_text: str) -> None:
        """Met à jour les actions Annuler/Rétablir.

        :param can_undo: annulation possible.
        :param undo_text: libellé de l'action annulable.
        :param can_redo: rétablissement possible.
        :param redo_text: libellé de l'action rétablissable.
        """
        undo, redo = self._actions["undo"], self._actions["redo"]
        undo.setEnabled(can_undo)
        undo.setToolTip(f"Annuler : {undo_text} (Ctrl+Z)" if can_undo else "Annuler (Ctrl+Z)")
        redo.setEnabled(can_redo)
        redo.setToolTip(f"Rétablir : {redo_text} (Ctrl+Y)" if can_redo
                        else "Rétablir (Ctrl+Y)")

    def set_title(self, project_name: str, dirty: bool) -> None:
        """Met à jour le titre de la fenêtre.

        :param project_name: nom du projet.
        :param dirty: modifications non enregistrées.
        """
        marker = " *" if dirty else ""
        self.setWindowTitle(f"{project_name}{marker} - {APP_NAME}")

    def set_status_info(self, info: StatusBarInfo) -> None:
        """Met à jour la barre d'état permanente.

        :param info: informations à afficher.
        """
        self._status_info_label.setText(
            f"Outil : {info.tool_name or '—'}   |   Utilisateur : "
            f"{info.user_name or '—'}   |   Reste à justifier : {info.unclassified}"
            f"/{info.total}   |   Avancement : {info.ratio_text}"
        )

    def show_status_message(self, message: str) -> None:
        """Affiche un message temporaire dans la barre d'état.

        :param message: texte à afficher.
        """
        self.statusBar().showMessage(message, STATUS_MESSAGE_TIMEOUT_MS)

    def selected_entry_ids(self) -> List[int]:
        """Retourne les éléments sélectionnés (groupes développés).

        :return: identifiants, dans l'ordre d'affichage.
        """
        return self._tree.selected_entry_ids()

    def selected_group_values(self) -> List[str]:
        """Retourne les groupes sélectionnés.

        :return: valeurs des groupes sélectionnés.
        """
        return self._tree.selected_group_values()

    # ------------------------------------------------------------ didacticiel
    def show_tutorial_step(self, index: int, count: int, title: str, text: str,
                           action_label: str, is_first: bool, is_last: bool,
                           target: str) -> None:
        """Affiche une étape du didacticiel et met en évidence sa cible.

        :param index: index (0-based) de l'étape.
        :param count: nombre d'étapes.
        :param title: titre.
        :param text: explication (HTML simple).
        :param action_label: libellé du bouton « Montre-moi » (vide = aucun).
        :param is_first: première étape.
        :param is_last: dernière étape.
        :param target: objectName du widget à mettre en évidence (vide = aucun).
        """
        self._tutorial_panel.show_step(index, count, title, text, action_label,
                                       is_first, is_last)
        self.highlight_widget(target)

    def hide_tutorial(self) -> None:
        """Ferme le didacticiel et retire la mise en évidence."""
        self._tutorial_panel.hide()
        self.highlight_widget("")

    def highlight_widget(self, object_name: str) -> None:
        """Met en évidence un widget (bordure définie dans le QSS).

        :param object_name: objectName du widget (vide = retirer la mise en évidence).
        """
        if self._highlighted is not None:
            self._set_highlight(self._highlighted, False)
            self._highlighted = None
        if not object_name:
            return
        widget = self.findChild(QWidget, object_name)
        if widget is not None:
            self._set_highlight(widget, True)
            self._highlighted = widget

    # -------------------------------------------------------------- dialogues
    def ask_open_file(self, title: str, file_filter: str) -> Optional[Path]:
        """Demande un fichier à ouvrir.

        :param title: titre du dialogue.
        :param file_filter: filtre de fichiers Qt.
        :return: chemin choisi, ou ``None``.
        """
        path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        return Path(path) if path else None

    def ask_save_file(self, title: str, file_filter: str, default_name: str,
                      extension: str) -> Optional[Path]:
        """Demande un fichier de destination (extension ajoutée si absente).

        :param title: titre du dialogue.
        :param file_filter: filtre de fichiers Qt.
        :param default_name: nom proposé.
        :param extension: extension attendue (ex. ``.xlsx``).
        :return: chemin choisi, ou ``None``.
        """
        path, _ = QFileDialog.getSaveFileName(self, title, default_name, file_filter)
        if not path:
            return None
        result = Path(path)
        return result if result.suffix.lower() == extension else result.with_name(
            result.name + extension)

    def ask_user_name(self, current: str) -> Optional[str]:
        """Demande le nom de l'utilisateur.

        :param current: valeur proposée.
        :return: nom saisi, ou ``None`` si annulé.
        """
        name, accepted = QInputDialog.getText(
            self, "Qui justifie ?",
            "Votre nom sera inscrit sur chaque justification.\n"
            "Il n'est demandé qu'une seule fois.",
            QLineEdit.Normal, current,
        )
        return name.strip() if accepted and name.strip() else None

    def ask_justification(self, statuses: Sequence[StatusChoice], selection_label: str,
                          selection_count: int, same_code_count: int,
                          initial_status_id: str,
                          initial_text: str) -> Optional[JustificationRequest]:
        """Ouvre le dialogue de justification.

        :param statuses: catégories proposées.
        :param selection_label: description de ce qui est justifié.
        :param selection_count: nombre d'éléments sélectionnés.
        :param same_code_count: nombre d'éléments du même code.
        :param initial_status_id: catégorie proposée.
        :param initial_text: justification préremplie.
        :return: saisie validée, ou ``None`` si annulée.
        """
        dialog = JustificationDialog(statuses, selection_label, selection_count,
                                     same_code_count, initial_status_id, initial_text, self)
        return dialog.request() if dialog.exec_() == JustificationDialog.Accepted else None

    def ask_unsaved_changes(self) -> str:
        """Demande quoi faire des modifications non enregistrées.

        :return: ``ANSWER_SAVE``, ``ANSWER_DISCARD`` ou ``ANSWER_CANCEL``.
        """
        answer = QMessageBox.question(
            self, APP_NAME,
            "Le projet contient des modifications non enregistrées. "
            "Voulez-vous les enregistrer ?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if answer == QMessageBox.Save:
            return ANSWER_SAVE
        return ANSWER_DISCARD if answer == QMessageBox.Discard else ANSWER_CANCEL

    def ask_yes_no(self, question: str) -> bool:
        """Pose une question fermée.

        :param question: texte de la question.
        :return: ``True`` si l'utilisateur répond oui.
        """
        return QMessageBox.question(self, APP_NAME, question,
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes

    def show_error(self, message: str) -> None:
        """Affiche une erreur.

        :param message: texte de l'erreur.
        """
        QMessageBox.critical(self, APP_NAME, message)

    def show_warning(self, message: str) -> None:
        """Affiche un avertissement.

        :param message: texte de l'avertissement.
        """
        QMessageBox.warning(self, APP_NAME, message)

    def show_info(self, message: str) -> None:
        """Affiche une information.

        :param message: texte de l'information.
        """
        QMessageBox.information(self, APP_NAME, message)

    def create_ai_help_dialog(self, data: AiHelpData) -> AiHelpDialog:
        """Crée le dialogue d'aide IA (le présentateur le pilote).

        :param data: contenu initial.
        :return: dialogue non affiché.
        """
        return AiHelpDialog(data, self)

    def create_matching_rules_dialog(self, keys: Sequence[MatchingKeyView],
                                     presets: Sequence[MatchingPresetView],
                                     example_title: str) -> MatchingRulesDialog:
        """Crée le dialogue des règles de correspondance (piloté par le présentateur).

        :param keys: critères proposés.
        :param presets: préréglages.
        :param example_title: élément servant d'exemple.
        :return: dialogue non affiché.
        """
        return MatchingRulesDialog(keys, presets, example_title, self)

    def ask_item(self, title: str, label: str, items: Sequence[str]) -> Optional[int]:
        """Fait choisir un élément dans une liste.

        :param title: titre du dialogue.
        :param label: question posée.
        :param items: choix proposés.
        :return: index choisi, ou ``None`` si annulé.
        """
        choice, accepted = QInputDialog.getItem(self, title, label, list(items), 0, False)
        return list(items).index(choice) if accepted and choice in items else None

    def create_plugin_editor(self) -> PluginEditorDialog:
        """Crée l'éditeur de plugin (le présentateur le pilote).

        :return: dialogue non affiché.
        """
        return PluginEditorDialog(self)

    def create_source_viewer(self, path_text: str, content: str, line: int,
                             external_editor_available: bool) -> SourceViewerDialog:
        """Crée la visionneuse de fichier source.

        :param path_text: chemin affiché.
        :param content: contenu du fichier.
        :param line: ligne à atteindre.
        :param external_editor_available: afficher le bouton d'éditeur externe.
        :return: dialogue non affiché.
        """
        return SourceViewerDialog(path_text, content, line, external_editor_available, self)

    def show_pdf(self, pdf_path: Path, page: int) -> bool:
        """Affiche un PDF à une page (visionneuse intégrée ou application système).

        :param pdf_path: fichier PDF.
        :param page: page à afficher.
        :return: ``True`` si la page exacte a pu être ciblée.
        """
        if is_web_engine_available():
            if self._pdf_viewer is None:
                self._pdf_viewer = PdfViewerDialog(self)
            self._pdf_viewer.show_page(pdf_path, page)
            return True
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf_path)))
        return False

    # ================================================================ interne
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Consulte le présentateur avant de fermer (API Qt).

        :param event: événement de fermeture.
        """
        if self._close_guard():
            event.accept()
        else:
            event.ignore()

    def _create_actions(self) -> None:
        """Crée les actions de menu et leurs raccourcis."""
        definitions = (
            ("new_project", "Nouveau projet", QKeySequence.New, self.new_project_requested),
            ("open_project", "Reprendre un projet…", QKeySequence.Open,
             self.open_project_requested),
            ("save_project", "Enregistrer", QKeySequence.Save, self.save_project_requested),
            ("save_project_as", "Enregistrer sous…", QKeySequence.SaveAs,
             self.save_project_as_requested),
            ("load_plugin", "Choisir le plugin…", "Ctrl+P", self.load_plugin_requested),
            ("open_log", "Ouvrir un log…", "Ctrl+L", self.open_log_requested),
            ("close_logs", "Fermer les logs", None, self.close_logs_requested),
            ("try_sample", "Ouvrir l'exemple fourni", None, self.try_sample_requested),
            ("import_rules", "Récupérer les justifications d'un collègue…", "Ctrl+Shift+I",
             self.import_rules_requested),
            ("export_rules", "Partager mes justifications…", "Ctrl+Shift+E",
             self.export_rules_requested),
            ("export_excel", "Exporter vers Excel…", "Ctrl+E", self.export_excel_requested),
            ("export_docx", "Exporter un rapport Word…", None, self.export_docx_requested),
            ("quit", "Quitter", QKeySequence.Quit, None),
            ("undo", "Annuler", QKeySequence.Undo, self.undo_requested),
            ("redo", "Rétablir", QKeySequence.Redo, self.redo_requested),
            ("classify", "Justifier…", "Ctrl+J", self.classify_requested),
            ("unclassify", "Retirer la justification", QKeySequence.Delete,
             self.unclassify_requested),
            ("ai_help", "Demander à l'IA…", "Ctrl+I", self.ai_help_requested),
            ("documentation", "Voir la documentation", "F1", self.documentation_requested),
            ("goto_source", "Ouvrir le fichier source", "Ctrl+G", self.goto_source_requested),
            ("change_user", "Changer d'utilisateur…", None, self.change_user_requested),
            ("search", "Rechercher", QKeySequence.Find, None),
            ("plugin_editor", "Modifier le plugin actuel…", "Ctrl+R",
             self.plugin_editor_requested),
            ("new_plugin", "Créer un nouveau plugin…", "Ctrl+Shift+N",
             self.new_plugin_requested),
            ("matching_rules", "Règles de correspondance…", "Ctrl+M",
             self.matching_rules_requested),
            ("tutorial", "Didacticiel", "Shift+F1", self.tutorial_requested),
            ("about", "À propos", None, None),
        )
        for key, text, shortcut, signal in definitions:
            action = QAction(text, self)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            if signal is not None:
                action.triggered.connect(signal)
            if key in TOOLBAR_ICONS:
                action.setIcon(self.style().standardIcon(TOOLBAR_ICONS[key]))
            self._actions[key] = action
        self._actions["quit"].triggered.connect(self.close)
        self._actions["search"].triggered.connect(self._filter_bar.focus_search)
        self._actions["about"].triggered.connect(self._show_about)

    def _create_menus_and_toolbar(self) -> None:
        """Construit la barre de menus et une barre d'outils réduite à l'essentiel."""
        menus = (
            ("&Fichier", ("open_log", "try_sample", None, "open_project", "save_project",
                          "save_project_as", "new_project", None, "import_rules",
                          "export_rules", None, "export_excel", "export_docx", None,
                          "load_plugin", "close_logs", None, "quit")),
            ("&Édition", ("undo", "redo", None, "classify", "unclassify", None, "search",
                          None, "matching_rules", "change_user")),
            ("É&lément", ("ai_help", "documentation", "goto_source")),
            ("&Outils", ("new_plugin", "plugin_editor")),
            ("&Aide", ("tutorial", None, "about")),
        )
        for title, keys in menus:
            menu = self.menuBar().addMenu(title)
            for key in keys:
                if key is None:
                    menu.addSeparator()
                else:
                    menu.addAction(self._actions[key])
        toolbar = QToolBar("Barre d'outils")
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        for key in TOOLBAR_KEYS:
            if key is None:
                toolbar.addSeparator()
                continue
            toolbar.addAction(self._actions[key])
            button = toolbar.widgetForAction(self._actions[key])
            if button is not None:
                button.setObjectName(f"{TOOLBAR_BUTTON_PREFIX}{key}")
        self.addToolBar(toolbar)

    def _build_layout(self) -> None:
        """Dispose l'accueil, l'espace de travail et le panneau du didacticiel."""
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self._guide_label)
        center_layout.addWidget(self._filter_bar)
        center_layout.addWidget(self._tree, stretch=1)
        center_layout.addWidget(self._count_label)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.addWidget(self._category_panel)
        splitter.addWidget(center)
        splitter.addWidget(self._details_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([250, 900, 350])
        work_page = QWidget()
        work_layout = QVBoxLayout(work_page)
        work_layout.addWidget(splitter)
        self._pages.addWidget(self._welcome_page)
        self._pages.addWidget(work_page)
        self.setCentralWidget(self._pages)
        self.addDockWidget(Qt.RightDockWidgetArea, self._tutorial_panel)
        self.statusBar().addPermanentWidget(self._status_info_label)

    def _connect_signals(self) -> None:
        """Relie les widgets enfants aux signaux publics."""
        self._category_panel.category_selected.connect(self.category_selected)
        self._filter_bar.filter_changed.connect(self.filter_changed)
        self._filter_bar.grouping_changed.connect(self.grouping_changed)
        self._filter_bar.expand_all_requested.connect(self._tree.expandAll)
        self._filter_bar.collapse_all_requested.connect(self._tree.collapseAll)
        self._details_panel.classify_clicked.connect(self.classify_requested)
        self._details_panel.unclassify_clicked.connect(self.unclassify_requested)
        self._details_panel.ai_help_clicked.connect(self.ai_help_requested)
        self._details_panel.documentation_clicked.connect(self.documentation_requested)
        self._details_panel.goto_source_clicked.connect(self.goto_source_requested)
        self._tree.entries_selected.connect(self.selection_changed)
        self._tree.entry_activated.connect(self.classify_requested)
        self._tree.context_menu_requested.connect(self._show_context_menu)
        self._welcome_page.open_log_clicked.connect(self.open_log_requested)
        self._welcome_page.open_project_clicked.connect(self.open_project_requested)
        self._welcome_page.try_sample_clicked.connect(self.try_sample_requested)
        self._welcome_page.tutorial_clicked.connect(self.tutorial_requested)
        self._welcome_page.choose_plugin_clicked.connect(self.load_plugin_requested)
        self._tutorial_panel.next_clicked.connect(self.tutorial_next_requested)
        self._tutorial_panel.previous_clicked.connect(self.tutorial_previous_requested)
        self._tutorial_panel.action_clicked.connect(self.tutorial_action_requested)
        self._tutorial_panel.quit_clicked.connect(self.tutorial_quit_requested)

    def _show_context_menu(self, global_position: QPoint) -> None:
        """Affiche le menu contextuel de l'arbre.

        :param global_position: position du clic à l'écran.
        """
        menu = QMenu(self)
        for key in ("classify", "unclassify", None, "ai_help", "documentation",
                    "goto_source"):
            if key is None:
                menu.addSeparator()
            else:
                menu.addAction(self._actions[key])
        menu.addSeparator()
        menu.addAction("Tout déplier", self._tree.expandAll)
        menu.addAction("Tout replier", self._tree.collapseAll)
        menu.exec_(global_position)

    @staticmethod
    def _set_highlight(widget: QWidget, enabled: bool) -> None:
        """Pose ou retire la propriété de mise en évidence et rafraîchit le style.

        :param widget: widget concerné.
        :param enabled: ``True`` pour mettre en évidence.
        """
        widget.setProperty(TUTORIAL_TARGET_PROPERTY, enabled)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _show_about(self) -> None:
        """Affiche la boîte « À propos »."""
        QMessageBox.about(
            self, f"À propos de {APP_NAME}",
            f"<b>{APP_NAME} {__version__}</b><br>Suivi et justification des messages "
            "de logs (notes, warnings, erreurs) pilotés par plugins.",
        )
