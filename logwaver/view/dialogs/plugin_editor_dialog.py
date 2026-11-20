"""Éditeur de plugin avec testeur de regex et génération automatique.

La vue conserve uniquement l'état du formulaire (texte saisi). Toute la
logique (test, génération, validation, lecture/écriture) est confiée au
présentateur via des signaux.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFontDatabase, QTextCursor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from logwaver.constants import STANDARD_FIELDS
from logwaver.view.dialogs.regex_highlighter import RegexHighlighter
from logwaver.view_models import PluginFormData, PluginTypeData, RegexTestRow, SelectionMark

TEST_DEBOUNCE_MS: int = 300
FIELD_COLUMN_NAME: int = 0
FIELD_COLUMN_REGEX: int = 1
GENERATION_HELP: str = (
    "Génération automatique : collez une ligne de log dans l'exemple, "
    "sélectionnez à la souris la valeur d'un champ, choisissez le champ puis "
    "cliquez sur « Marquer la sélection ». Répétez pour chaque champ, puis "
    "cliquez sur « Générer les regex »."
)


class PluginEditorDialog(QDialog):
    """Formulaire d'édition d'un fichier plugin."""

    open_requested = pyqtSignal()
    save_requested = pyqtSignal()
    save_as_requested = pyqtSignal()
    validate_requested = pyqtSignal()
    load_sample_requested = pyqtSignal()
    test_requested = pyqtSignal(str, str)
    mark_requested = pyqtSignal(object)
    clear_marks_requested = pyqtSignal()
    generate_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Construit l'éditeur.

        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("PluginEditorDialog")
        self.setWindowTitle("Éditeur de plugin et testeur de regex")
        self.resize(1250, 820)
        self._types: Dict[str, PluginTypeData] = {}
        self._current_type: str = ""
        self._active_field_row: int = -1  # -1 = regex de détection active
        self._create_widgets()
        self._build_layout()
        self._connect_signals()

    # ======================================================== API présentateur
    def set_form_data(self, data: PluginFormData) -> None:
        """Remplit le formulaire.

        :param data: contenu du plugin.
        """
        self._tool_edit.setText(data.tool_name)
        self._pdf_edit.setText(data.pdf_documentation)
        self._index_edit.setText(data.pdf_page_index)
        self._types = {item.name: item for item in data.types}
        self._current_type = ""
        self._type_list.blockSignals(True)
        self._type_list.clear()
        self._type_list.addItems([item.name for item in data.types])
        self._type_list.blockSignals(False)
        if data.types:
            self._type_list.setCurrentRow(0)
        else:
            self._show_type(None)

    def form_data(self) -> PluginFormData:
        """Retourne le contenu actuel du formulaire.

        :return: données du plugin.
        """
        self._store_current_type()
        ordered = [self._type_list.item(i).text() for i in range(self._type_list.count())]
        return PluginFormData(
            tool_name=self._tool_edit.text().strip(),
            pdf_documentation=self._pdf_edit.text().strip(),
            pdf_page_index=self._index_edit.text().strip(),
            types=tuple(self._types[name] for name in ordered),
        )

    def set_file_label(self, text: str) -> None:
        """Affiche le fichier en cours d'édition.

        :param text: chemin ou mention « nouveau ».
        """
        self._file_label.setText(text)

    def set_sample_text(self, text: str) -> None:
        """Remplace le texte d'exemple.

        :param text: lignes de log d'exemple.
        """
        self._sample_edit.setPlainText(text)

    def show_test_result(self, rows: Sequence[RegexTestRow], error: str,
                         truncated: bool) -> None:
        """Affiche le résultat du test de la regex active.

        :param rows: correspondances.
        :param error: erreur de compilation (vide si valide).
        :param truncated: ``True`` si les résultats sont tronqués.
        """
        self._result_table.setRowCount(0)
        ranges: Dict[int, List[Tuple[int, int]]] = {}
        for row in rows:
            position = self._result_table.rowCount()
            self._result_table.insertRow(position)
            self._result_table.setItem(position, 0, QTableWidgetItem(str(row.line_number)))
            self._result_table.setItem(position, 1, QTableWidgetItem(row.extracted))
            ranges.setdefault(row.line_number, []).append((row.start, row.end))
        self._highlighter.set_match_ranges(ranges)
        if error:
            self._test_status.setText(f"Regex invalide : {error}")
            self._test_status.setProperty("state", "error")
        else:
            suffix = " (résultats tronqués)" if truncated else ""
            self._test_status.setText(f"{len(rows)} correspondance(s){suffix}")
            self._test_status.setProperty("state", "ok" if rows else "warning")
        self._test_status.style().unpolish(self._test_status)
        self._test_status.style().polish(self._test_status)

    def set_marks(self, marks: Sequence[SelectionMark]) -> None:
        """Affiche les sélections marquées pour la génération.

        :param marks: sélections courantes.
        """
        self._marks_list.clear()
        ranges: Dict[int, List[Tuple[int, int]]] = {}
        for mark in marks:
            self._marks_list.addItem(f"{mark.field_name} = « {mark.selected_text} »")
            ranges.setdefault(mark.line_number, []).append((mark.start, mark.end))
        self._highlighter.set_mark_ranges(ranges)
        self._generate_button.setEnabled(bool(marks))

    def apply_generated(self, detect_regex: str,
                        field_regexes: Sequence[Tuple[str, str]]) -> None:
        """Remplace les regex du type courant par des regex générées.

        :param detect_regex: regex de détection.
        :param field_regexes: couples (champ, regex).
        """
        if not self._current_type:
            return
        existing = dict(self._read_field_rows())
        existing.update(dict(field_regexes))
        order = [name for name, _ in self._read_field_rows()]
        order += [name for name, _ in field_regexes if name not in order]
        self._detect_edit.setText(detect_regex)
        self._fill_field_rows([(name, existing[name]) for name in order])
        self._store_current_type()
        self._request_test()

    def current_type_name(self) -> str:
        """Retourne le type d'élément en cours d'édition.

        :return: nom du type (vide si aucun).
        """
        return self._current_type

    def ask_open_path(self, title: str, file_filter: str) -> Optional[str]:
        """Demande un fichier à ouvrir.

        :param title: titre du dialogue.
        :param file_filter: filtre de fichiers Qt.
        :return: chemin choisi, ou ``None``.
        """
        path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        return path or None

    def ask_save_path(self, title: str, file_filter: str, default: str) -> Optional[str]:
        """Demande un fichier de destination.

        :param title: titre du dialogue.
        :param file_filter: filtre de fichiers Qt.
        :param default: nom proposé.
        :return: chemin choisi, ou ``None``.
        """
        path, _ = QFileDialog.getSaveFileName(self, title, default, file_filter)
        return path or None

    def show_error(self, message: str) -> None:
        """Affiche une erreur.

        :param message: texte de l'erreur.
        """
        QMessageBox.critical(self, "Éditeur de plugin", message)

    def show_info(self, message: str) -> None:
        """Affiche une information.

        :param message: texte de l'information.
        """
        QMessageBox.information(self, "Éditeur de plugin", message)

    # ================================================================ widgets
    def _create_widgets(self) -> None:
        """Crée tous les widgets du formulaire."""
        monospace = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self._file_label = QLabel("Nouveau plugin")
        self._file_label.setObjectName("HintLabel")
        self._tool_edit = QLineEdit()
        self._pdf_edit = QLineEdit()
        self._pdf_edit.setPlaceholderText("chemin relatif au plugin, ex. manuel.pdf")
        self._index_edit = QLineEdit()
        self._index_edit.setPlaceholderText("ex. manuel_index.ini")
        self._type_list = QListWidget()
        self._add_type_button = QPushButton("Ajouter")
        self._rename_type_button = QPushButton("Renommer")
        self._remove_type_button = QPushButton("Supprimer")
        self._detect_edit = QLineEdit()
        self._detect_edit.setFont(monospace)
        self._field_table = QTableWidget(0, 2)
        self._field_table.setHorizontalHeaderLabels(["Champ", "Regex"])
        self._field_table.horizontalHeader().setSectionResizeMode(
            FIELD_COLUMN_REGEX, QHeaderView.Stretch)
        self._field_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._field_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._field_table.setFont(monospace)
        self._add_field_button = QPushButton("Ajouter un champ")
        self._remove_field_button = QPushButton("Supprimer le champ")
        self._test_detect_button = QPushButton("Tester la détection")
        self._sample_edit = QPlainTextEdit()
        self._sample_edit.setFont(monospace)
        self._sample_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._sample_edit.setPlaceholderText("Collez ici des lignes de log d'exemple…")
        self._highlighter = RegexHighlighter(self._sample_edit.document())
        self._load_sample_button = QPushButton("Charger un log d'exemple…")
        self._test_status = QLabel()
        self._test_status.setObjectName("TestStatus")
        self._result_table = QTableWidget(0, 2)
        self._result_table.setHorizontalHeaderLabels(["Ligne", "Valeur extraite"])
        self._result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._mark_field_combo = QComboBox()
        self._mark_field_combo.setEditable(True)
        self._mark_button = QPushButton("Marquer la sélection")
        self._clear_marks_button = QPushButton("Réinitialiser")
        self._marks_list = QListWidget()
        self._generate_button = QPushButton("Générer les regex")
        self._generate_button.setProperty("role", "primary")
        self._generate_button.setEnabled(False)
        self._open_button = QPushButton("Ouvrir…")
        self._save_button = QPushButton("Enregistrer")
        self._save_as_button = QPushButton("Enregistrer sous…")
        self._validate_button = QPushButton("Valider le plugin")
        self._close_button = QPushButton("Fermer")
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(TEST_DEBOUNCE_MS)

    def _build_layout(self) -> None:
        """Dispose les widgets dans des layouts imbriqués."""
        general_box = QGroupBox("Plugin")
        general_form = QFormLayout(general_box)
        general_form.addRow("Fichier :", self._file_label)
        general_form.addRow("Nom de l'outil :", self._tool_edit)
        general_form.addRow("Documentation PDF :", self._pdf_edit)
        general_form.addRow("Index des pages :", self._index_edit)

        types_box = QGroupBox("Types d'éléments")
        types_layout = QVBoxLayout(types_box)
        types_layout.addWidget(self._type_list)
        type_buttons = QHBoxLayout()
        for button in (self._add_type_button, self._rename_type_button,
                       self._remove_type_button):
            type_buttons.addWidget(button)
        types_layout.addLayout(type_buttons)

        regex_box = QGroupBox("Regex du type sélectionné")
        regex_layout = QVBoxLayout(regex_box)
        detect_row = QHBoxLayout()
        detect_row.addWidget(QLabel("Détection :"))
        detect_row.addWidget(self._detect_edit, stretch=1)
        detect_row.addWidget(self._test_detect_button)
        regex_layout.addLayout(detect_row)
        regex_layout.addWidget(self._field_table, stretch=1)
        field_buttons = QHBoxLayout()
        field_buttons.addWidget(self._add_field_button)
        field_buttons.addWidget(self._remove_field_button)
        field_buttons.addStretch(1)
        regex_layout.addLayout(field_buttons)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(general_box)
        left_layout.addWidget(types_box)
        left_layout.addWidget(regex_box, stretch=1)

        sample_box = QGroupBox("Exemple de log et résultats du test")
        sample_layout = QVBoxLayout(sample_box)
        sample_layout.addWidget(self._load_sample_button, alignment=Qt.AlignLeft)
        sample_layout.addWidget(self._sample_edit, stretch=2)
        sample_layout.addWidget(self._test_status)
        sample_layout.addWidget(self._result_table, stretch=1)

        generation_box = QGroupBox("Assistant de génération automatique")
        generation_layout = QVBoxLayout(generation_box)
        help_label = QLabel(GENERATION_HELP)
        help_label.setObjectName("HintLabel")
        help_label.setWordWrap(True)
        generation_layout.addWidget(help_label)
        mark_row = QHBoxLayout()
        mark_row.addWidget(QLabel("Champ :"))
        mark_row.addWidget(self._mark_field_combo, stretch=1)
        mark_row.addWidget(self._mark_button)
        mark_row.addWidget(self._clear_marks_button)
        generation_layout.addLayout(mark_row)
        generation_layout.addWidget(self._marks_list)
        generation_layout.addWidget(self._generate_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(sample_box, stretch=2)
        right_layout.addWidget(generation_box, stretch=1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        bottom = QHBoxLayout()
        for button in (self._open_button, self._save_button, self._save_as_button,
                       self._validate_button):
            bottom.addWidget(button)
        bottom.addStretch(1)
        bottom.addWidget(self._close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, stretch=1)
        layout.addLayout(bottom)

    def _connect_signals(self) -> None:
        """Relie les widgets aux gestionnaires internes et signaux publics."""
        self._type_list.currentTextChanged.connect(self._on_type_changed)
        self._add_type_button.clicked.connect(self._add_type)
        self._rename_type_button.clicked.connect(self._rename_type)
        self._remove_type_button.clicked.connect(self._remove_type)
        self._add_field_button.clicked.connect(self._add_field)
        self._remove_field_button.clicked.connect(self._remove_field)
        self._detect_edit.textEdited.connect(self._activate_detect)
        self._test_detect_button.clicked.connect(self._activate_detect)
        self._field_table.currentCellChanged.connect(self._on_field_row_changed)
        self._field_table.itemChanged.connect(self._on_field_item_changed)
        self._sample_edit.textChanged.connect(self._debounce.start)
        self._debounce.timeout.connect(self._request_test)
        self._load_sample_button.clicked.connect(self.load_sample_requested)
        self._mark_button.clicked.connect(self._emit_mark)
        self._clear_marks_button.clicked.connect(self.clear_marks_requested)
        self._generate_button.clicked.connect(self.generate_requested)
        self._open_button.clicked.connect(self.open_requested)
        self._save_button.clicked.connect(self.save_requested)
        self._save_as_button.clicked.connect(self.save_as_requested)
        self._validate_button.clicked.connect(self.validate_requested)
        self._close_button.clicked.connect(self.accept)

    # ======================================================== types et champs
    def _on_type_changed(self, type_name: str) -> None:
        """Change le type en cours d'édition.

        :param type_name: type sélectionné.
        """
        self._store_current_type()
        self._show_type(self._types.get(type_name))

    def _show_type(self, item: Optional[PluginTypeData]) -> None:
        """Affiche les regex d'un type.

        :param item: type à afficher, ``None`` pour vider.
        """
        self._current_type = item.name if item else ""
        self._detect_edit.setText(item.detect_regex if item else "")
        self._fill_field_rows(item.field_regexes if item else ())
        for widget in (self._detect_edit, self._field_table, self._add_field_button,
                       self._remove_field_button, self._test_detect_button):
            widget.setEnabled(item is not None)
        self._refresh_mark_fields()
        self._activate_detect()

    def _store_current_type(self) -> None:
        """Mémorise les saisies du type courant."""
        if not self._current_type:
            return
        self._types[self._current_type] = PluginTypeData(
            name=self._current_type,
            detect_regex=self._detect_edit.text().strip(),
            field_regexes=tuple(self._read_field_rows()),
        )

    def _fill_field_rows(self, rows: Sequence[Tuple[str, str]]) -> None:
        """Remplit la table des champs.

        :param rows: couples (champ, regex).
        """
        self._field_table.blockSignals(True)
        self._field_table.setRowCount(0)
        for name, regex in rows:
            position = self._field_table.rowCount()
            self._field_table.insertRow(position)
            self._field_table.setItem(position, FIELD_COLUMN_NAME, QTableWidgetItem(name))
            self._field_table.setItem(position, FIELD_COLUMN_REGEX, QTableWidgetItem(regex))
        self._field_table.blockSignals(False)

    def _read_field_rows(self) -> List[Tuple[str, str]]:
        """Lit la table des champs.

        :return: couples (champ, regex) dont le nom n'est pas vide.
        """
        rows: List[Tuple[str, str]] = []
        for index in range(self._field_table.rowCount()):
            name_item = self._field_table.item(index, FIELD_COLUMN_NAME)
            regex_item = self._field_table.item(index, FIELD_COLUMN_REGEX)
            name = name_item.text().strip() if name_item else ""
            if name:
                rows.append((name, regex_item.text().strip() if regex_item else ""))
        return rows

    def _add_type(self) -> None:
        """Ajoute un type d'élément (nom demandé à l'utilisateur)."""
        name, accepted = QInputDialog.getText(self, "Nouveau type", "Nom du type :")
        name = name.strip()
        if not accepted or not name:
            return
        if name in self._types:
            self.show_error(f"Le type « {name} » existe déjà.")
            return
        self._types[name] = PluginTypeData(
            name, "", tuple((field, "") for field in STANDARD_FIELDS)
        )
        self._type_list.addItem(name)
        self._type_list.setCurrentRow(self._type_list.count() - 1)

    def _rename_type(self) -> None:
        """Renomme le type sélectionné."""
        item = self._type_list.currentItem()
        if item is None:
            return
        new_name, accepted = QInputDialog.getText(self, "Renommer", "Nouveau nom :",
                                                  text=item.text())
        new_name = new_name.strip()
        if not accepted or not new_name or new_name == item.text():
            return
        if new_name in self._types:
            self.show_error(f"Le type « {new_name} » existe déjà.")
            return
        self._store_current_type()
        old = self._types.pop(item.text())
        self._types[new_name] = PluginTypeData(new_name, old.detect_regex, old.field_regexes)
        self._current_type = new_name
        self._type_list.blockSignals(True)
        item.setText(new_name)
        self._type_list.blockSignals(False)

    def _remove_type(self) -> None:
        """Supprime le type sélectionné."""
        row = self._type_list.currentRow()
        if row < 0:
            return
        name = self._type_list.item(row).text()
        self._types.pop(name, None)
        self._current_type = ""
        self._type_list.takeItem(row)
        if self._type_list.count() == 0:
            self._show_type(None)

    def _add_field(self) -> None:
        """Ajoute une ligne vide à la table des champs."""
        position = self._field_table.rowCount()
        self._field_table.insertRow(position)
        self._field_table.setItem(position, FIELD_COLUMN_NAME, QTableWidgetItem("nouveau_champ"))
        self._field_table.setItem(position, FIELD_COLUMN_REGEX, QTableWidgetItem(""))
        self._field_table.setCurrentCell(position, FIELD_COLUMN_NAME)
        self._field_table.editItem(self._field_table.item(position, FIELD_COLUMN_NAME))

    def _remove_field(self) -> None:
        """Supprime le champ sélectionné."""
        row = self._field_table.currentRow()
        if row >= 0:
            self._field_table.removeRow(row)
            self._store_current_type()
            self._refresh_mark_fields()
            self._activate_detect()

    def _refresh_mark_fields(self) -> None:
        """Propose les champs du type courant dans l'assistant."""
        current = self._mark_field_combo.currentText()
        names = [name for name, _ in self._read_field_rows()] or list(STANDARD_FIELDS)
        self._mark_field_combo.clear()
        self._mark_field_combo.addItems(names)
        if current in names:
            self._mark_field_combo.setCurrentText(current)

    # ================================================================ tests
    def _activate_detect(self) -> None:
        """Rend la regex de détection active et la teste."""
        self._active_field_row = -1
        self._request_test()

    def _on_field_row_changed(self, row: int, _column: int, _prev_row: int,
                              _prev_column: int) -> None:
        """Rend active la regex du champ sélectionné.

        :param row: nouvelle ligne courante.
        :param _column: colonne courante (inutilisée).
        :param _prev_row: ligne précédente (inutilisée).
        :param _prev_column: colonne précédente (inutilisée).
        """
        if row >= 0:
            self._active_field_row = row
            name_item = self._field_table.item(row, FIELD_COLUMN_NAME)
            if name_item is not None:
                self._mark_field_combo.setCurrentText(name_item.text())
            self._request_test()

    def _on_field_item_changed(self, _item: QTableWidgetItem) -> None:
        """Mémorise et reteste après modification d'une cellule.

        :param _item: cellule modifiée (inutilisée).
        """
        self._store_current_type()
        self._refresh_mark_fields()
        self._debounce.start()

    def _request_test(self) -> None:
        """Émet ``test_requested`` pour la regex active."""
        self._test_status.setText("")
        self.test_requested.emit(self._active_pattern(), self._sample_edit.toPlainText())

    def _active_pattern(self) -> str:
        """Retourne le texte de la regex active.

        :return: regex de détection ou du champ sélectionné.
        """
        if 0 <= self._active_field_row < self._field_table.rowCount():
            item = self._field_table.item(self._active_field_row, FIELD_COLUMN_REGEX)
            return item.text() if item else ""
        return self._detect_edit.text()

    # ============================================================ génération
    def _emit_mark(self) -> None:
        """Émet la sélection courante de l'exemple associée à un champ."""
        cursor: QTextCursor = self._sample_edit.textCursor()
        field_name = self._mark_field_combo.currentText().strip()
        if not cursor.hasSelection() or not field_name:
            self.show_error("Sélectionnez du texte dans l'exemple et choisissez un champ.")
            return
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        document = self._sample_edit.document()
        block = document.findBlock(start)
        if document.findBlock(end - 1).blockNumber() != block.blockNumber():
            self.show_error("La sélection doit tenir sur une seule ligne.")
            return
        self.mark_requested.emit(SelectionMark(
            field_name=field_name,
            line_number=block.blockNumber() + 1,
            line_text=block.text(),
            start=start - block.position(),
            end=end - block.position(),
        ))
