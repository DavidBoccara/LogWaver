"""Assistant regex pas à pas : type → ligne d'exemple → éléments → vérification.

Vue passive : toute la logique (marques, génération, vérification) est dans
``RegexWizardPresenter``.
"""

from __future__ import annotations

from typing import Optional, Sequence

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from logwaver.constants import FIELD_LABELS, STANDARD_FIELDS
from logwaver.view.dialogs.regex_highlighter import RegexHighlighter
from logwaver.view_models import WizardCheckRow, WizardMarkView

PAGE_TYPE: int = 0
PAGE_LINE: int = 1
PAGE_ELEMENTS: int = 2
PAGE_CHECK: int = 3
LINE_TEXT_ROLE: int = Qt.UserRole + 20


def _hint(text: str) -> QLabel:
    """Crée un texte d'explication.

    :param text: explication (HTML simple).
    :return: étiquette avec retour à la ligne.
    """
    label = QLabel(text)
    label.setObjectName("HintLabel")
    label.setWordWrap(True)
    return label


class _LinePage(QWizardPage):
    """Étape 2 : choisir la ligne où apparaît l'élément complet."""

    def __init__(self, wizard: "RegexWizardDialog") -> None:
        """Construit la page.

        :param wizard: assistant parent.
        """
        super().__init__()
        self._wizard = wizard
        self.setTitle("2. Choisissez une ligne d'exemple")
        self.setSubTitle("Cliquez sur une ligne du log où l'élément apparaît en entier.")

    def isComplete(self) -> bool:  # noqa: N802
        """Autorise « Suivant » quand une ligne est choisie (API Qt).

        :return: ``True`` si une ligne est sélectionnée.
        """
        return bool(self._wizard.selected_line_text())


class _ElementsPage(QWizardPage):
    """Étape 3 : sélectionner les éléments à extraire et les parties ignorées."""

    def __init__(self, wizard: "RegexWizardDialog") -> None:
        """Construit la page.

        :param wizard: assistant parent.
        """
        super().__init__()
        self._wizard = wizard
        self.setTitle("3. Sélectionnez les éléments")
        self.setSubTitle("Surlignez à la souris chaque élément, puis cliquez sur son bouton.")

    def isComplete(self) -> bool:  # noqa: N802
        """Autorise « Suivant » dès qu'un élément est marqué (API Qt).

        :return: ``True`` si au moins un élément à extraire est marqué.
        """
        return self._wizard.has_field_marks()


