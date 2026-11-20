"""Fenêtre principale de LogWaver (vue passive du patron MVP).

La fenêtre n'exécute aucune logique métier : elle affiche ce que lui
transmet le présentateur et émet des signaux pour chaque intention de
l'utilisateur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Sequence

from PyQt5.QtCore import (
    QItemSelection,
    QModelIndex,
    QPoint,
    QSortFilterProxyModel,
    Qt,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import QCloseEvent, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QFileDialog,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from logwaver import __version__
from logwaver.constants import APP_NAME
from logwaver.view.dialogs.ai_help_dialog import AiHelpDialog
from logwaver.view.dialogs.justification_dialog import JustificationDialog
from logwaver.view.dialogs.pdf_viewer_dialog import PdfViewerDialog, is_web_engine_available
from logwaver.view.dialogs.plugin_editor_dialog import PluginEditorDialog
from logwaver.view.dialogs.source_viewer_dialog import SourceViewerDialog
from logwaver.view.entry_table_model import (
    COLUMN_CODE,
    COLUMN_DESCRIPTION,
    COLUMN_LINE,
    COLUMN_TYPE,
    ENTRY_ID_ROLE,
    SORT_ROLE,
    EntryTableModel,
)
from logwaver.view.widgets.category_panel import CategoryPanel
from logwaver.view.widgets.details_panel import DetailsPanel
from logwaver.view.widgets.filter_bar import FilterBar
from logwaver.view_models import (
    ANSWER_CANCEL,
    ANSWER_DISCARD,
    ANSWER_SAVE,
    ActionsState,
    AiHelpData,
    CategoryItem,
    EntryDetails,
    EntryRow,
    JustificationRequest,
    StatusBarInfo,
    StatusChoice,
)

STATUS_MESSAGE_TIMEOUT_MS: int = 6000


class MainWindow(QMainWindow):
    """Fenêtre principale : catégories | table filtrée | détails."""

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
    category_selected = pyqtSignal(str)
    filter_changed = pyqtSignal(str, str, str, str)
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
        self._category_panel = CategoryPanel()
        self._filter_bar = FilterBar()
        self._details_panel = DetailsPanel()
        self._table_model = EntryTableModel(self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._table_model)
        self._proxy_model.setSortRole(SORT_ROLE)
        self._table = QTableView()
        self._count_label = QLabel()
        self._count_label.setObjectName("CountLabel")
        self._status_info_label = QLabel()
        self._actions: dict = {}
        self._configure_table()
        self._create_actions()
        self._create_menus_and_toolbar()
        self._build_layout()
        self._connect_signals()

    # ======================================================= API présentateur
    def set_close_guard(self, guard: Callable[[], bool]) -> None:
        """Définit la fonction autorisant (ou non) la fermeture.

        :param guard: retourne ``True`` si la fenêtre peut se fermer.
        """
        self._close_guard = guard

    def set_entries(self, rows: Sequence[EntryRow], total: int) -> None:
        """Affiche les éléments filtrés en conservant la sélection si possible.

        :param rows: lignes à afficher.
        :param total: nombre total d'éléments (avant filtrage).
        """
        selected = set(self.selected_entry_ids())
        self._table.selectionModel().blockSignals(True)
        self._table_model.set_rows(rows)
        self._restore_selection(selected)
        self._table.selectionModel().blockSignals(False)
        self._count_label.setText(f"{len(rows)} élément(s) affiché(s) sur {total}")
        self._emit_selection()

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
            "open_log": state.has_plugin,
            "close_logs": state.has_entries,
            "classify": state.has_selection,
            "unclassify": state.selection_classified,
            "ai_help": state.single_selection,
            "documentation": state.single_selection and state.can_open_documentation,
            "goto_source": state.single_selection and state.can_open_source,
            "export_rules": state.has_justifications,
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
        undo.setToolTip(f"Annuler : {undo_text}" if can_undo else "Annuler")
        redo.setEnabled(can_redo)
        redo.setToolTip(f"Rétablir : {redo_text}" if can_redo else "Rétablir")

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
            f"{info.user_name or '—'}   |   Non justifiés : {info.unclassified}"
            f"/{info.total}   |   Classés : {info.ratio_text}"
        )

    def show_status_message(self, message: str) -> None:
        """Affiche un message temporaire dans la barre d'état.

        :param message: texte à afficher.
        """
        self.statusBar().showMessage(message, STATUS_MESSAGE_TIMEOUT_MS)

    def selected_entry_ids(self) -> List[int]:
        """Retourne les identifiants des éléments sélectionnés.

        :return: identifiants, dans l'ordre d'affichage.
        """
        rows = sorted(index.row() for index in self._table.selectionModel().selectedRows())
        return [int(self._proxy_model.index(row, 0).data(ENTRY_ID_ROLE)) for row in rows]

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
            self, "Utilisateur",
            "Votre nom (il sera associé à vos justifications) :",
            QLineEdit.Normal, current,
        )
        return name.strip() if accepted and name.strip() else None

    def ask_justification(self, statuses: Sequence[StatusChoice], selection_count: int,
                          same_code_count: int, initial_status_id: str,
                          initial_text: str) -> Optional[JustificationRequest]:
        """Ouvre le dialogue de classement.

        :param statuses: catégories proposées.
        :param selection_count: nombre d'éléments sélectionnés.
        :param same_code_count: nombre d'éléments du même code.
        :param initial_status_id: catégorie proposée.
        :param initial_text: justification préremplie.
        :return: saisie validée, ou ``None`` si annulée.
        """
        dialog = JustificationDialog(statuses, selection_count, same_code_count,
                                     initial_status_id, initial_text, self)
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

    def _configure_table(self) -> None:
        """Configure la table des éléments."""
        self._table.setObjectName("EntryTable")
        self._table.setModel(self._proxy_model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(COLUMN_DESCRIPTION, QHeaderView.Stretch)
        for column in (COLUMN_TYPE, COLUMN_CODE, COLUMN_LINE):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        self._table.sortByColumn(0, Qt.AscendingOrder)

    def _create_actions(self) -> None:
        """Crée les actions de menu et leurs raccourcis."""
        definitions = (
            ("new_project", "Nouveau projet", QKeySequence.New, self.new_project_requested),
            ("open_project", "Ouvrir un projet…", QKeySequence.Open, self.open_project_requested),
            ("save_project", "Enregistrer le projet", QKeySequence.Save,
             self.save_project_requested),
            ("save_project_as", "Enregistrer le projet sous…", QKeySequence.SaveAs,
             self.save_project_as_requested),
            ("load_plugin", "Charger un plugin…", "Ctrl+P", self.load_plugin_requested),
            ("open_log", "Ouvrir un fichier de log…", "Ctrl+L", self.open_log_requested),
            ("close_logs", "Fermer les logs", None, self.close_logs_requested),
            ("import_rules", "Importer des justifications…", "Ctrl+Shift+I",
             self.import_rules_requested),
            ("export_rules", "Exporter les justifications…", "Ctrl+Shift+E",
             self.export_rules_requested),
            ("export_excel", "Exporter vers Excel…", "Ctrl+E", self.export_excel_requested),
            ("export_docx", "Exporter un rapport Word…", None, self.export_docx_requested),
            ("quit", "Quitter", QKeySequence.Quit, None),
            ("undo", "Annuler", QKeySequence.Undo, self.undo_requested),
            ("redo", "Rétablir", QKeySequence.Redo, self.redo_requested),
            ("classify", "Classer / Justifier…", "Ctrl+J", self.classify_requested),
            ("unclassify", "Retirer la justification", QKeySequence.Delete,
             self.unclassify_requested),
            ("ai_help", "Aide IA…", "Ctrl+I", self.ai_help_requested),
            ("documentation", "Documentation PDF", "F1", self.documentation_requested),
            ("goto_source", "Aller à la ligne", "Ctrl+G", self.goto_source_requested),
            ("change_user", "Changer d'utilisateur…", None, self.change_user_requested),
            ("search", "Rechercher", QKeySequence.Find, None),
            ("plugin_editor", "Éditeur de plugin / testeur de regex…", "Ctrl+R",
             self.plugin_editor_requested),
            ("about", "À propos", None, None),
        )
        for key, text, shortcut, signal in definitions:
            action = QAction(text, self)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            if signal is not None:
                action.triggered.connect(signal)
            self._actions[key] = action
        self._actions["quit"].triggered.connect(self.close)
        self._actions["search"].triggered.connect(self._filter_bar.focus_search)
        self._actions["about"].triggered.connect(self._show_about)

    def _create_menus_and_toolbar(self) -> None:
        """Construit la barre de menus et la barre d'outils."""
        menus = (
            ("&Fichier", ("new_project", "open_project", "save_project", "save_project_as",
                          None, "load_plugin", "open_log", "close_logs", None,
                          "import_rules", "export_rules", None, "export_excel",
                          "export_docx", None, "quit")),
            ("&Édition", ("undo", "redo", None, "classify", "unclassify", None, "search",
                          None, "change_user")),
            ("É&lément", ("ai_help", "documentation", "goto_source")),
            ("&Outils", ("plugin_editor",)),
            ("&Aide", ("about",)),
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
        for key in ("open_project", "save_project", None, "load_plugin", "open_log", None,
                    "undo", "redo", None, "classify", "unclassify", "ai_help", None,
                    "import_rules", "export_rules", "export_excel"):
            if key is None:
                toolbar.addSeparator()
            else:
                toolbar.addAction(self._actions[key])
        self.addToolBar(toolbar)

    def _build_layout(self) -> None:
        """Dispose les trois panneaux dans des séparateurs redimensionnables."""
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self._filter_bar)
        center_layout.addWidget(self._table, stretch=1)
        center_layout.addWidget(self._count_label)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.addWidget(self._category_panel)
        splitter.addWidget(center)
        splitter.addWidget(self._details_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([260, 900, 340])
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(splitter)
        self.setCentralWidget(container)
        self.statusBar().addPermanentWidget(self._status_info_label)

    def _connect_signals(self) -> None:
        """Relie les widgets enfants aux signaux publics."""
        self._category_panel.category_selected.connect(self.category_selected)
        self._filter_bar.filter_changed.connect(self.filter_changed)
        self._details_panel.classify_clicked.connect(self.classify_requested)
        self._details_panel.unclassify_clicked.connect(self.unclassify_requested)
        self._details_panel.ai_help_clicked.connect(self.ai_help_requested)
        self._details_panel.documentation_clicked.connect(self.documentation_requested)
        self._details_panel.goto_source_clicked.connect(self.goto_source_requested)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

    def _on_selection_changed(self, _selected: QItemSelection,
                              _deselected: QItemSelection) -> None:
        """Relaie un changement de sélection.

        :param _selected: plages sélectionnées (inutilisées).
        :param _deselected: plages désélectionnées (inutilisées).
        """
        self._emit_selection()

    def _emit_selection(self) -> None:
        """Émet la liste des éléments sélectionnés."""
        self.selection_changed.emit(self.selected_entry_ids())

    def _on_double_click(self, _index: QModelIndex) -> None:
        """Ouvre le classement sur double-clic.

        :param _index: cellule cliquée (inutilisée).
        """
        self.classify_requested.emit()

    def _show_context_menu(self, position: QPoint) -> None:
        """Affiche le menu contextuel de la table.

        :param position: position du clic dans la table.
        """
        menu = QMenu(self)
        for key in ("classify", "unclassify", None, "ai_help", "documentation",
                    "goto_source"):
            if key is None:
                menu.addSeparator()
            else:
                menu.addAction(self._actions[key])
        menu.exec_(self._table.viewport().mapToGlobal(position))

    def _restore_selection(self, entry_ids: set) -> None:
        """Resélectionne les lignes encore visibles.

        :param entry_ids: identifiants précédemment sélectionnés.
        """
        selection_model = self._table.selectionModel()
        selection = QItemSelection()
        for row in range(self._proxy_model.rowCount()):
            index = self._proxy_model.index(row, 0)
            if index.data(ENTRY_ID_ROLE) in entry_ids:
                selection.select(index, index)
        selection_model.select(selection, selection_model.ClearAndSelect
                               | selection_model.Rows)

    def _show_about(self) -> None:
        """Affiche la boîte « À propos »."""
        QMessageBox.about(
            self, f"À propos de {APP_NAME}",
            f"<b>{APP_NAME} {__version__}</b><br>Suivi et justification des messages "
            "de logs (notes, warnings, erreurs) pilotés par plugins.",
        )