class RegexWizardDialog(QWizard):
    """Assistant de création des regex d'un type d'élément.

    Signaux :
    * ``type_chosen(str)`` : type validé à l'étape 1 ;
    * ``line_chosen(str)`` : ligne d'exemple choisie ;
    * ``mark_requested(str, int, int)`` : champ (ou ``""`` pour une partie
      ignorée) et zone sélectionnée ;
    * ``remove_mark_requested(int)`` : supprimer la marque n° i ;
    * ``suggest_requested()`` : proposer les parties variables ;
    * ``check_requested()`` : générer et vérifier (entrée dans l'étape 4) ;
    * ``load_sample_requested()`` : charger un log d'exemple.
    """

    type_chosen = pyqtSignal(str)
    line_chosen = pyqtSignal(str)
    mark_requested = pyqtSignal(str, int, int)
    remove_mark_requested = pyqtSignal(int)
    suggest_requested = pyqtSignal()
    check_requested = pyqtSignal()
    load_sample_requested = pyqtSignal()

    def __init__(self, type_names: Sequence[str], initial_type: str,
                 parent: Optional[QWidget] = None) -> None:
        """Construit l'assistant.

        :param type_names: types existants dans le plugin.
        :param initial_type: type proposé.
        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("RegexWizard")
        self.setWindowTitle("Assistant regex pas à pas")
        self.setWizardStyle(QWizard.ModernStyle)
        self.resize(980, 700)
        self.setButtonText(QWizard.NextButton, "Suivant ▶")
        self.setButtonText(QWizard.BackButton, "◀ Précédent")
        self.setButtonText(QWizard.FinishButton, "Utiliser ces regex")
        self.setButtonText(QWizard.CancelButton, "Annuler")
        self._monospace = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self._field_names = list(STANDARD_FIELDS)
        self._has_field_marks = False
        self._add_type_page(type_names, initial_type)
        self._add_line_page()
        self._add_elements_page()
        self._add_check_page()
        self.currentIdChanged.connect(self._on_page_changed)

    # ================================================================== API
    def type_name(self) -> str:
        """Retourne le type d'élément choisi à l'étape 1.

        :return: nom du type (espaces retirés).
        """
        return self._type_combo.currentText().strip()

    def set_field_names(self, names: Sequence[str]) -> None:
        """Définit les champs proposés à l'étape 3 (boutons).

        :param names: champs du type choisi.
        """
        self._field_names = list(names) or list(STANDARD_FIELDS)
        self._rebuild_field_buttons()

    def set_sample_lines(self, lines: Sequence[str]) -> None:
        """Affiche les lignes d'exemple de l'étape 2.

        :param lines: lignes de l'exemple.
        """
        self._line_list.clear()
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            item = QListWidgetItem(f"{number:>5}  {line}")
            item.setData(LINE_TEXT_ROLE, line)
            self._line_list.addItem(item)
        self._filter_lines(self._line_filter.text())

    def selected_line_text(self) -> str:
        """Retourne la ligne d'exemple choisie.

        :return: texte de la ligne (vide si aucune).
        """
        item = self._line_list.currentItem()
        return str(item.data(LINE_TEXT_ROLE)) if item is not None else ""

    def set_marks(self, marks: Sequence[WizardMarkView], template: str) -> None:
        """Affiche les sélections et le modèle de ligne résultant.

        :param marks: sélections courantes.
        :param template: ligne où chaque sélection est remplacée par ‹nom›.
        """
        self._marks_list.clear()
        fields, ignored = {}, {}
        for mark in marks:
            prefix = "◌" if mark.ignored else "●"
            self._marks_list.addItem(f"{prefix} {mark.label} = « {mark.text} »")
            (ignored if mark.ignored else fields).setdefault(1, []).append(
                (mark.start, mark.end))
        self._highlighter.set_mark_ranges(fields)
        self._highlighter.set_ignored_ranges(ignored)
        self._template_label.setText(template)
        self._has_field_marks = any(not mark.ignored for mark in marks)
        self.page(PAGE_ELEMENTS).completeChanged.emit()

    def has_field_marks(self) -> bool:
        """Indique si au moins un élément à extraire est marqué.

        :return: ``True`` si oui.
        """
        return self._has_field_marks

    def show_check(self, detect_regex: str, field_regexes: Sequence[tuple],
                   rows: Sequence[WizardCheckRow], summary: str, error: str) -> None:
        """Affiche le résultat de la génération à l'étape 4.

        :param detect_regex: regex de détection.
        :param field_regexes: couples (champ, regex).
        :param rows: valeurs extraites des lignes reconnues.
        :param summary: phrase de bilan.
        :param error: message d'erreur (vide si la génération a réussi).
        """
        self._check_error = bool(error)
        self._check_summary.setText(error or summary)
        self._check_summary.setProperty("state", "error" if error else "ok")
        self._check_summary.style().unpolish(self._check_summary)
        self._check_summary.style().polish(self._check_summary)
        lines = [f"detect = {detect_regex}"] + [f"regex.{n} = {r}" for n, r in field_regexes]
        self._regex_text.setPlainText("" if error else "\n".join(lines))
        names = [name for name, _ in field_regexes]
        self._check_table.clear()
        self._check_table.setColumnCount(len(names) + 1)
        self._check_table.setHorizontalHeaderLabels(
            ["N° dans l'exemple"] + [FIELD_LABELS.get(n, n) for n in names])
        self._check_table.setRowCount(0 if error else len(rows))
        for row_index, row in enumerate(rows if not error else ()):
            self._check_table.setItem(row_index, 0, QTableWidgetItem(str(row.line_number)))
            for column, value in enumerate(row.values, start=1):
                self._check_table.setItem(row_index, column, QTableWidgetItem(value))
        self.button(QWizard.FinishButton).setEnabled(not error)

    def ask_field_name(self) -> Optional[str]:
        """Demande le nom d'un champ supplémentaire.

        :return: nom saisi, ou ``None``.
        """
        name, accepted = QInputDialog.getText(
            self, "Autre champ", "Nom du champ (ex. module, severite) :")
        name = name.strip().replace(" ", "_")
        return name if accepted and name else None

    # ================================================================ pages
    def _add_type_page(self, type_names: Sequence[str], initial_type: str) -> None:
        """Crée l'étape 1 : choix du type.

        :param type_names: types existants.
        :param initial_type: type proposé.
        """
        page = QWizardPage()
        page.setTitle("1. Quel type d'élément voulez-vous reconnaître ?")
        page.setSubTitle("Choisissez un type existant ou tapez un nouveau nom.")
        self._type_combo = QComboBox()
        self._type_combo.setEditable(True)
        self._type_combo.addItems(list(type_names) or ["Warning"])
        self._type_combo.setCurrentText(initial_type or self._type_combo.itemText(0))
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Type d'élément :"))
        layout.addWidget(self._type_combo)
        layout.addWidget(_hint(
            "Exemples : <b>Warning</b>, <b>Error</b>, <b>Note</b>. L'assistant crée la "
            "regex qui reconnaît ce type de ligne et celles qui en extraient chaque "
            "élément."))
        layout.addStretch(1)
        self.addPage(page)

    def _add_line_page(self) -> None:
        """Crée l'étape 2 : choix de la ligne d'exemple."""
        page = _LinePage(self)
        self._line_filter = QLineEdit()
        self._line_filter.setPlaceholderText("Filtrer les lignes (ex. WARNING)…")
        self._line_filter.setClearButtonEnabled(True)
        self._line_list = QListWidget()
        self._line_list.setFont(self._monospace)
        load_button = QPushButton("Charger un log d'exemple…")
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(self._line_filter, stretch=1)
        row.addWidget(load_button)
        layout.addLayout(row)
        layout.addWidget(self._line_list, stretch=1)
        self._line_filter.textChanged.connect(self._filter_lines)
        self._line_list.currentItemChanged.connect(lambda *_: page.completeChanged.emit())
        load_button.clicked.connect(self.load_sample_requested)
        self.addPage(page)

    def _add_elements_page(self) -> None:
        """Crée l'étape 3 : marquage des éléments et des parties variables."""
        page = _ElementsPage(self)
        self._line_view = QPlainTextEdit()
        self._line_view.setObjectName("WizardLine")
        self._line_view.setReadOnly(True)
        self._line_view.setFont(self._monospace)
        self._line_view.setMaximumHeight(80)
        self._highlighter = RegexHighlighter(self._line_view.document())
        self._field_buttons_box = QWidget()
        self._field_buttons_layout = QGridLayout(self._field_buttons_box)
        self._field_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._ignore_button = QPushButton("◌ Partie variable sans intérêt (date, heure…)")
        self._suggest_button = QPushButton("Proposer automatiquement les parties variables")
        self._marks_list = QListWidget()
        self._remove_button = QPushButton("Retirer la sélection choisie")
        self._template_label = QLabel()
        self._template_label.setObjectName("WizardTemplate")
        self._template_label.setWordWrap(True)
        self._template_label.setFont(self._monospace)
        layout = QVBoxLayout(page)
        layout.addWidget(_hint(
            "<b>●</b> Surlignez la valeur d'un élément (chemin du fichier, code…) puis "
            "cliquez sur son bouton. Chaque élément pourra prendre <b>n'importe quelle "
            "valeur</b> sur les autres lignes.<br><b>◌</b> Marquez aussi ce qui change "
            "d'une ligne à l'autre sans vous intéresser (date, heure, identifiant).<br>"
            "<b>Tout le reste est considéré comme fixe</b> : c'est lui qui permet de "
            "reconnaître la ligne."))
        layout.addWidget(self._line_view)
        layout.addWidget(QLabel("Marquer la sélection comme :"))
        layout.addWidget(self._field_buttons_box)
        ignore_row = QHBoxLayout()
        ignore_row.addWidget(self._ignore_button)
        ignore_row.addWidget(self._suggest_button)
        layout.addLayout(ignore_row)
        layout.addWidget(QLabel("Sélections :"))
        layout.addWidget(self._marks_list, stretch=1)
        layout.addWidget(self._remove_button)
        layout.addWidget(QLabel("Modèle de ligne obtenu (texte fixe et ‹éléments›) :"))
        layout.addWidget(self._template_label)
        self._ignore_button.clicked.connect(lambda: self._emit_mark(""))
        self._suggest_button.clicked.connect(self.suggest_requested)
        self._remove_button.clicked.connect(self._emit_remove)
        self._rebuild_field_buttons()
        self.addPage(page)

    def _add_check_page(self) -> None:
        """Crée l'étape 4 : vérification sur tout l'exemple."""
        page = QWizardPage()
        page.setTitle("4. Vérifiez le résultat")
        page.setSubTitle("Les regex générées sont appliquées à toutes les lignes de l'exemple.")
        self._check_summary = QLabel()
        self._check_summary.setObjectName("TestStatus")
        self._check_summary.setWordWrap(True)
        self._regex_text = QPlainTextEdit()
        self._regex_text.setReadOnly(True)
        self._regex_text.setFont(self._monospace)
        self._regex_text.setMaximumHeight(130)
        self._check_table = QTableWidget(0, 1)
        self._check_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._check_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._check_error = False
        layout = QVBoxLayout(page)
        layout.addWidget(self._check_summary)
        layout.addWidget(QLabel("Regex générées (enregistrées dans le plugin) :"))
        layout.addWidget(self._regex_text)
        layout.addWidget(QLabel("Valeurs extraites des lignes reconnues :"))
        layout.addWidget(self._check_table, stretch=1)
        layout.addWidget(_hint(
            "Si une ligne attendue manque ou qu'une valeur est fausse, revenez à l'étape 3 "
            "pour marquer une partie variable ou ajuster une sélection."))
        self.addPage(page)

    # ============================================================== interne
    def _rebuild_field_buttons(self) -> None:
        """Recrée un bouton par champ, plus « Autre champ… »."""
        while self._field_buttons_layout.count():
            widget = self._field_buttons_layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        names = self._field_names + [""]
        for index, name in enumerate(names):
            label = f"● {FIELD_LABELS.get(name, name)}" if name else "● Autre champ…"
            button = QPushButton(label)
            button.setProperty("role", "primary" if name else "")
            button.clicked.connect(lambda _checked=False, n=name: self._on_field_button(n))
            self._field_buttons_layout.addWidget(button, index // 4, index % 4)

    def _on_field_button(self, name: str) -> None:
        """Marque la sélection comme valeur d'un champ.

        :param name: champ visé (vide = demander un nouveau nom).
        """
        if not name:
            name = self.ask_field_name() or ""
            if not name:
                return
        self._emit_mark(name)

    def _emit_mark(self, name: str) -> None:
        """Émet la sélection courante de la ligne.

        :param name: champ visé (vide = partie ignorée).
        """
        cursor = self._line_view.textCursor()
        if cursor.hasSelection():
            self.mark_requested.emit(name, cursor.selectionStart(), cursor.selectionEnd())

    def _emit_remove(self) -> None:
        """Émet la suppression de la sélection choisie dans la liste."""
        row = self._marks_list.currentRow()
        if row >= 0:
            self.remove_mark_requested.emit(row)

    def _filter_lines(self, text: str) -> None:
        """Masque les lignes ne contenant pas le filtre.

        :param text: filtre saisi.
        """
        fragment = text.casefold()
        for row in range(self._line_list.count()):
            item = self._line_list.item(row)
            item.setHidden(bool(fragment) and fragment not in item.text().casefold())

    def _on_page_changed(self, page_id: int) -> None:
        """Prévient le présentateur des changements d'étape.

        :param page_id: étape affichée.
        """
        if page_id == PAGE_LINE:
            self.type_chosen.emit(self.type_name())
        elif page_id == PAGE_ELEMENTS:
            line = self.selected_line_text()
            if line != self._line_view.toPlainText():
                self._line_view.setPlainText(line)
                self.line_chosen.emit(line)
        elif page_id == PAGE_CHECK:
            self.check_requested.emit()
